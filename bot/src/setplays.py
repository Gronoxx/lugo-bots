"""Jogadas ensaiadas de REINÍCIO (kickoff) — gene `kickoff_play` (off = v3).

Evidência (36 replays, ago/2026): o reinício é 100% determinístico (todos
teleportam p/ init_position; 1º toque em reset+13; nosso #10 ganha 100% vs
level-1) e hoje rende ZERO chutes em 120 turnos — o #10 segura e solta para
trás. Este playbook converte a posse garantida em progressão:

  TAKER (#10) pega e tenta, nesta ordem: (1) TABELA ensaiada para o RECV (#9)
  em corrida — passe com lead, veto por fronteiras de turno + corrida no
  destino; (2) toque pro ESPAÇO à frente no flanco do RECV; (3) None → a
  cascata normal decide (nunca pior que a v3).
  RECV (#9) corre a rota funda (meio-campo + kickoff_run_depth, no próprio
  flanco). ONDA-2 (#7/#11) apóia em canais à frente. Os demais seguem o
  fluxo normal.
  ABORTA se o adversário vira o dono da bola (nunca tomar contra-ataque do
  kickoff DELES).

Estado usado (leve, re-derivável): `bot._reset_turn`, escrito por
`getting_ready` (dispara em TODO GET_READY, incl. pós-gol) e por assinatura
da bola no `_update_transition` (fallback p/ reconexão).
"""
import math

import lugo4py

import geometry as geo
import tactics as tac
from geometry import (BALL_MAX_SPEED, MAX_X, MAX_Y, dist, lead_target, point,
                      speed_for_distance, turns_for_ball, turns_for_player)
from params import P

TAKER = 10
RECV = 9
WAVE2 = (7, 11)
BLITZ_EXTRA = (8, 10)     # v7 (kickoff_blitz): somam-se a RECV+WAVE2 = bloco de 5


def _dir_sign(side):
    return 1.0 if side == lugo4py.TeamSide.HOME else -1.0


def active(bot, inspector):
    """Janela do kickoff aberta? (gene on + dentro da janela + sem contra).

    CONSERTO (v7, commit 0): o aborto por contra usava `bot._reset_turn=None`,
    o que matava o relógio do reset para TODOS os consumidores — inclusive os
    genes que agem exatamente quando a corrida é PERDIDA (kickoff_race ring,
    kickoff_shield). Agora aborta por flag `_ko_abort` (comportamento do
    kickoff_play idêntico; `_reset_turn` preservado). A flag é zerada em
    getting_ready e no fallback de reset do _update_transition."""
    if P.get("kickoff_play") != "on":
        return False
    if getattr(bot, "_ko_abort", False):
        return False
    rt = getattr(bot, "_reset_turn", None)
    if rt is None:
        return False
    turn = inspector.get_snapshot().turn
    if turn < rt or turn - rt > P["kickoff_window"]:
        return False
    h = inspector.get_ball_holder()
    if (h is not None and h.number != 0
            and h.team_side != inspector.get_my_team_side()):
        bot._ko_abort = True         # perdemos o kickoff: abortar a jogada
        return False
    return True


def _recv_route(me, side):
    """Rota do RECV: meio-campo + run_depth no sentido de ataque, no flanco."""
    x = MAX_X / 2.0 + _dir_sign(side) * P["kickoff_run_depth"]
    y = max(1200.0, min(MAX_Y - 1200.0, float(me.position.y)))
    return point(x, y)


def _wave2_route(me, side):
    """Canal de apoio da onda-2: meio caminho da rota do RECV, no próprio y."""
    x = MAX_X / 2.0 + _dir_sign(side) * (P["kickoff_run_depth"] * 0.5)
    y = max(1200.0, min(MAX_Y - 1200.0, float(me.position.y)))
    return point(x, y)


