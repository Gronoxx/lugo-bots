"""
Avalia uma política JAX no env do Lugo, em jogos COMPLETOS, reportando saldo de
gols e taxa de vitória. Oponente = outra política (pkl) ou 'chase' (baseline).

  ../.venv-rl/bin/python rl/train/evaluate.py policy.pkl [opp.pkl|chase] [n_games] [episode_len]
"""
import pickle
import sys
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in (_R / "rl/envs", _R / "rl/jax", _R / "rl/train"):
    sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp
import numpy as np

import lugo_env as E
import step as J
from networks import Actor

actor = Actor(nvec=tuple(E.META["action_nvec"]))


def chase_action(state):
    """Baseline JAX: cada jogador vai à bola; o dono chuta ao gol. Formato do env
    (B,2,11,4) [move_dir,kick_dir,catch,jump] no referencial canônico."""
    import actions as A
    to = state.ball_pos[:, None, None, :] - state.pos          # (B,2,11,2)
    # canoniza x por lado (mesma convenção da obs): AWAY espelha x
    sign = jnp.array([1.0, -1.0]).reshape(1, 2, 1)
    ang = jnp.arctan2(to[..., 1], to[..., 0] * sign) % (2 * jnp.pi)
    md = (jnp.round(ang / (2 * jnp.pi / A.N_DIR)).astype(jnp.int32) % A.N_DIR) + 1
    kd = jnp.zeros_like(md)                                     # chase não chuta
    catch = jnp.ones_like(md)
    jump = jnp.zeros_like(md)
    return jnp.stack([md, kd, catch, jump], -1)


def _greedy(params, aobs_side):
    logits = actor.apply(params, aobs_side)
    return jnp.stack([lg.argmax(-1) for lg in logits], -1)      # (B,11,4)


def evaluate(home, away, n_games, episode_len):
    reset, step = E.make_env(n_games, episode_len=episode_len)
    state, obs = reset()

    @jax.jit
    def run(state, obs):
        def body(carry, _):
            state, obs = carry
            aobs, _ = obs
            aH = _greedy(home, aobs[:, J.HOME])
            if away == "chase":
                act = chase_action(state)
                aA = act[:, J.AWAY]
            else:
                aA = _greedy(away, aobs[:, J.AWAY])
            action = jnp.stack([aH, aA], 1)
            state, obs, _, _, _ = step(state, action)
            return (state, obs), None
        (state, obs), _ = jax.lax.scan(body, (state, obs), None, length=episode_len)
        return state
    final = run(state, obs)
    sc = np.asarray(final.score)                               # (n_games,2)
    diff = sc[:, J.HOME] - sc[:, J.AWAY]
    wins = (diff > 0).mean(); draws = (diff == 0).mean()
    print(f"HOME {sc[:,0].mean():.2f} x {sc[:,1].mean():.2f} AWAY | saldo {diff.mean():+.2f} "
          f"| vitórias {wins*100:.0f}% empates {draws*100:.0f}% (n={n_games}, {episode_len}t)")
    return diff.mean()


if __name__ == "__main__":
    hp = pickle.load(open(sys.argv[1], "rb"))
    aw = sys.argv[2] if len(sys.argv) > 2 else "chase"
    away = "chase" if aw == "chase" else pickle.load(open(aw, "rb"))
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 64
    L = int(sys.argv[4]) if len(sys.argv) > 4 else 6000
    evaluate(hp, away, n, L)
