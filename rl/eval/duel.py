"""
Confronta duas políticas no env JAX (gols acumulados por evento). Cada lado pode
ser: um .pkl de rede, ou 'static'/'chase'/'formation'/'null'.

  ../.venv-rl/bin/python rl/eval/duel.py <home> <away> [n] [turns]
  ex.: duel.py scratch/policy_v8.pkl formation 128 6000
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
from networks import Actor, sample_action
from opponents import chase_action, formation_action

_actor = Actor(nvec=tuple(E.META["action_nvec"]))
_KINDS = ("static", "chase", "formation", "null")


def _load(spec):
    if spec in _KINDS:
        return spec, None
    return "net", jax.tree_util.tree_map(jnp.asarray, pickle.load(open(spec, "rb")))


def _side_action(kind, params, state, aobs, side, key):
    if kind == "net":
        return sample_action(_actor.apply(params, aobs[:, side]), key)[0]
    if kind == "static" or kind == "null":
        return jnp.zeros((aobs.shape[0], 11, 4), jnp.int32)
    if kind == "chase":
        return chase_action(state)[:, side]
    return formation_action(state)[:, side]


def duel(home, away, n, turns):
    hk, hp = _load(home)
    ak, ap = _load(away)
    reset, step = E.make_env(n, episode_len=turns)
    state, obs = reset()

    @jax.jit
    def run(state, obs, key):
        def body(carry, _):
            state, obs, key = carry
            aobs, _g = obs
            key, kh, ka = jax.random.split(key, 3)
            aH = _side_action(hk, hp, state, aobs, J.HOME, kh)
            aA = _side_action(ak, ap, state, aobs, J.AWAY, ka)
            s2, obs2, _, _, _ = step(state, jnp.stack([aH, aA], 1))
            gh = ((s2.score[:, J.HOME] - state.score[:, J.HOME]) > 0).astype(jnp.float32)
            ga = ((s2.score[:, J.AWAY] - state.score[:, J.AWAY]) > 0).astype(jnp.float32)
            poss = (s2.holder_side == J.HOME).astype(jnp.float32)
            return (s2, obs2, key), (gh, ga, poss)
        (state, obs, key), (gh, ga, poss) = jax.lax.scan(body, (state, obs, key), None, length=turns)
        return gh.sum(0), ga.sum(0), poss.mean()
    gh, ga, poss = run(state, obs, jax.random.PRNGKey(0))
    gh, ga = np.asarray(gh), np.asarray(ga)
    diff = gh - ga
    print(f"{home} {gh.mean():.2f} x {ga.mean():.2f} {away} | saldo {diff.mean():+.2f} "
          f"| posse(H) {float(poss)*100:.0f}% | vit {float((diff>0).mean())*100:.0f}% "
          f"emp {float((diff==0).mean())*100:.0f}% (n={n},{turns}t)")
    return diff.mean()


if __name__ == "__main__":
    duel(sys.argv[1], sys.argv[2],
         int(sys.argv[3]) if len(sys.argv) > 3 else 128,
         int(sys.argv[4]) if len(sys.argv) > 4 else 6000)