def hold_orders(bot, inspector, me, opponents):
    """Saída ensaiada do TAKER com a bola. None = cascata normal decide."""
    if not active(bot, inspector) or me.number != TAKER:
        return None
    side = inspector.get_my_team_side()
    ball = inspector.get_ball()
    recv = next((p for p in inspector.get_my_team_players()
                 if p.number == RECV), None)
    opps = list(opponents)

    # (1) TABELA para o RECV em corrida
    if recv is not None:
        d = dist(me.position, recv.position)
        if P["pass_min_dist"] * 0.5 <= d <= geo.MAX_KICK_RANGE:
            speed = min(BALL_MAX_SPEED,
                        speed_for_distance(d) * P["pass_speed_mult"])
            t_ball = turns_for_ball(speed, max(1.0, d - geo.TOUCH_RADIUS))
            if t_ball != math.inf:
                tgt = lead_target(recv, t_ball)
                t_recv = turns_for_player(dist(recv.position, tgt))
                race_ok = all(turns_for_player(dist(o.position, tgt)) > t_recv
                              for o in opps)
                if race_ok and geo.intercept_slack_turnwise(
                        ball.position, tgt, opps, speed) > 0.0:
                    return [geo.kick_to(inspector, me, ball, tgt, speed)]

    # (2) toque pro ESPAÇO à frente, viés para o flanco do RECV
    fy = float(recv.position.y) if recv is not None else MAX_Y / 2.0
    base_y = me.position.y + (300.0 if fy > me.position.y else -300.0)
    cand = point(me.position.x + _dir_sign(side) * 1100.0,
                 max(600.0, min(MAX_Y - 600.0, base_y)))
    my_t = turns_for_player(dist(me.position, cand))
    spd = speed_for_distance(dist(me.position, cand))
    if (all(turns_for_player(dist(o.position, cand)) > my_t + 1.0 for o in opps)
            and not geo.opponent_can_intercept(ball.position, cand, opps, spd)):
        return [geo.kick_to(inspector, me, ball, cand, spd)]

    return None                       # (3) cascata normal


def race_lost_active(bot, inspector):
    """v7/METAMORFO (kickoff_race): janela pós-reset com a corrida PERDIDA —
    eles seguram a saída, ou a disputa está perdida (chegam antes). NÃO usa
    active(): aquela janela ABORTA quando eles viram donos, que é exatamente
    o cenário do ring. Fonte: anel de 6 do BotAdversario1 antigo e do BotAdversario4
    sobre o kickoff adversário (roubo→gol em ~8s)."""
    if P.get("kickoff_race") != "on":
        return False
    rt = getattr(bot, "_reset_turn", None)
    if rt is None:
        return False
    turn = inspector.get_snapshot().turn
    if turn < rt or turn - rt > P["kr_window"]:
        return False
    h = inspector.get_ball_holder()
    if h is not None and h.number != 0:
        return h.team_side != inspector.get_my_team_side()
    return not tac.we_are_closest(inspector)


def ring_orders(bot, inspector, me, chasers, safe_move_fn):
    """v7 (kickoff_race): arco de interceptação do 1º passe deles, ao redor
    do círculo central no LADO DEFENSIVO, quando a corrida do reinício foi
    perdida. kr_ring_count MIDS/FWDS não-chasers mais próximos do centro;
    DEFENDERS nunca (a retaguarda fica). Slots por ordem de y em
    [-kr_arc_deg, +kr_arc_deg] da direção círculo→NOSSO gol, raio
    kr_ring_radius (fora do círculo; em jogo a posição é livre).
    None = fluxo normal."""
    if not race_lost_active(bot, inspector):
        return None
    if me.number == tac.GOALKEEPER or me.number in chasers:
        return None
    if me.number not in tac.MIDFIELDERS and me.number not in tac.FORWARDS:
        return None
    center = point(MAX_X / 2.0, MAX_Y / 2.0)
    pool = [p for p in inspector.get_my_team_players()
            if p.number not in chasers and p.number != tac.GOALKEEPER
            and (p.number in tac.MIDFIELDERS or p.number in tac.FORWARDS)]
    pool.sort(key=lambda p: (dist(p.position, center), p.number))
    chosen = pool[:int(round(P["kr_ring_count"]))]
    nums = [p.number for p in chosen]
    if me.number not in nums:
        return None
    by_y = sorted(chosen, key=lambda p: (p.position.y, p.number))
    slot = next(i for i, p in enumerate(by_y) if p.number == me.number)
    R = len(by_y)
    off_deg = 0.0 if R == 1 else (-1.0 + 2.0 * slot / (R - 1)) * P["kr_arc_deg"]
    side = inspector.get_my_team_side()
    # direção círculo -> NOSSO gol (HOME defende x=0 => pi; AWAY => 0)
    base_ang = math.pi if side == lugo4py.TeamSide.HOME else 0.0
    ang = base_ang + math.radians(off_deg)
    r = P["kr_ring_radius"]
    tx = center.x + math.cos(ang) * r
    ty = max(400.0, min(MAX_Y - 400.0, center.y + math.sin(ang) * r))
    return [safe_move_fn(point(tx, ty)), inspector.make_order_catch()]


