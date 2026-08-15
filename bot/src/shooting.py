"""Fundamentos de FINALIZACAO (spec do usuario). Primitivos puros, reusaveis:

- coverage_prob(pt, defenders, t): LIBERDADE probabilistica de um ponto (0..1) —
  ponto na borda do disco de 1 defensor ~ provavel livre; fundo/varios ~ improvavel
  (produto de logisticas do slack por defensor). A evolucao 'probabilistico' da spec.
- keeper_expected_y(gk, ball_side_y, turns): posicao y ESPERADA do goleiro apos
  `turns` (ele rastreia a bola a <=100/turno em y, preso a linha).
- shot_slack(target_y, gk_y, t_ball, jump): folga do goleiro a uma mira (conta o
  pulo 200/turno x3, so vale mais perto). >0 => ele nao cobre.
- best_goal_shot(...): melhor ponto do gol p/ chutar AGORA (max slack, alcancavel,
  linha livre) => base do Caso 1 (chutar se GOL CERTO).

Zona do gol: chutes saem de >=1400 do centro (jogadores de linha nao entram).
Nada disto altera o bot ate ser ligado por gene.
"""
import math

import geometry as geo
from geometry import BALL_MAX_SPEED, turns_for_ball, ball_range

GK_HALF = geo.GOALKEEPER_HALF_EXTENT          # ~560
GOAL_LO, GOAL_HI = geo.GOAL_MIN_Y, geo.GOAL_MAX_Y   # 3500, 6500
JUMP_SPEED = 200.0
JUMP_TURNS = 3.0


def _logistic(x, k):
    return 1.0 / (1.0 + math.exp(-x / k))


def coverage_prob(px, py, defenders, t, spread=1.0):
    """LIBERDADE (0..1) do ponto (px,py) no horizonte de t turnos. defenders =
    lista (x,y,reach,speed). slack_k = (|P-Q_k|-reach)/speed - t (turnos que o
    defensor SOBRA); livre se todos sobram. Produto de logisticas: borda de 1 disco
    (slack~0)=>~0.5; fundo/varios=>baixo; nenhum perto=>~1. `spread` = suavidade."""
    free = 1.0
    for dx, dy, reach, spd in defenders:
        d = math.hypot(px - dx, py - dy)
        t_reach = (d - reach) / max(1.0, spd)
        slack = t_reach - t
        free *= _logistic(slack, spread)
        if free <= 1e-4:
            break
    return free


def keeper_expected_y(gk_y, ball_target_y, turns, speed=100.0):
    """y ESPERADO do goleiro apos `turns`: ele desliza em direcao a ameaca
    (ball_target_y) a <=speed/turno, preso a linha. Aproxima o rastreamento."""
    step = speed * turns
    if ball_target_y > gk_y:
        return min(ball_target_y, gk_y + step)
    return max(ball_target_y, gk_y - step)


def shot_slack(target_y, gk_y, t_ball, gk_reach_speed):
    """Folga do goleiro a uma mira `target_y`, contando o pulo (200/turno ate 3
    turnos, depois corrida) a partir de gk_y. >0 => nao cobre. Modelo conservador
    (usa o MAIOR alcance vertical que o goleiro consegue em t_ball turnos)."""
    reach_move = JUMP_SPEED * min(t_ball, JUMP_TURNS)
    if t_ball > JUMP_TURNS:
        reach_move += gk_reach_speed * (t_ball - JUMP_TURNS)
    return abs(target_y - gk_y) - (GK_HALF + reach_move)


def best_goal_shot(ball_pos, goal_x, gk, opponents, gk_reach_speed,
                   v0=BALL_MAX_SPEED, n_targets=13):
    """Melhor ponto do gol p/ chutar AGORA. Devolve (target_point, slack, t_ball)
    do ponto com MAIOR folga do goleiro, alcancavel (alcance da bola) e com linha
    livre (nao interceptavel). None se nenhum ponto e' viavel. slack>margin => Caso 1
    (gol praticamente certo)."""
    bx, by = ball_pos.x, ball_pos.y
    gk_y = gk.position.y if gk is not None else (GOAL_LO + GOAL_HI) / 2.0
    best = None
    for i in range(n_targets):
        ty = GOAL_LO + 150 + i * (GOAL_HI - GOAL_LO - 300) / (n_targets - 1)
        tgt = geo.point(goal_x, ty)
        d = math.hypot(goal_x - bx, ty - by)
        if ball_range(v0) < d:
            continue                          # forca nao alcanca esse ponto
        t_ball = turns_for_ball(v0, d)
        if t_ball == math.inf:
            continue
        # goleiro no fim do voo: desliza rumo a mira
        gk_end = keeper_expected_y(gk_y, ty, t_ball)
        sl = shot_slack(ty, gk_end, t_ball, gk_reach_speed)
        # linha livre de adversarios (chute nao interceptado)
        if geo.can_be_intercepted(ball_pos, tgt, opponents, v0, False):
            continue
        if best is None or sl > best[1]:
            best = (tgt, sl, t_ball)
    return best
