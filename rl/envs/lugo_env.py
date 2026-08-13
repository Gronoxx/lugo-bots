"""
Env multiagente vetorizado do Lugo sobre o sim JAX — interface de RL.

reset(batch) -> (state, (agent_obs, global_obs))
step(state, action) -> (state', (agent_obs, global_obs), reward, done, info)

action: (B, 2, 11, 4) int [move_dir, kick_dir, catch, jump] (ver actions.py).
reward: (B, 2, 11).  done: (B,).  Auto-reset por partida ao fim do episódio.

Controla os DOIS times (self-play / liga): o loop de treino decide quais dos 22
agentes são o aprendiz e quais o oponente. jit-able (batch/episode_len estáticos).
"""
import sys
from functools import partial
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in (_HERE.parents[1] / "jax", _HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp

import step as J
from actions import decode, action_dims  # noqa: E402
from obs import get_obs, OBS_DIM, GLOBAL_DIM  # noqa: E402
from rewards import compute_reward  # noqa: E402


def reset(batch):
    s = J.initial_state(batch)
    return s, get_obs(s)


@partial(jax.jit, static_argnums=(2, 3))
def step(state, action, episode_len=6000, gamma=0.99):
    move, kick, do_catch, do_jump = decode(action)
    s2 = J.step(state, move, kick, do_catch, do_jump)
    reward = compute_reward(state, s2, gamma)
    done = s2.turn >= episode_len                          # (B,)
    B = state.pos.shape[0]
    fresh = J.initial_state(B)
    s_next = jax.tree_util.tree_map(
        lambda a, b: jnp.where(done.reshape((B,) + (1,) * (a.ndim - 1)), a, b),
        fresh, s2)
    info = {"score": s2.score, "done": done}
    return s_next, get_obs(s_next), reward, done, info


def make_env(batch, episode_len=6000, gamma=0.99):
    """Fecha batch/episode_len/gamma; retorna (reset_fn, step_fn) prontos."""
    def _reset():
        return reset(batch)

    def _step(state, action):
        return step(state, action, episode_len, gamma)

    return _reset, _step


META = dict(action_nvec=action_dims(), obs_dim=OBS_DIM, global_dim=GLOBAL_DIM,
           n_agents_per_side=11)
