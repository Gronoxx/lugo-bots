"""
Behavior cloning: treina o Actor para imitar o v9 (obs -> ação do v9).
Roda no .venv-rl (JAX). Salva os pesos como warm-start do PPO.

  ../.venv-rl/bin/python rl/train/bc_train.py [bc_data.npz] [epochs]
"""
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

import step as J
from obs import get_obs
from networks import Actor

BS = 4096


def _state_from(d, idx):
    """Monta um J.State (batch = idx) a partir dos arrays numpy carregados."""
    g = lambda k: jnp.asarray(d[k][idx])
    return J.State(
        turn=jnp.zeros(idx.shape[0], jnp.int32),
        pos=g("pos").astype(jnp.float32), vel=g("vel").astype(jnp.float32),
        ball_pos=g("ball_pos").astype(jnp.float32), ball_vel=g("ball_vel").astype(jnp.float32),
        holder_side=g("holder_side").astype(jnp.int32), holder_idx=g("holder_idx").astype(jnp.int32),
        score=g("score").astype(jnp.int32), shot_clock_side=g("shot_clock_side").astype(jnp.int32),
        shot_clock=g("shot_clock").astype(jnp.int32), jump_left=g("jump_left").astype(jnp.int32),
        goal_zone_turns=g("goal_zone_turns").astype(jnp.int32))


def main(path, epochs):
    d = {k: np.asarray(v) for k, v in np.load(path).items()}
    T = d["action"].shape[0]
    actions = d["action"]                                    # (T,2,11,4)
    print(f"dados: {T} turnos, {T*22} amostras/agente")

    actor = Actor()
    key = jax.random.PRNGKey(0)
    s0 = _state_from(d, np.arange(2))
    aobs0, _ = get_obs(s0)
    params = actor.init(key, aobs0)
    opt = optax.adam(3e-4)
    ostate = opt.init(params)

    def loss_fn(params, state, act):
        logits = actor.apply(params, get_obs(state)[0])       # lista (B,2,11,ni)
        loss = 0.0
        acc = 0.0
        for j, lg in enumerate(logits):
            loss = loss + optax.softmax_cross_entropy_with_integer_labels(
                lg, act[..., j]).mean()
            acc = acc + (lg.argmax(-1) == act[..., j]).mean()
        return loss, acc / len(logits)

    @jax.jit
    def train_step(params, ostate, state, act):
        (loss, acc), g = jax.value_and_grad(loss_fn, has_aux=True)(params, state, act)
        upd, ostate = opt.update(g, ostate)
        return optax.apply_updates(params, upd), ostate, loss, acc

    t0 = time.time()
    for ep in range(epochs):
        perm = np.random.permutation(T)
        losses, accs = [], []
        for i in range(0, T - BS, BS):
            idx = perm[i:i + BS]
            state = _state_from(d, idx)
            act = jnp.asarray(actions[idx])
            params, ostate, loss, acc = train_step(params, ostate, state, act)
            losses.append(float(loss)); accs.append(float(acc))
        print(f"epoch {ep+1}/{epochs} | loss {np.mean(losses):.3f} | "
              f"acc média das 4 cabeças {np.mean(accs):.3f} | {time.time()-t0:.0f}s", flush=True)

    out = _R / "rl/checkpoints/bc_actor.pkl"
    with open(out, "wb") as f:
        pickle.dump(jax.tree_util.tree_map(np.asarray, params), f)
    print(f"salvo warm-start em {out}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else str(_R / "rl/checkpoints/bc_data.npz")
    epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(path, epochs)
