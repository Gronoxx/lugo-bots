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
from geometry import (BALL_MAX_SPEED, MAX_X, MAX_Y, dist, lead_target, point,
                      speed_for_distance, turns_for_ball, turns_for_player)
from params import P

TAKER = 10
RECV = 9
WAVE2 = (7, 11)


def _dir_sign(side):
    return 1.0 if side == lugo4py.TeamSide.HOME else -1.0


def active(bot, inspector):
    """Janela do kickoff aberta? (gene on + dentro da janela + sem contra)."""
    if P.get("kickoff_play") != "on":
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
        bot._reset_turn = None       # perdemos o kickoff: abortar a jogada
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


def route_orders(bot, inspector, me, safe_move_fn):
    """Rotas do RECV/onda-2 durante a janela (supporting/disputing).
    None = fluxo normal. `safe_move_fn(target) -> Order`."""
    if not active(bot, inspector):
        return None
    side = inspector.get_my_team_side()
    if me.number == RECV:
        return [safe_move_fn(_recv_route(me, side)),
                inspector.make_order_catch()]
    if me.number in WAVE2:
        return [safe_move_fn(_wave2_route(me, side)),
                inspector.make_order_catch()]
    return None
