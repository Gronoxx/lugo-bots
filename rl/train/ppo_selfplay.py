"""
PPO self-play (MAPPO — CTDE com compartilhamento de parâmetros) para o Lugo/JAX.

- Ator compartilhado sobre a obs egocêntrica dos 11 jogadores.
- Crítico CENTRAL sobre a obs GLOBAL do time -> valor POR-AGENTE (11).
- Reward POR-AGENTE (time compartilhado + near-ball individual, ver rewards.py).
- GAE e vantagem por-agente; ratio por-agente; clip PPO; minibatches.
- Aprendiz=HOME. Oponente: estático (bootstrap), self-play (pool frozen), ou
  CURRÍCULO (estático nos primeiros updates -> self-play). Snapshots periódicos.
- Log CSV: reward, entropia, POSSE%, TERRITÓRIO% por update (verificar, não presumir).

  ../.venv-rl/bin/python rl/train/ppo_selfplay.py --updates N [--bc] [--opp curriculum]
"""
import argparse
import csv
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
EPOCHS, N_MB = 4, 8
GAMMA, LAM = 0.99, 0.95
CLIP, VF, ENT, LR = 0.2, 0.5, 0.005, 3e-4
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
            aA = jnp.zeros_like(aH) if opp_static else _act(opp, aobs[:, J.AWAY], kA)[0]
            val = critic.apply(cp, gobs[:, J.HOME])            # (B,11)
            action = jnp.stack([aH, aA], axis=1)
            s2, obs2, reward, done, _ = env_step(state, action)
            poss = (s2.holder_side == J.HOME).mean()
            terr = (s2.ball_pos[:, 0] > J.MAX_X / 2).mean()
            goals = (reward[:, J.HOME, 0] > 0.7).mean()        # ~evento de gol (rew salta ~+1)
            tr = dict(obs=aobs[:, J.HOME], gobs=gobs[:, J.HOME], act=aH, logp=lpH,
                      val=val, rew=reward[:, J.HOME], done=done, poss=poss, terr=terr,
                      goals=goals)
            return (s2, obs2, key), tr
        (state, obs, key), traj = jax.lax.scan(stepf, (state, obs, key), None, length=T)
        last_val = critic.apply(cp, obs[1][:, J.HOME])         # (B,11)
        return state, obs, key, traj, last_val
    return rollout


def gae(rew, val, done, last_val):
    """rew,val: (T,B,11); done: (T,B). Vantagem por-agente."""
    d = done[..., None]
    def f(carry, x):
        adv, nv = carry
        r, v, dd = x
        delta = r + GAMMA * nv * (1 - dd) - v
        adv = delta + GAMMA * LAM * (1 - dd) * adv
        return (adv, v), adv
    _, adv = jax.lax.scan(f, (jnp.zeros_like(last_val), last_val),
                          (rew, val, d), reverse=True)
    return adv, adv + val


@jax.jit
def update(lp, cp, ostate, traj, adv, ret, key):
    M = T * B                                                 # timesteps de time
    mbsize = M // N_MB
    fl = lambda x: x.reshape((M,) + x.shape[2:])
    obs, gobs, act = fl(traj["obs"]), fl(traj["gobs"]), fl(traj["act"])
    old_logp = fl(traj["logp"]); A = fl(adv); R = fl(ret)     # (M,11) exceto gobs (M,96)
    A = (A - A.mean()) / (A.std() + 1e-8)

    def epoch(carry, ekey):
        lp, cp, ostate = carry
        perm = jax.random.permutation(ekey, M)
        def mb(carry, mbi):
            lp, cp, ostate = carry
            sl = jax.lax.dynamic_slice_in_dim(perm, mbi * mbsize, mbsize)
            o, g, a, ol, Ai, Ri = obs[sl], gobs[sl], act[sl], old_logp[sl], A[sl], R[sl]
            def loss(params):
                lp_, cp_ = params
                logits = actor.apply(lp_, o)                  # (mb,11,ni)
                nlp = action_logprob(logits, a)               # (mb,11)
                ratio = jnp.exp(nlp - ol)
                pg = -jnp.minimum(ratio * Ai,
                                  jnp.clip(ratio, 1 - CLIP, 1 + CLIP) * Ai).mean()
                v = critic.apply(cp_, g)                      # (mb,11)
                vl = ((v - Ri) ** 2).mean()
                return pg + VF * vl - ENT * entropy(logits).mean()
            grads = jax.grad(loss)((lp, cp))
            upd, ostate = OPT.update(grads, ostate)
            lp, cp = optax.apply_updates((lp, cp), upd)
            return (lp, cp, ostate), None
        (lp, cp, ostate), _ = jax.lax.scan(mb, (lp, cp, ostate), jnp.arange(N_MB))
        return (lp, cp, ostate), None
    keys = jax.random.split(key, EPOCHS)
    (lp, cp, ostate), _ = jax.lax.scan(epoch, (lp, cp, ostate), keys)
    return lp, cp, ostate


