"""
Reward por agente (B, 2, 11) a partir da transição (prev -> state).

DESIGN (v4, 2026-08-13). Evolução:
- v3 resolveu PERSEGUIR/PEGAR (posse 0%->57%) com near-ball forte + avanço gated
  por posse + catch-evento (ver [[lugo-rl-training]]). MAS não FINALIZA (0 gols):
  segurava no meio-campo (ball_x~12400) sem levar a bola ao gol. E marcar EXIGE um
  CHUTE: `_advance_players` empurra jogadores de linha p/ fora do círculo 1400 do
  gol atacado, então o holder não entra no gol driblando.
- v4: o avanço vira PROGRESSO-COM-POSSE (delta de distância ao gol enquanto SEGURA)
  — não-farmável parado (segurar no meio-campo = 0 progresso) e leva a bola ao gol.
  + reward de CHUTE perto do gol (bola solta rumo ao gol DENTRO do alcance de
  finalização) p/ ensinar a finalizar. Gol grande domina.

Regras: shaping DIRETO (não PBRS); todo peso por env-var; nada farmável parado.
"""
import os

import jax
import jax.numpy as jnp

import step as J


def _w(name, d):
    return float(os.environ.get(name, d))


W_BALL = _w("W_BALL", 0.30)          # near-ball per-agente (driver de perseguição)
BALL_SCALE = _w("BALL_SCALE", 8000.)  # escala da near-ball (menor = mais íngreme)
W_CATCH = _w("W_CATCH", 1.0)         # EVENTO de ganhar a posse (per-agente)
W_HOLD = _w("W_HOLD", 0.02)          # segurar por turno (per-agente) — minúsculo
W_RECV = _w("W_RECV", 0.60)          # pegar bola EM MOVIMENTO (receber passe/interceptar)
RECV_SPEED = _w("RECV_SPEED", 150.)  # limiar de velocidade p/ contar como passe/chute
W_ADV = _w("W_ADV", 0.15)            # avanço ABSOLUTO ao gol COM POSSE (time) — puxa ao gol
W_PROG = _w("W_PROG", 20.0)          # PROGRESSO (delta) ao gol COM POSSE (time) — driver forte
W_POS = _w("W_POS", 0.02)            # posse (time)
W_SHOT = _w("W_SHOT", 1.00)          # bola solta rumo ao gol DENTRO do alcance (time) — forte p/ finalizar
W_DANGER = _w("W_DANGER", 0.60)      # PENALIDADE: bola solta rumo ao PRÓPRIO gol no alcance (defesa)
FINISH_RANGE = _w("FINISH_RANGE", 6000.)  # alcance p/ shot/danger (dist ao gol)
W_GOAL = _w("W_GOAL", 10.0)          # gol (time) — grande

_ARANGE2 = jnp.arange(2)
_ARANGE11 = jnp.arange(11)


def _is_holder(state):
    """(B,2,11) 1.0 se o jogador (side,idx) segura a bola neste estado."""
    return ((state.holder_side[:, None, None] == _ARANGE2[None, :, None]) &
            (state.holder_idx[:, None, None] == _ARANGE11[None, None, :])).astype(jnp.float32)


def _goal_dists(ball_pos):
    """Distância (raw) da bola ao gol ATACADO por cada lado. (B,2): [HOME->gol AWAY, AWAY->gol HOME]."""
    bx, by = ball_pos[:, 0], ball_pos[:, 1]
    d_home = jnp.sqrt((bx - J.MAX_X) ** 2 + (by - J.MAX_Y / 2) ** 2)   # HOME ataca x=MAX_X
    d_away = jnp.sqrt(bx ** 2 + (by - J.MAX_Y / 2) ** 2)              # AWAY ataca x=0
    return jnp.stack([d_home, d_away], axis=-1)


