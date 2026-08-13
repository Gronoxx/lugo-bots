"""
Reward por agente a partir da transição (prev_state -> state).

- Esparso principal: ±1 por gol (delta de score). O time que marca recebe +1, o
  que sofre -1, compartilhado pelos 11 agentes.
- Shaping POTENTIAL-BASED F = γΦ(s') − Φ(s) (invariante à política ótima, pode
  ser anelado): Φ = avanço da bola rumo ao gol atacado + posse. Pesos pequenos
  para dar gradiente denso sem dominar o gol.
"""
import jax
import jax.numpy as jnp

import step as J

W_ADV = 0.05     # peso do avanço da bola no potencial
W_POS = 0.02     # peso da posse


def _potential(state):
    """Φ por lado (B, 2)."""
    bx = state.ball_pos[:, 0] / J.MAX_X                     # 0..1 (x da bola)
    adv = jnp.stack([bx, 1.0 - bx], axis=-1)               # HOME quer x alto; AWAY baixo
    held = state.holder_side >= 0
    poss = jax.nn.one_hot(jnp.clip(state.holder_side, 0, 1), 2, dtype=jnp.float32) \
        * held[:, None].astype(jnp.float32)
    return W_ADV * adv + W_POS * poss


def compute_reward(prev, state, gamma=0.99):
    """Retorna reward por agente (B, 2, 11)."""
    d_home = (state.score[:, 0] - prev.score[:, 0]).astype(jnp.float32)
    d_away = (state.score[:, 1] - prev.score[:, 1]).astype(jnp.float32)
    goal = jnp.stack([d_home - d_away, d_away - d_home], axis=-1)   # (B,2)
    F = gamma * _potential(state) - _potential(prev)               # (B,2)
    r_side = goal + F                                              # (B,2)
    return jnp.broadcast_to(r_side[:, :, None], r_side.shape + (11,))