def blitz_active(bot, inspector):
    """v7/METAMORFO (kickoff_blitz): janela da blitz do NOSSO reinício —
    corrida GANHA (ou em disputa), bloco ainda não chegou ao terço final.
    RELEASE devolve os corpos ao fluxo (nunca sequestra o finish_mode):
      - bola avançada além de kb_release; ou
      - portador nosso já em alcance de finalização (+1500 = janela do
        finish_mode); ou
      - perdemos a bola (contra: aborta).
    Fonte: BotAdversario2 7×0 — o PRÓPRIO kickoff convertido em blitz, gol aos 7s."""
    if P.get("kickoff_blitz") != "on":
        return False
    rt = getattr(bot, "_reset_turn", None)
    if rt is None or getattr(bot, "_ko_abort", False):
        return False
    turn = inspector.get_snapshot().turn
    if turn < rt or turn - rt > P["kb_window"]:
        return False
    side = inspector.get_my_team_side()
    h = inspector.get_ball_holder()
    if h is not None and h.number != 0:
        if h.team_side != side:
            return False              # perdemos a corrida: sem blitz
        gc = bot.mapper.get_attack_goal().get_center()
        if dist(h.position, gc) <= P["dangerous_shot_range"] + 1500.0:
            return False              # jogada madura: finish/cascata assumem
    if tac.ball_advance_frac(inspector.get_ball().position,
                             side) >= P["kb_release"]:
        return False                  # bloco chegou: fluxo normal decide
    return True


def _blitz_route(me, side):
    """Canal profundo da blitz: kb_depth além do meio-campo, no próprio y."""
    x = MAX_X / 2.0 + _dir_sign(side) * P["kb_depth"]
    y = max(1200.0, min(MAX_Y - 1200.0, float(me.position.y)))
    return point(x, y)


def route_orders(bot, inspector, me, safe_move_fn):
    """Rotas do RECV/onda-2 durante a janela (supporting/disputing).
    None = fluxo normal. `safe_move_fn(target) -> Order`.
    v7 (kickoff_blitz): terminada/ausente a janela ensaiada, o bloco de 5
    (RECV+WAVE2+BLITZ_EXTRA, exceto o portador) aprofunda ao terço final."""
    side = inspector.get_my_team_side()
    if active(bot, inspector):
        if me.number == RECV:
            return [safe_move_fn(_recv_route(me, side)),
                    inspector.make_order_catch()]
        if me.number in WAVE2:
            return [safe_move_fn(_wave2_route(me, side)),
                    inspector.make_order_catch()]
    if blitz_active(bot, inspector):
        h = inspector.get_ball_holder()
        hnum = (h.number if (h is not None and h.number != 0
                             and h.team_side == side) else -1)
        if me.number != hnum and (me.number == RECV or me.number in WAVE2
                                  or me.number in BLITZ_EXTRA):
            return [safe_move_fn(_blitz_route(me, side)),
                    inspector.make_order_catch()]
    return None