def main(updates, use_bc, episode_len, opp, curr_frac=0.4):
    reset_env, env_step = E.make_env(B, episode_len=episode_len)
    roll_static = make_rollout(env_step, opp_static=True)
    roll_self = make_rollout(env_step, opp_static=False)
    key = jax.random.PRNGKey(0)
    state, obs = reset_env()
    lp = actor.init(key, obs[0][:, J.HOME])
    cp = critic.init(key, obs[1][:, J.HOME])                  # crítico na obs GLOBAL
    if use_bc:
        with open(_R / "rl/checkpoints/bc_actor.pkl", "rb") as f:
            bc = pickle.load(f)
        lp = jax.tree_util.tree_map(lambda a, b: jnp.asarray(b), lp, bc)
        print("warm-start do BC carregado", flush=True)
    pool = [jax.tree_util.tree_map(jnp.array, lp)]
    ostate = OPT.init((lp, cp))
    logf = open(_R / "rl/checkpoints/train_log.csv", "w", newline="")
    logw = csv.writer(logf); logw.writerow(["update", "reward", "entropy", "poss", "terr", "goals", "phase"])

    n_static = int(updates * curr_frac) if opp == "curriculum" else (updates if opp == "static" else 0)
    t0 = time.time()
    for u in range(updates):
        phase = "static" if u < n_static else "selfplay"
        key, kr, ku = jax.random.split(key, 3)
        if phase == "static":
            state, obs, kr, traj, last_val = roll_static(lp, cp, lp, state, obs, kr)
        else:
            oi = pool[np.random.randint(len(pool))]
            state, obs, kr, traj, last_val = roll_self(lp, cp, oi, state, obs, kr)
        adv, ret = gae(traj["rew"], traj["val"], traj["done"], last_val)
        lp, cp, ostate = update(lp, cp, ostate, traj, adv, ret, ku)
        if (u + 1) % SNAP_EVERY == 0 and phase == "selfplay":
            pool.append(jax.tree_util.tree_map(jnp.array, lp)); pool = pool[-6:]
        if u % 10 == 0 or u == updates - 1:
            ent = float(entropy(actor.apply(lp, traj["obs"][0, :64])).mean())
            rew = float(traj["rew"].mean()); poss = float(traj["poss"].mean())
            terr = float(traj["terr"].mean()); gls = float(traj["goals"].mean()) * T
            logw.writerow([u, rew, ent, poss, terr, gls, phase]); logf.flush()
            print(f"u{u:4d}[{phase[:4]}] reward {rew:+.4f} ent {ent:.3f} posse {poss*100:.0f}% "
                  f"terr {terr*100:.0f}% gols/ep~{gls:.2f} {time.time()-t0:.0f}s", flush=True)

    logf.close()
    with open(_R / "rl/checkpoints/policy.pkl", "wb") as f:
        pickle.dump(jax.tree_util.tree_map(np.asarray, lp), f)
    print("política salva em rl/checkpoints/policy.pkl", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=400)
    ap.add_argument("--bc", action="store_true")
    ap.add_argument("--episode-len", type=int, default=2000)
    ap.add_argument("--opp", default="curriculum", choices=["static", "selfplay", "curriculum"])
    a = ap.parse_args()
    main(a.updates, a.bc, a.episode_len, a.opp)
