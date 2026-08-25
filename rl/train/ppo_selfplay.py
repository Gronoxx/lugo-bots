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
from obs import get_obs as _get_obs
from opponents import chase_action, formation_action
from networks import Actor, Critic, sample_action, action_logprob, entropy

B, T = 512, 128
EPOCHS, N_MB = 4, 8
GAMMA, LAM = 0.99, 0.95
CLIP, VF, ENT, LR = 0.2, 0.5, 0.005, 3e-4
SNAP_EVERY = 25

actor = Actor(nvec=tuple(E.META["action_nvec"]))
critic = Critic()
OPT = None   # construído em main() p/ permitir annealing de LR e batch variável


def _act(params, aobs_side, key):
    return sample_action(actor.apply(params, aobs_side), key)


def make_rollout(env_step, opp_kind="self"):
    """opp_kind: 'static' (AWAY parado), 'chase'/'formation' (heurísticos JAX) ou
    'self' (AWAY = política do pool via `opp`). Aprendiz=HOME sempre."""
    @jax.jit
    def rollout(lp, cp, opp, state, obs, key):
        def stepf(carry, _):
            state, obs, key = carry
            aobs, gobs = obs
            key, kH, kA = jax.random.split(key, 3)
            aH, lpH = _act(lp, aobs[:, J.HOME], kH)
            if opp_kind == "static":
                aA = jnp.zeros_like(aH)
            elif opp_kind == "chase":
                aA = chase_action(state)[:, J.AWAY]
            elif opp_kind == "formation":
                aA = formation_action(state)[:, J.AWAY]
            else:
                aA = _act(opp, aobs[:, J.AWAY], kA)[0]
            val = critic.apply(cp, gobs[:, J.HOME])            # (B,11)
            action = jnp.stack([aH, aA], axis=1)
            s2, obs2, reward, done, _ = env_step(state, action)
            poss = (s2.holder_side == J.HOME).mean()
            terr = (s2.ball_pos[:, 0] > J.MAX_X / 2).mean()
            goals = ((s2.score[:, J.HOME] - state.score[:, J.HOME]) > 0).mean()  # gol REAL (Δplacar)
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


