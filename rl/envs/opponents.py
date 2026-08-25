"""
Oponentes heurísticos JAX-nativos (vetorizados, branchless) para o pool de treino
e para avaliação. Ação (B,2,11,4) no referencial CANÔNICO (sempre ataca +x); o
env des-espelha o x do AWAY.

- chase_action: todos vão à bola (enxame) + catch. Baseline fraco.
- formation_action: DEFESA ORGANIZADA + contra-ataque — segura formação, pressiona
  com os 2 mais próximos, goleiro acompanha a bola, holder dribla ao gol e chuta
  perto. Oponente MUITO mais forte que o chase (ataca o gargalo do RL: só treinava
  vs oponentes fracos).
"""
import jax
import jax.numpy as jnp

import step as J

N_DIR = 16
_SIGN = jnp.array([1.0, -1.0]).reshape(1, 2, 1)          # flip x p/ canônico do AWAY
_IS_GK = (jnp.arange(11) == 0).reshape(1, 1, 11)
_AR2 = jnp.arange(2).reshape(1, 2, 1)
_AR11 = jnp.arange(11).reshape(1, 1, 11)

_HOME_ABS = jnp.stack([J._FORM[:, 0] * J.MAX_X, J._FORM[:, 1] * J.MAX_Y], -1)   # (11,2)
_AWAY_ABS = jnp.stack([(1 - J._FORM[:, 0]) * J.MAX_X, J._FORM[:, 1] * J.MAX_Y], -1)
_FORM_ABS = jnp.stack([_HOME_ABS, _AWAY_ABS], 0)         # (2,11,2) casa de cada jogador
# gol ATACADO por cada lado: HOME->x=MAX_X, AWAY->x=0 (y no meio)
_ATK_GOAL = jnp.stack([jnp.array([J.MAX_X, J.MAX_Y / 2]), jnp.array([0.0, J.MAX_Y / 2])], 0)  # (2,2)


def _discretize(vec_abs):
    """(...,2) direção ABSOLUTA -> move_dir canônico (...,), 0 se ~parado."""
    ang = jnp.arctan2(vec_abs[..., 1], vec_abs[..., 0] * _SIGN) % (2 * jnp.pi)
    d = (jnp.round(ang / (2 * jnp.pi / N_DIR)).astype(jnp.int32) % N_DIR) + 1
    small = (jnp.sqrt((vec_abs ** 2).sum(-1)) < 50.0)
    return jnp.where(small, 0, d)


def chase_action(state):
    to = state.ball_pos[:, None, None, :] - state.pos       # (B,2,11,2)
    md = _discretize(to)
    z = jnp.zeros_like(md)
    return jnp.stack([md, z, jnp.ones_like(md), z], -1)


def formation_action(state):
    B = state.pos.shape[0]
    pos = state.pos                                          # (B,2,11,2)
    ball = state.ball_pos                                    # (B,2)
    to_ball = ball[:, None, None, :] - pos                   # (B,2,11,2)
    dist = jnp.sqrt((to_ball ** 2).sum(-1))                  # (B,2,11)
    dist_of = jnp.where(_IS_GK, jnp.inf, dist)
    closest = dist_of == dist_of.min(-1, keepdims=True)
    press = (closest | (dist_of < 1500.0)) & ~_IS_GK        # 2 mais próximos pressionam

    to_home = _FORM_ABS[None] - pos                          # (B,2,11,2) rumo à casa
    to_goal = _ATK_GOAL[None, :, None, :] - pos              # (B,2,11,2) rumo ao gol atacado
    is_holder = (state.holder_side[:, None, None] == _AR2) & (state.holder_idx[:, None, None] == _AR11)

    desired = jnp.where(press[..., None], to_ball, to_home)  # press->bola, resto->casa
    desired = jnp.where(is_holder[..., None], to_goal, desired)  # holder dribla ao gol
    # goleiro (idx 0): acompanha o y da bola (x é preso pelo sim)
    gk_dy = ball[:, 1][:, None] - pos[:, :, 0, 1]            # (B,2)
    desired = desired.at[:, :, 0, 0].set(0.0)
    desired = desired.at[:, :, 0, 1].set(gk_dy)

    md = _discretize(desired)
    # chute: só o holder, e só perto do gol (senão dribla)
    d_goal = jnp.sqrt((to_goal ** 2).sum(-1))               # (B,2,11)
    kick_close = is_holder & (d_goal < 5000.0)
    kd = jnp.where(kick_close, _discretize(to_goal), 0)
    catch = jnp.ones_like(md)
    jump = jnp.zeros_like(md)
    return jnp.stack([md, kd, catch, jump], -1)