def _team(prev, state):
    """Parte de TIME (B, 2): progresso+avanço COM POSSE + posse + chute perto do gol."""
    held = state.holder_side >= 0
    hold_oh = jax.nn.one_hot(jnp.clip(state.holder_side, 0, 1), 2, dtype=jnp.float32) \
        * held[:, None].astype(jnp.float32)                                    # (B,2) lado que segura AGORA
    d_now = _goal_dists(state.ball_pos)                                         # (B,2)
    d_prev = _goal_dists(prev.ball_pos)
    prox = 1.0 - d_now / J.MAX_X
    prog = (d_prev - d_now) / J.MAX_X                                          # >0 se a bola foi ao gol
    adv = W_ADV * prox * hold_oh          # pull absoluto (leve) só do lado que segura
    progr = W_PROG * prog * hold_oh       # PROGRESSO só do lado que segura (farm-proof)
    poss = W_POS * hold_oh
    # finalização: bola SOLTA rumo ao gol atacado E dentro do alcance de finalização
    bvx, bvy = state.ball_vel[:, 0], state.ball_vel[:, 1]
    loose = (state.holder_side < 0).astype(jnp.float32)
    bx, by = state.ball_pos[:, 0], state.ball_pos[:, 1]
    uhx, uhy = J.MAX_X - bx, J.MAX_Y / 2 - by
    nh = jnp.sqrt(uhx ** 2 + uhy ** 2) + 1e-6
    uax, uay = -bx, J.MAX_Y / 2 - by
    na = jnp.sqrt(uax ** 2 + uay ** 2) + 1e-6
    ch = jnp.maximum(0.0, (bvx * uhx + bvy * uhy) / nh) / J.BALL_MAX_SPEED
    ca = jnp.maximum(0.0, (bvx * uax + bvy * uay) / na) / J.BALL_MAX_SPEED
    in_range = (d_now <= FINISH_RANGE).astype(jnp.float32)                     # (B,2) perto do gol ATACADO
    shot = W_SHOT * jnp.stack([ch, ca], -1) * loose[:, None] * in_range
    # PERIGO: bola solta rumo ao PRÓPRIO gol e perto dele -> penalidade (afastar).
    # d_now = [dist->gol AWAY, dist->gol HOME]; próprio gol do HOME é x=0 (col 1),
    # do AWAY é x=MAX_X (col 0) -> d_own = d_now invertido.
    d_own = d_now[:, ::-1]                                                     # (B,2) dist ao PRÓPRIO gol
    in_range_own = (d_own <= FINISH_RANGE).astype(jnp.float32)
    toward_own = jnp.stack([ca, ch], -1)                                       # HOME: ca(rumo x=0); AWAY: ch(rumo MAX_X)
    danger = -W_DANGER * toward_own * loose[:, None] * in_range_own
    return adv + progr + poss + shot + danger


def _per_agent(prev, state):
    """Parte POR-AGENTE (B, 2, 11): near-ball (íngreme) + catch-event + hold.
    near-ball UNGATED: o holder tem a bola colada (near~0.29), e uma bola chutada
    (solta) foge a 400/turno > jogador 100/turno -> quem chuta PERDE o near-ball;
    logo o ungated FAVORECE segurar (posse ~50%, validado v3/v4). A finalização vem
    do avanço forte (W_ADV/W_PROG) + drill de start-state (finishing_state), não de
    gatear o near-ball (gate -> farm de bola-solta, posse 0%)."""
    dball = jnp.sqrt(((state.pos - state.ball_pos[:, None, None, :]) ** 2).sum(-1))  # (B,2,11)
    near = W_BALL * jnp.clip(1.0 - dball / BALL_SCALE, 0.0, 1.0)
    now_h = _is_holder(state)
    was_h = _is_holder(prev)
    catch_event = now_h * (1.0 - was_h)               # 1 só no turno da tomada de posse
    # receber passe / interceptar: pegar a bola quando ela estava EM MOVIMENTO
    ball_speed_prev = jnp.sqrt((prev.ball_vel ** 2).sum(-1))          # (B,)
    moving = (ball_speed_prev > RECV_SPEED).astype(jnp.float32)[:, None, None]
    receive = catch_event * moving
    return near + W_CATCH * catch_event + W_HOLD * now_h + W_RECV * receive


def compute_reward(prev, state, gamma=0.99):
    d_home = (state.score[:, 0] - prev.score[:, 0]).astype(jnp.float32)
    d_away = (state.score[:, 1] - prev.score[:, 1]).astype(jnp.float32)
    goal = W_GOAL * jnp.stack([d_home - d_away, d_away - d_home], axis=-1)   # (B,2)
    team = goal + _team(prev, state)                                        # (B,2)
    return team[:, :, None] + _per_agent(prev, state)                      # (B,2,11)