def main(updates, use_bc, episode_len, opp, curr_frac=0.4,
         batch=512, ent=0.005, lr=3e-4, lr_anneal=False, ckpt_every=0, drill_frac=0.0,
         boot_pkl=None, p_chase=0.34, p_boot=0.0, init_pkl=None, p_form=0.0):
    global B, ENT, LR, OPT
    B, ENT, LR = batch, ent, lr
    if lr_anneal:
        sched = optax.linear_schedule(lr, 0.0, updates * EPOCHS * N_MB)
        OPT = optax.chain(optax.clip_by_global_norm(0.5), optax.adam(sched))
    else:
        OPT = optax.chain(optax.clip_by_global_norm(0.5), optax.adam(lr))
    print(f"config: B={B} T={T} updates={updates} ent={ENT} lr={LR} anneal={lr_anneal} "
          f"opp={opp} ep_len={episode_len} ckpt={ckpt_every} drill={drill_frac} "
          f"p_chase={p_chase} p_boot={p_boot} boot={boot_pkl is not None}", flush=True)
    reset_env, env_step = E.make_env(B, episode_len=episode_len)
    roll_static = make_rollout(env_step, "static")
    roll_self = make_rollout(env_step, "self")
    roll_chase = make_rollout(env_step, "chase")
    roll_form = make_rollout(env_step, "formation")
    key = jax.random.PRNGKey(0)
    state, obs = reset_env()
    lp = actor.init(key, obs[0][:, J.HOME])
    cp = critic.init(key, obs[1][:, J.HOME])                  # crítico na obs GLOBAL
    if init_pkl is not None:                                  # warm-start
        with open(init_pkl, "rb") as f:
            obj = pickle.load(f)
        if isinstance(obj, tuple) and len(obj) == 2:          # (ator, crítico)
            lp = jax.tree_util.tree_map(jnp.asarray, obj[0])
            cp = jax.tree_util.tree_map(jnp.asarray, obj[1])
            print(f"warm-start (ator+crítico) de {init_pkl}", flush=True)
        else:                                                 # só ator (crítico fresco)
            lp = jax.tree_util.tree_map(jnp.asarray, obj)
            print(f"warm-start (só ator; crítico fresco) de {init_pkl}", flush=True)
    elif use_bc:
        with open(_R / "rl/checkpoints/bc_actor.pkl", "rb") as f:
            bc = pickle.load(f)
        lp = jax.tree_util.tree_map(lambda a, b: jnp.asarray(b), lp, bc)
        print("warm-start do BC carregado", flush=True)
    pool = [jax.tree_util.tree_map(jnp.array, lp)]
    boot_params = None
    if boot_pkl is not None:
        with open(boot_pkl, "rb") as f:
            boot_params = jax.tree_util.tree_map(jnp.asarray, pickle.load(f))
        print(f"oponente booting carregado de {boot_pkl}", flush=True)
    ostate = OPT.init((lp, cp))
    logf = open(_R / "rl/checkpoints/train_log.csv", "w", newline="")
    logw = csv.writer(logf); logw.writerow(["update", "reward", "entropy", "poss", "terr", "goals", "phase"])

    n_drill = int(updates * drill_frac)                       # start-state de finalização
    if opp == "curriculum":
        n_static_end = n_drill + int(updates * curr_frac)
    elif opp == "static":
        n_static_end = updates
    else:                                                     # selfplay puro
        n_static_end = n_drill
    t0 = time.time()
    for u in range(updates):
        phase = "drill" if u < n_drill else ("static" if u < n_static_end else "selfplay")
        key, kr, ku, kd = jax.random.split(key, 4)
        if phase == "drill":
            state = J.finishing_state(B, kd)                  # cada update: B finalizações diversas
            obs = _get_obs(state)
            state, obs, kr, traj, last_val = roll_static(lp, cp, lp, state, obs, kr)
        elif phase == "static":
            state, obs, kr, traj, last_val = roll_static(lp, cp, lp, state, obs, kr)
        else:                                                 # self-play com pool DIVERSO
            r = np.random.rand()
            if r < p_chase:                                   # chase (enxame agressivo)
                state, obs, kr, traj, last_val = roll_chase(lp, cp, lp, state, obs, kr)
            elif r < p_chase + p_form:                        # formation (defesa organizada FORTE)
                state, obs, kr, traj, last_val = roll_form(lp, cp, lp, state, obs, kr)
            elif boot_params is not None and r < p_chase + p_form + p_boot:  # booting
                state, obs, kr, traj, last_val = roll_self(lp, cp, boot_params, state, obs, kr)
            else:                                             # snapshot do pool (fictitious self-play)
                oi = pool[np.random.randint(len(pool))]
                state, obs, kr, traj, last_val = roll_self(lp, cp, oi, state, obs, kr)
        adv, ret = gae(traj["rew"], traj["val"], traj["done"], last_val)
        lp, cp, ostate = update(lp, cp, ostate, traj, adv, ret, ku)
        if (u + 1) % SNAP_EVERY == 0 and phase == "selfplay":
            pool.append(jax.tree_util.tree_map(jnp.array, lp)); pool = pool[-6:]
        if ckpt_every and (u + 1) % ckpt_every == 0:
            with open(_R / f"rl/checkpoints/policy_u{u+1}.pkl", "wb") as f:
                pickle.dump(jax.tree_util.tree_map(np.asarray, lp), f)
            print(f"  checkpoint salvo: policy_u{u+1}.pkl", flush=True)
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
    with open(_R / "rl/checkpoints/warmstart.pkl", "wb") as f:   # ator+crítico p/ continuar
        pickle.dump((jax.tree_util.tree_map(np.asarray, lp),
                     jax.tree_util.tree_map(np.asarray, cp)), f)
    print("política salva em rl/checkpoints/policy.pkl (+ warmstart.pkl)", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--updates", type=int, default=400)
    ap.add_argument("--bc", action="store_true")
    ap.add_argument("--episode-len", type=int, default=2000)
    ap.add_argument("--opp", default="curriculum", choices=["static", "selfplay", "curriculum"])
    ap.add_argument("--curr-frac", type=float, default=0.4)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--ent", type=float, default=0.005)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--lr-anneal", action="store_true")
    ap.add_argument("--ckpt-every", type=int, default=0)
    ap.add_argument("--drill-frac", type=float, default=0.0)
    ap.add_argument("--boot-pkl", default=None)
    ap.add_argument("--p-chase", type=float, default=0.34)
    ap.add_argument("--p-boot", type=float, default=0.0)
    ap.add_argument("--p-form", type=float, default=0.0)      # oponente formation (forte)
    ap.add_argument("--init-pkl", default=None)               # warmstart.pkl (ator+crítico)
    a = ap.parse_args()
    main(a.updates, a.bc, a.episode_len, a.opp, curr_frac=a.curr_frac,
         batch=a.batch, ent=a.ent, lr=a.lr, lr_anneal=a.lr_anneal, ckpt_every=a.ckpt_every,
         drill_frac=a.drill_frac, boot_pkl=a.boot_pkl, p_chase=a.p_chase, p_boot=a.p_boot,
         init_pkl=a.init_pkl, p_form=a.p_form)
