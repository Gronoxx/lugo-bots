"""Caso 2 da finalizacao (spec do usuario): MANOBRAR o goleiro.

O condutor compromete um lado (perto do anel de 1400); o Jogador 1 corre para o
lado CONTRARIO ate o ponto probabilisticamente mais livre com bom angulo de chute
dado a posicao ESPERADA do goleiro (deslocado p/ o lado do condutor); o Jogador 2
e' um no-rele intermediario/seguranca. Determinismo por papel (cada jogador calcula
a mesma jogada do snapshot; sem comunicacao). Re-planeja a cada turno.

Zona do gol: pontos de corrida/chute ficam a >=1400 do centro do gol.
Tudo inerte ate finish_mode="on".
"""
import math

import geometry as geo
from geometry import PLAYER_SPEED, point, dist
from params import P
import shooting as S

FORWARDS = (9, 10, 11)
MIDS = (6, 7, 8)
GOAL_ZONE = 1400.0
GOAL_C = (geo.GOAL_MIN_Y + geo.GOAL_MAX_Y) / 2.0   # 5000


def _defs(opponents, gk):
    gkn = gk.number if gk is not None else -1
    return [(o.position.x, o.position.y, geo.TOUCH_RADIUS, PLAYER_SPEED)
            for o in opponents if o.number != gkn]


def roles(holder, mates):
    """(jog1, jog2) deterministicos. jog1 = atacante no lado CONTRARIO ao condutor
    (o mais avancado); jog2 = meia mais central p/ ser rele. None se nao houver."""
    hy = holder.position.y
    fwds = [m for m in mates if m.number in FORWARDS]
    opp_side = [m for m in fwds if (m.position.y - GOAL_C) * (hy - GOAL_C) < 0]
    pool = opp_side or fwds
    jog1 = max(pool, key=lambda m: m.position.x if holder.position.x > 10000
               else -m.position.x, default=None)
    mids = [m for m in mates if m.number in MIDS and (jog1 is None or m.number != jog1.number)]
    jog2 = min(mids, key=lambda m: abs(m.position.y - GOAL_C), default=None)
    return jog1, jog2


def run_point(receiver, ball_pos, gk, opponents, goal_x, holder_pos, horizon):
    """Ponto de corrida do Jogador 1: no lado CONTRARIO ao condutor, a >=1400 do
    gol, que maximiza w_cover*liberdade + w_slack*angulo_de_chute (dado o goleiro
    ESPERADO deslocado p/ o lado do condutor). None se nada razoavel."""
    defs = _defs(opponents, gk)
    gk_y = gk.position.y if gk is not None else GOAL_C
    gk_end = S.keeper_expected_y(gk_y, holder_pos.y, horizon)   # goleiro puxado p/ o condutor
    far_up = holder_pos.y < GOAL_C                              # condutor embaixo -> jog1 em cima
    ys = ([5900, 6300, 6600] if far_up else [4100, 3700, 3400])
    xs = [goal_x - d if goal_x > 10000 else goal_x + d for d in (1500, 1900, 2400)]
    best = None
    for rx in xs:
        for ry in ys:
            if math.hypot(goal_x - rx, GOAL_C - ry) < GOAL_ZONE:
                continue
            if not (0 <= rx <= geo.MAX_X and 0 <= ry <= geo.MAX_Y):
                continue
            cov = S.coverage_prob(rx, ry, defs, horizon)
            # slack de chute do ponto (mira o canto oposto ao goleiro esperado)
            tgt_y = geo.GOAL_MIN_Y if gk_end > GOAL_C else geo.GOAL_MAX_Y
            d_shot = math.hypot(goal_x - rx, tgt_y - ry)
            tb = geo.turns_for_ball(geo.BALL_MAX_SPEED, d_shot)
            sl = S.shot_slack(tgt_y, gk_end, tb if tb != math.inf else 6.0,
                              P["gk_reach_speed"])
            score = P["finish_w_cover"] * cov + P["finish_w_slack"] * max(0.0, sl) / 1000.0
            if best is None or score > best[0]:
                best = (score, point(rx, ry))
    return best[1] if best else None


def relay_point(jog2, holder_pos, jog1_target, opponents, gk):
    """Ponto do Jogador 2 (rele/seguranca): entre o condutor e o Jogador 1 no eixo
    y, um pouco RECUADO no x, buscando ficar livre p/ receber e repassar."""
    my = (holder_pos.y + jog1_target.y) / 2.0
    mx = min(holder_pos.x, jog1_target.x) - 700.0     # recuado
    mx = max(0.0, min(geo.MAX_X, mx))
    # ajusta y p/ a maior liberdade local (evita marcador)
    defs = _defs(opponents, gk)
    best = (S.coverage_prob(mx, my, defs, 3), point(mx, my))
    for dy in (-800, -400, 400, 800):
        yy = max(0.0, min(geo.MAX_Y, my + dy))
        c = S.coverage_prob(mx, yy, defs, 3)
        if c > best[0]:
            best = (c, point(mx, yy))
    return best[1]


def holder_cross(holder, jog1, gk, opponents, goal_x):
    """Se o Jogador 1 esta aberto (linha de cruzamento livre) E teria um chute que
    vence o goleiro da posicao dele -> (target, speed) do cruzamento; senao None.

    Conserto (P1, 2026-08-16): a versao anterior mirava a posicao ATUAL do
    jog1 — que esta CORRENDO para o ponto de corrida — entao o cruzamento
    chegava atras do corredor. Agora mira lead_target(jog1, t_bola) e exige a
    corrida no destino (padrao pass_endpoint_race): o cruzamento so sai se o
    corredor chega ao ponto antes de qualquer adversario."""
    if jog1 is None:
        return None
    d = dist(holder.position, jog1.position)
    if d < P["pass_min_dist"] or d > geo.MAX_KICK_RANGE:
        return None
    speed = min(geo.BALL_MAX_SPEED, geo.speed_for_distance(d) * P["pass_speed_mult"])
    t_ball = geo.turns_for_ball(speed, max(1.0, d - geo.TOUCH_RADIUS))
    if t_ball == math.inf:
        return None
    opps = list(opponents)
    tgt = geo.lead_target(jog1, t_ball)
    t_recv = geo.turns_for_player(dist(jog1.position, tgt))
    if any(geo.turns_for_player(dist(o.position, tgt)) <= t_recv for o in opps):
        return None
    if geo.can_be_intercepted(holder.position, tgt, opps, speed, False):
        return None
    # o Jogador 1 venceria o goleiro DO PONTO DE CHEGADA?
    sh = S.best_goal_shot(tgt, goal_x, gk, opps, P["gk_reach_speed"])
    if sh is None or sh[1] <= P["finish_sure_slack"]:
        return None
    return (tgt, speed)
