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

W_ADV = 0.20     # peso da PROXIMIDADE da bola ao gol atacado (potencial denso)
W_POS = 0.05     # peso da posse
W_BALL = 0.10    # peso da proximidade do time À BOLA (incentiva perseguir/ganhar)


def _potential(state):
    """Φ por lado (B, 2): proximidade da bola ao gol ATACADO + posse.
    Puxa a bola rumo ao gol (dá gradiente denso para avançar e finalizar)."""
    bx, by = state.ball_pos[:, 0], state.ball_pos[:, 1]
    # distância da bola ao centro do gol atacado por cada lado (HOME->x=MAX_X)
    d_home = jnp.sqrt((bx - J.MAX_X) ** 2 + (by - J.MAX_Y / 2) ** 2) / J.MAX_X
    d_away = jnp.sqrt(bx ** 2 + (by - J.MAX_Y / 2) ** 2) / J.MAX_X
    prox = jnp.stack([1.0 - d_home, 1.0 - d_away], axis=-1)   # perto do gol = alto
    held = state.holder_side >= 0
    poss = jax.nn.one_hot(jnp.clip(state.holder_side, 0, 1), 2, dtype=jnp.float32) \
        * held[:, None].astype(jnp.float32)
    # proximidade do time à bola (o jogador mais perto de cada lado)
    dball = jnp.sqrt(((state.pos - state.ball_pos[:, None, None, :]) ** 2).sum(-1))  # (B,2,11)
    near = 1.0 - jnp.min(dball, axis=2) / J.MAX_X                                   # (B,2)
    return W_ADV * prox + W_POS * poss + W_BALL * near


def compute_reward(prev, state, gamma=0.99):
    """Retorna reward por agente (B, 2, 11)."""
    d_home = (state.score[:, 0] - prev.score[:, 0]).astype(jnp.float32)
    d_away = (state.score[:, 1] - prev.score[:, 1]).astype(jnp.float32)
    goal = jnp.stack([d_home - d_away, d_away - d_home], axis=-1)   # (B,2)
    F = gamma * _potential(state) - _potential(prev)               # (B,2)
    r_side = goal + F                                              # (B,2)
    return jnp.broadcast_to(r_side[:, :, None], r_side.shape + (11,))
