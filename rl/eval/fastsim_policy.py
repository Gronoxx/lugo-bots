"""
Adaptador da política RL (JAX) para o formato do fastsim ESCALAR: permite jogar
a rede treinada CONTRA o my_bot (v9) no simulador em processo (sem docker/gRPC),
reusando a MESMA obs (obs.py) e decodificação de ação da rede.

  policy(state, side) -> lista de 11 dicts   (formato consumido por fastsim.step)

fastsim.State e J.State (JAX) são ports do MESMO sim, então a conversão é direta.
Roda bem na CPU (JAX_PLATFORMS=cpu) — inferência da rede é minúscula.
"""
import math
import pickle
import sys
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in (_R / "rl/envs", _R / "rl/jax", _R / "rl/train", _R / "sim"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp
import numpy as np

import step as J
from obs import get_obs
from networks import Actor, sample_action
from opponents import formation_action

import fastsim as fs

_actor = Actor(nvec=(17, 17, 2, 2))
N_DIR = 16
_UNIT = [(math.cos(2 * math.pi * k / N_DIR), math.sin(2 * math.pi * k / N_DIR))
         for k in range(N_DIR)]


def fastsim_to_state(s):
    """fastsim.State -> J.State (batch 1)."""
    if s.holder is None:
        hs, hi = -1, 0
    else:
        hs, hi = int(s.holder[0]), int(s.holder[1])
    return J.State(
        turn=jnp.zeros(1, jnp.int32),
        pos=jnp.asarray(s.pos[None], jnp.float32),
        vel=jnp.asarray(s.vel[None], jnp.float32),
        ball_pos=jnp.asarray(s.ball_pos[None], jnp.float32),
        ball_vel=jnp.asarray(s.ball_vel[None], jnp.float32),
        holder_side=jnp.asarray([hs], jnp.int32), holder_idx=jnp.asarray([hi], jnp.int32),
        score=jnp.asarray([list(s.score)], jnp.int32),
        shot_clock_side=jnp.asarray([s.shot_clock_side], jnp.int32),
        shot_clock=jnp.asarray([s.shot_clock], jnp.int32),
        jump_left=jnp.asarray(s.jump_left[None], jnp.int32),
        goal_zone_turns=jnp.asarray([s.turns_ball_in_goal_zone], jnp.int32))


@jax.jit
def _sample_side(params, aobs_side, key):
    a, _ = sample_action(_actor.apply(params, aobs_side), key)  # (1,11,4)
    return a


@jax.jit
def _greedy_side(params, aobs_side):
    logits = _actor.apply(params, aobs_side)
    return jnp.stack([lg.argmax(-1) for lg in logits], -1)      # (1,11,4)


def _decode_to_orders(a, side):
    """(11,4) ação canônica -> lista de 11 dicts do fastsim (des-canoniza x do AWAY)."""
    sign = 1.0 if side == fs.HOME else -1.0
    orders = []
    for i in range(11):
        md, kd, catch, jump = int(a[i, 0]), int(a[i, 1]), int(a[i, 2]), int(a[i, 3])
        d = {}
        if md > 0:
            ux, uy = _UNIT[md - 1]
            d["move"] = (ux * sign * J.PLAYER_MAX_SPEED, uy * J.PLAYER_MAX_SPEED)
        if kd > 0:
            ux, uy = _UNIT[kd - 1]
            d["kick"] = (ux * sign * J.BALL_MAX_SPEED, uy * J.BALL_MAX_SPEED)
        if catch:
            d["catch"] = True
        if jump and i == 0:
            ux, uy = (_UNIT[md - 1] if md > 0 else (0.0, 1.0))
            d["jump"] = (ux * sign * J.GOALKEEPER_JUMP_SPEED, uy * J.GOALKEEPER_JUMP_SPEED)
        orders.append(d or None)
    return orders


def make_formation_fastsim_policy():
    """O oponente heurístico 'formation' (JAX) como política do fastsim — para medir
    seu teto vs o v9."""
    def policy(state, side):
        st = fastsim_to_state(state)
        a = np.asarray(formation_action(st))[0, side]         # (11,4)
        return _decode_to_orders(a, side)
    return policy


def make_net_fastsim_policy(params_path=None, params=None, sample=True, seed=0):
    if params is None:
        with open(params_path, "rb") as f:
            params = jax.tree_util.tree_map(jnp.asarray, pickle.load(f))
    key = [jax.random.PRNGKey(seed)]

    def policy(state, side):
        st = fastsim_to_state(state)
        aobs, _ = get_obs(st)                                   # (1,2,11,109)
        if sample:
            key[0], k = jax.random.split(key[0])
            a = np.asarray(_sample_side(params, aobs[:, side], k))[0]  # (11,4)
        else:
            a = np.asarray(_greedy_side(params, aobs[:, side]))[0]
        sign = 1.0 if side == fs.HOME else -1.0                 # des-canoniza x do AWAY
        orders = []
        for i in range(11):
            md, kd, catch, jump = int(a[i, 0]), int(a[i, 1]), int(a[i, 2]), int(a[i, 3])
            d = {}
            if md > 0:
                ux, uy = _UNIT[md - 1]
                d["move"] = (ux * sign * J.PLAYER_MAX_SPEED, uy * J.PLAYER_MAX_SPEED)
            if kd > 0:
                ux, uy = _UNIT[kd - 1]
                d["kick"] = (ux * sign * J.BALL_MAX_SPEED, uy * J.BALL_MAX_SPEED)
            if catch:
                d["catch"] = True
            if jump and i == 0:
                ux, uy = (_UNIT[md - 1] if md > 0 else (0.0, 1.0))
                d["jump"] = (ux * sign * J.GOALKEEPER_JUMP_SPEED, uy * J.GOALKEEPER_JUMP_SPEED)
            orders.append(d or None)
        return orders

    return policy
