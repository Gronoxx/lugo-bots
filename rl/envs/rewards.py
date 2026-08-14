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


def _team_reward(state):
    """Parte de TIME (B, 2): proximidade da bola ao gol atacado + posse."""
    bx, by = state.ball_pos[:, 0], state.ball_pos[:, 1]
    d_home = jnp.sqrt((bx - J.MAX_X) ** 2 + (by - J.MAX_Y / 2) ** 2) / J.MAX_X
    d_away = jnp.sqrt(bx ** 2 + (by - J.MAX_Y / 2) ** 2) / J.MAX_X
    prox = jnp.stack([1.0 - d_home, 1.0 - d_away], axis=-1)
    held = state.holder_side >= 0
    poss = jax.nn.one_hot(jnp.clip(state.holder_side, 0, 1), 2, dtype=jnp.float32) \
        * held[:, None].astype(jnp.float32)
    return W_ADV * prox + W_POS * poss                       # (B,2)


def _near_ball(state):
    """Parte PER-AGENTE (B, 2, 11): cada jogador recompensado pela SUA distância
    à bola. Sinal individual claro p/ aprender a perseguir (credit assignment)."""
    dball = jnp.sqrt(((state.pos - state.ball_pos[:, None, None, :]) ** 2).sum(-1))  # (B,2,11)
    return W_BALL * (1.0 - dball / J.MAX_X)


def compute_reward(prev, state, gamma=0.99):
    """Retorna reward por agente (B, 2, 11).

    IMPORTANTE: o shaping denso (Φ) entra DIRETO, não como diferença potencial
    γΦ'−Φ. Potential-based shaping é invariante à política (Ng 1999): numa tarefa
    sem gols a vantagem vira 0 por construção e o ATOR não aprende nada (só o
    crítico ajusta V≈−Φ). Reward direta enviesa para "perseguir/reter/avançar" —
    exatamente o comportamento que queremos bootstrapar. (Diagnóstico 2026-08-13.)"""
    d_home = (state.score[:, 0] - prev.score[:, 0]).astype(jnp.float32)
    d_away = (state.score[:, 1] - prev.score[:, 1]).astype(jnp.float32)
    goal = jnp.stack([d_home - d_away, d_away - d_home], axis=-1)   # (B,2) time
    team = goal + _team_reward(state)                             # (B,2) time
    return team[:, :, None] + _near_ball(state)                  # (B,2,11) time + per-agente
