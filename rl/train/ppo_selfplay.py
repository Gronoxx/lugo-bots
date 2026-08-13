"""
PPO self-play (MAPPO, param-sharing) para o Lugo em JAX.

Aprendiz controla o HOME (11 atores compartilhados + crítico central sobre a
global obs). AWAY = oponente FROZEN amostrado de um pool (init = clone-BC do v9).
Reward de time (gol±1 + shaping), GAE, ratio por-agente, clip PPO, minibatches.
Periodicamente o aprendiz vira snapshot no pool (self-play).

  ../.venv-rl/bin/python rl/train/ppo_selfplay.py [--updates N] [--bc] [--episode-len L]

Salva rl/checkpoints/policy.pkl.
"""
import argparse
import pickle
import sys
import time
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in (_R / "rl/envs", _R / "rl/jax", _R / "rl/train"):
    sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp
import numpy as np
import optax

import lugo_env as E
import step as J
from networks import Actor, Critic, sample_action, action_logprob, entropy

B, T = 512, 128
EPOCHS, N_MB = 4, 4
GAMMA, LAM = 0.99, 0.95
CLIP, VF, ENT, LR = 0.2, 0.5, 0.003, 3e-4
SNAP_EVERY = 25

actor = Actor(nvec=tuple(E.META["action_nvec"]))
critic = Critic()
OPT = optax.chain(optax.clip_by_global_norm(0.5), optax.adam(LR))


def _act(params, aobs_side, key):
    return sample_action(actor.apply(params, aobs_side), key)


def make_rollout(env_step, opp_static=False):
    @jax.jit
    def rollout(lp, cp, opp, state, obs, key):
        def stepf(carry, _):
            state, obs, key = carry
            aobs, gobs = obs
            key, kH, kA = jax.random.split(key, 3)
            aH, lpH = _act(lp, aobs[:, J.HOME], kH)
            if opp_static:
                aA = jnp.zeros_like(aH)
            else:
                aA, _ = _act(opp, aobs[:, J.AWAY], kA)
            val = critic.apply(cp, gobs[:, J.HOME])
            action = jnp.stack([aH, aA], axis=1)
            s2, obs2, reward, done, _ = env_step(state, action)
            tr = dict(obs=aobs[:, J.HOME], gobs=gobs[:, J.HOME], act=aH,
                      logp=lpH, val=val, rew=reward[:, J.HOME, 0], done=done)
            return (s2, obs2, key), tr
        (state, obs, key), traj = jax.lax.scan(stepf, (state, obs, key), None, length=T)
        last_val = critic.apply(cp, obs[1][:, J.HOME])
        return state, obs, key, traj, last_val
    return rollout


def gae(rew, val, done, last_val):
    def f(carry, x):
        adv, next_val = carry
        r, v, d = x
        delta = r + GAMMA * next_val * (1 - d) - v
        adv = delta + GAMMA * LAM * (1 - d) * adv
        return (adv, v), adv
    _, adv = jax.lax.scan(f, (jnp.zeros_like(last_val), last_val),
                          (rew, val, done), reverse=True)
    return adv, adv + val


@jax.jit
def update(lp, cp, ostate, traj, adv, ret, key):
    N = T * B
    mbsize = N // N_MB
    flat = lambda x: x.reshape((N,) + x.shape[2:])
    obs, gobs, act = flat(traj["obs"]), flat(traj["gobs"]), flat(traj["act"])
    old_logp = flat(traj["logp"])
    A = flat(adv); R = flat(ret)
    A = (A - A.mean()) / (A.std() + 1e-8)

    def epoch(carry, ekey):
        lp, cp, ostate = carry
        perm = jax.random.permutation(ekey, N)

        def mb(carry, mbi):
            lp, cp, ostate = carry
            sl = jax.lax.dynamic_slice_in_dim(perm, mbi * mbsize, mbsize)
            o, g, a = obs[sl], gobs[sl], act[sl]
            ol, Ai, Ri = old_logp[sl], A[sl], R[sl]

            def loss(params):
                lp_, cp_ = params
                logits = actor.apply(lp_, o)
                nlp = action_logprob(logits, a)
                ratio = jnp.exp(nlp - ol)
                ae = Ai[:, None]
                pg = -jnp.minimum(ratio * ae,
                                  jnp.clip(ratio, 1 - CLIP, 1 + CLIP) * ae).mean()
                v = critic.apply(cp_, g)
                vl = ((v - Ri) ** 2).mean()
                ent = entropy(logits).mean()
                return pg + VF * vl - ENT * ent
            grads = jax.grad(loss)((lp, cp))
            upd, ostate = OPT.update(grads, ostate)
            lp, cp = optax.apply_updates((lp, cp), upd)
            return (lp, cp, ostate), None
        (lp, cp, ostate), _ = jax.lax.scan(mb, (lp, cp, ostate), jnp.arange(N_MB))
        return (lp, cp, ostate), None

    keys = jax.random.split(key, EPOCHS)
    (lp, cp, ostate), _ = jax.lax.scan(epoch, (lp, cp, ostate), keys)
    return lp, cp, ostate


def main(updates, use_bc, episode_len, opp="selfplay"):
    reset_env, env_step = E.make_env(B, episode_len=episode_len)
    rollout = make_rollout(env_step, opp_static=(opp == "static"))
    key = jax.random.PRNGKey(0)
    state, obs = reset_env()
    lp = actor.init(key, obs[0][:, J.HOME])
    cp = critic.init(key, obs[1][:, J.HOME])
    if use_bc:
        with open(_R / "rl/checkpoints/bc_actor.pkl", "rb") as f:
            bc = pickle.load(f)
        lp = jax.tree_util.tree_map(lambda a, b: jnp.asarray(b), lp, bc)
        print("warm-start do BC carregado", flush=True)
    pool = [jax.tree_util.tree_map(jnp.array, lp)]
    ostate = OPT.init((lp, cp))

    t0 = time.time()
    for u in range(updates):
        key, kr, ku = jax.random.split(key, 3)
        opp = pool[np.random.randint(len(pool))]
        state, obs, kr, traj, last_val = rollout(lp, cp, opp, state, obs, kr)
        adv, ret = gae(traj["rew"], traj["val"], traj["done"], last_val)
        lp, cp, ostate = update(lp, cp, ostate, traj, adv, ret, ku)
        if (u + 1) % SNAP_EVERY == 0:
            pool.append(jax.tree_util.tree_map(jnp.array, lp))
            pool = pool[-6:]
        if u % 10 == 0 or u == updates - 1:
            print(f"update {u:4d} | reward/passo {float(traj['rew'].mean()):+.4f} "
                  f"| pool {len(pool)} | {time.time()-t0:.0f}s", flush=True)

    out = _R / "rl/checkpoints/policy.pkl"
    with open(out, "wb") as f:
        pickle.dump(jax.tree_util.tree_map(np.asarray, lp), f)
    print(f"política salva em {out}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=200)
    ap.add_argument("--bc", action="store_true")
    ap.add_argument("--episode-len", type=int, default=2000)
    ap.add_argument("--opp", default="selfplay", choices=["selfplay", "static"])
    a = ap.parse_args()
    main(a.updates, a.bc, a.episode_len, a.opp)
