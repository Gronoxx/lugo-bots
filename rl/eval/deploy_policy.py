"""
Adaptador de deploy (Etapa 5): transforma a política JAX treinada num bot que
joga no SERVIDOR REAL (via lugo4py). Inverte a ponte da Etapa 1.

policy(side, number, inspector) -> [lugo4py.Order]   (assinatura do remote_match)

Pipeline por turno: inspector.get_snapshot() -> State (batch 1) -> obs (obs.py)
-> rede (argmax) -> ação discreta -> Order (direção des-canonizada + speed).

Roda no .venv-rl (JAX + lugo4py + grpc). Carrega rl/checkpoints/policy.pkl.
"""
import math
import pickle
import sys
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in (_R / "rl/envs", _R / "rl/jax", _R / "rl/train"):
    sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp
import numpy as np

import lugo4py
from lugo4py.protos import server_pb2, physics_pb2

import step as J
from obs import get_obs
from networks import Actor
import actions as A

_actor = Actor(nvec=tuple((17, 17, 2, 2)))
_UNIT = [(math.cos(2 * math.pi * k / A.N_DIR), math.sin(2 * math.pi * k / A.N_DIR))
         for k in range(A.N_DIR)]


def _vel_cart(v):
    dx, dy, sp = v.direction.x, v.direction.y, v.speed
    n = math.hypot(dx, dy)
    return (0.0, 0.0) if n == 0 or sp == 0 else (dx / n * sp, dy / n * sp)


def snapshot_to_state(snap):
    """GameSnapshot -> J.State (batch 1)."""
    pos = np.zeros((1, 2, 11, 2), np.float32)
    vel = np.zeros((1, 2, 11, 2), np.float32)
    for side, team in ((J.HOME, snap.home_team), (J.AWAY, snap.away_team)):
        for p in team.players:
            i = p.number - 1
            if 0 <= i < 11:
                pos[0, side, i] = (p.position.x, p.position.y)
                vel[0, side, i] = _vel_cart(p.velocity)
    b = snap.ball
    hs, hi = -1, 0
    if b.HasField("holder") and b.holder.number > 0:
        hs = int(b.holder.team_side); hi = b.holder.number - 1
    return J.State(
        turn=jnp.zeros(1, jnp.int32), pos=jnp.asarray(pos), vel=jnp.asarray(vel),
        ball_pos=jnp.asarray([[b.position.x, b.position.y]], jnp.float32),
        ball_vel=jnp.asarray([list(_vel_cart(b.velocity))], jnp.float32),
        holder_side=jnp.asarray([hs], jnp.int32), holder_idx=jnp.asarray([hi], jnp.int32),
        score=jnp.asarray([[snap.home_team.score, snap.away_team.score]], jnp.int32),
        shot_clock_side=jnp.asarray([snap.shot_clock.team_side], jnp.int32),
        shot_clock=jnp.asarray([snap.shot_clock.remaining_turns or J.SHOT_CLOCK_TIME], jnp.int32),
        jump_left=jnp.zeros((1, 2, 11), jnp.int32),
        goal_zone_turns=jnp.asarray([snap.turns_ball_in_goal_zone], jnp.int32))


@jax.jit
def _greedy_side(params, aobs_side):
    logits = _actor.apply(params, aobs_side)
    return jnp.stack([lg.argmax(-1) for lg in logits], -1)      # (1,11,4)


def make_net_policy(params_path=None, params=None):
    if params is None:
        with open(params_path or (_R / "rl/checkpoints/policy.pkl"), "rb") as f:
            params = jax.tree_util.tree_map(jnp.asarray, pickle.load(f))

    def policy(side, number, inspector):
        me = inspector.get_me()
        snap = inspector.get_snapshot()
        state = snapshot_to_state(snap)
        aobs, _ = get_obs(state)                              # (1,2,11,109)
        act = np.asarray(_greedy_side(params, aobs[:, side]))[0]  # (11,4)
        md, kd, catch, jump = act[number - 1]
        sign = 1.0 if side == J.HOME else -1.0                # des-canoniza x do AWAY
        orders = []
        if md > 0:
            ux, uy = _UNIT[md - 1]
            tgt = _mk_point(me.position.x + ux * sign * 500, me.position.y + uy * 500)
            orders.append(inspector.make_order_move(tgt, J.PLAYER_MAX_SPEED))
        if kd > 0:
            ux, uy = _UNIT[kd - 1]
            tgt = _mk_point(me.position.x + ux * sign * 3000, me.position.y + uy * 3000)
            orders.append(inspector.make_order_kick(tgt, J.BALL_MAX_SPEED))
        if jump and number == 1:
            ux, uy = _UNIT[md - 1] if md > 0 else (0.0, 1.0)
            tgt = _mk_point(me.position.x + ux * sign * 500, me.position.y + uy * 500)
            orders.append(inspector.make_order_jump(tgt, J.GOALKEEPER_JUMP_SPEED))
        if catch:
            orders.append(inspector.make_order_catch())
        if not orders:
            orders.append(inspector.make_order_catch())
        return orders

    return policy


def _mk_point(x, y):
    p = physics_pb2.Point()
    p.x = int(max(0, min(J.MAX_X, x))); p.y = int(max(0, min(J.MAX_Y, y)))
    return p
