"""
Reward por agente (B, 2, 11) a partir da transição (prev -> state).

Composição (pesos ajustáveis por variável de ambiente p/ experimentar):
- POR-AGENTE (credit assignment claro): near-ball (W_BALL, dist do jogador à bola)
  + is-holder (W_HOLD, +1 se ESTE jogador segura a bola -> aprende a pegar/reter).
- TIME (compartilhado pelos 11): avanço da bola ao gol atacado (W_ADV) + posse
  (W_POS) + finalização (W_SHOT, bola solta rumo ao gol) + GOL ±1.

IMPORTANTE: o shaping denso entra DIRETO (não potential-based γΦ'−Φ, que é
invariante à política e zera a vantagem em tarefa sem gols — bug de 2026-08-13).
"""
import os

import jax
import jax.numpy as jnp

import step as J


def _w(name, d):
    return float(os.environ.get(name, d))


W_ADV = _w("W_ADV", 0.20)     # avanço da bola ao gol (time)
W_POS = _w("W_POS", 0.02)     # posse (time)
W_BALL = _w("W_BALL", 0.10)   # proximidade à bola (per-agente)
W_HOLD = _w("W_HOLD", 0.30)   # segurar a bola (per-agente)
W_SHOT = _w("W_SHOT", 0.10)   # bola solta rumo ao gol atacado (time)
W_GOAL = _w("W_GOAL", 1.0)    # gol (time)

_ARANGE2 = jnp.arange(2)
_ARANGE11 = jnp.arange(11)


def _team(state):
    """Parte de TIME (B, 2)."""
    bx, by = state.ball_pos[:, 0], state.ball_pos[:, 1]
    d_home = jnp.sqrt((bx - J.MAX_X) ** 2 + (by - J.MAX_Y / 2) ** 2) / J.MAX_X
    d_away = jnp.sqrt(bx ** 2 + (by - J.MAX_Y / 2) ** 2) / J.MAX_X
    prox = jnp.stack([1.0 - d_home, 1.0 - d_away], axis=-1)
    held = state.holder_side >= 0
    poss = jax.nn.one_hot(jnp.clip(state.holder_side, 0, 1), 2, dtype=jnp.float32) \
        * held[:, None].astype(jnp.float32)
    # finalização: componente da velocidade da bola SOLTA rumo ao gol atacado
    bvx, bvy = state.ball_vel[:, 0], state.ball_vel[:, 1]
    loose = (state.holder_side < 0).astype(jnp.float32)
    uhx, uhy = J.MAX_X - bx, J.MAX_Y / 2 - by
    nh = jnp.sqrt(uhx ** 2 + uhy ** 2) + 1e-6
    uax, uay = -bx, J.MAX_Y / 2 - by
    na = jnp.sqrt(uax ** 2 + uay ** 2) + 1e-6
    ch = jnp.maximum(0.0, (bvx * uhx + bvy * uhy) / nh) / J.BALL_MAX_SPEED
    ca = jnp.maximum(0.0, (bvx * uax + bvy * uay) / na) / J.BALL_MAX_SPEED
    shot = jnp.stack([ch, ca], -1) * loose[:, None]
    return W_ADV * prox + W_POS * poss + W_SHOT * shot


def _per_agent(state):
    """Parte POR-AGENTE (B, 2, 11): near-ball + is-holder."""
    dball = jnp.sqrt(((state.pos - state.ball_pos[:, None, None, :]) ** 2).sum(-1))  # (B,2,11)
    near = W_BALL * (1.0 - dball / J.MAX_X)
    is_holder = ((state.holder_side[:, None, None] == _ARANGE2[None, :, None]) &
                 (state.holder_idx[:, None, None] == _ARANGE11[None, None, :])).astype(jnp.float32)
    return near + W_HOLD * is_holder


def compute_reward(prev, state, gamma=0.99):
    d_home = (state.score[:, 0] - prev.score[:, 0]).astype(jnp.float32)
    d_away = (state.score[:, 1] - prev.score[:, 1]).astype(jnp.float32)
    goal = W_GOAL * jnp.stack([d_home - d_away, d_away - d_home], axis=-1)   # (B,2)
    team = goal + _team(state)                                              # (B,2)
    return team[:, :, None] + _per_agent(state)                            # (B,2,11)
