"""Planejador de passe NAO-GULOSO (Componente 2 do "quando passar").

Transforma a decisao de passe de gulosa (melhor 1 salto) numa BUSCA EM FEIXE
sobre um grafo de linhas de passe VIAVEIS no tempo, terminando no jogador mais
perto do gol. Control-aware: a Etapa 0 (ablacao exec_speed) provou que o
first-touch e' REAL (bola quente sai fraca), entao cada perna usa a velocidade
EXECUTAVEL (forma fechada, barata) e existe a opcao de CONTROLAR (assentar a bola
k turnos -> passe pleno, ao custo de dar k turnos a mais aos defensores).

Fisica reusada de geometry.py (nada recalculado). Horizonte recuado (MPC): o
chamador executa so a 1a perna e replaneja a cada turno.

Tudo default-off: com pass_lookahead="off" o modulo nunca e' chamado (=v9).
"""
import math

import geometry as geo
from geometry import (BALL_MAX_SPEED, PLAYER_SPEED, TOUCH_RADIUS, MAX_X,
                      dist, point, speed_for_distance, turns_for_ball,
                      turns_for_player, lead_target, ball_range)
from params import P

GK_NUMBER = 1


# ---------------------------------------------------------------- primitivas
def exec_speed_toward(cvx, cvy, ux, uy):
    """Velocidade EXECUTAVEL da bola na direcao unitaria (ux,uy), em forma
    fechada (barata; NAO a busca de 288 de achievable_shot_speed). Modela o
    first-touch: a velocidade atual da bola (cvx,cvy) e' somada ao chute (o
    jogador orienta-se ao alvo -> fator de angulo ~1), o total e' limitado a
    BALL_MAX_SPEED e projetado no alvo. Bola quente adversa reduz a saida; bola
    assentada (c=0) => BALL_MAX_SPEED pleno."""
    rx, ry = cvx + ux * BALL_MAX_SPEED, cvy + uy * BALL_MAX_SPEED
    n = math.hypot(rx, ry)
    if n > BALL_MAX_SPEED:
        rx, ry = rx / n * BALL_MAX_SPEED, ry / n * BALL_MAX_SPEED
    return max(0.0, rx * ux + ry * uy)


def leg_slack(ox, oy, tx, ty, opponents, kick_speed, theta, use_velocity):
    """Menor folga temporal (turnos) de um adversario interceptar a bola na perna
    ox,oy -> tx,ty, com os discos dos defensores INFLADOS pelo horizonte global
    `theta` (turnos ja gastos na cadeia). Generaliza o veto v9:
       slack = turns_for_player(d_opp) - theta - t_ball(ponto)
    >0 seguro; <=0 interceptavel; UNREACHABLE se a bola nao chega. theta=0
    reproduz o veto de 1 passo (a menos da densidade de amostragem)."""
    dx, dy = tx - ox, ty - oy
    total = math.hypot(dx, dy)
    if total == 0.0:
        return math.inf
    steps = max(8, min(geo.INTERCEPT_MAX_STEPS,
                       int(math.ceil(total / geo.INTERCEPT_SAMPLE_SPACING))))
    mn = math.inf
    for i in range(1, steps + 1):
        f = i / steps
        db = total * f
        if db < geo.NO_BLOCK_NEAR_ORIGIN:
            continue
        px, py = ox + dx * f, oy + dy * f
        tb = turns_for_ball(kick_speed, db)
        if tb == math.inf:
            return geo.UNREACHABLE_RISK
        for o in opponents:
            dop = math.hypot(px - o.position.x, py - o.position.y)
            if use_velocity:
                lx, ly = geo._lead_pos(o, min(tb, geo.INTERCEPT_LEAD_TURNS))
                dl = math.hypot(px - lx, py - ly)
                if dl < dop:
                    dop = dl
            slack = turns_for_player(dop) - theta - tb
            if slack < mn:
                mn = slack
    return mn


def _nearest_opp_turns(px, py, opponents, opp_gk):
    """Turnos ate o adversario de LINHA mais proximo alcancar (px,py). Exclui o
    goleiro adversario (mesma convencao do status)."""
    gk = opp_gk.number if opp_gk is not None else -1
    best = math.inf
    for o in opponents:
        if o.number == gk:
            continue
        t = turns_for_player(math.hypot(px - o.position.x, py - o.position.y))
        if t < best:
            best = t
    return best


def _is_free(px, py, opponents, opp_gk):
    return _nearest_opp_turns(px, py, opponents, opp_gk) > P["status_attention_turns"]


def node_value(px, py, opponents, opp_gk, goal_center):
    """Valor de ter a bola em (px,py): progresso ao gol + bonus por chute com
    folga do goleiro (fora de alcance -> so progresso) + bonus se a posicao esta
    livre. Unidades em distancia (progresso domina)."""
    dgoal = math.hypot(goal_center.x - px, goal_center.y - py)
    v = P["plan_w_progress"] * (MAX_X - dgoal)
    if dgoal <= P["dangerous_shot_range"] and opp_gk is not None:
        tb = turns_for_ball(BALL_MAX_SPEED, dgoal)
        if tb != math.inf:
            # mira a trave mais LONGE do goleiro; folga = quanto ele NAO cobre
            gc_y = (geo.GOAL_MIN_Y + geo.GOAL_MAX_Y) / 2.0
            far_y = geo.GOAL_MIN_Y if opp_gk.position.y > gc_y else geo.GOAL_MAX_Y
            slack = abs(far_y - opp_gk.position.y) - (geo.GOALKEEPER_HALF_EXTENT
                                                      + P["gk_reach_speed"] * tb)
            if slack > 0.0:
                v += P["plan_w_shot"] * slack
    if _is_free(px, py, opponents, opp_gk):
        v += P["plan_w_livre"]
    return v


# ------------------------------------------------------------------- pernas
def _make_leg(ox, oy, bvx, bvy, theta, mate, opponents, control, use_velocity):
    """Uma perna de (ox,oy) [bola chega com vel (bvx,bvy)] ate `mate`. Devolve
    (target, kick_speed, child_pos, child_bvx, child_bvy, theta_after) ou None se
    inviavel (nao alcanca, interceptavel, ou fora de faixa)."""
    d0 = math.hypot(mate.position.x - ox, mate.position.y - oy)
    if d0 < P["pass_min_dist"] or d0 > geo.MAX_KICK_RANGE:
        return None
    desired = min(BALL_MAX_SPEED, speed_for_distance(d0) * P["pass_speed_mult"])
    # ponto de lead (projeta o receptor pela sua velocidade)
    t_est = turns_for_ball(desired, max(1.0, d0))
    tgt = lead_target(mate, t_est if t_est != math.inf else 0.0)
    dx, dy = tgt.x - ox, tgt.y - oy
    d = math.hypot(dx, dy)
    if d < 1.0:
        return None
    ux, uy = dx / d, dy / d
    cvx, cvy = (0.0, 0.0) if control else (bvx, bvy)
    kick = min(desired, exec_speed_toward(cvx, cvy, ux, uy))
    d_reach = max(1.0, d - TOUCH_RADIUS) if P.get("pass_touch_lead") == "on" else d
    if ball_range(kick) < d_reach:
        return None                       # first-touch fraco demais p/ chegar
    tb = turns_for_ball(kick, d_reach)
    if tb == math.inf:
        return None
    theta_extra = P["plan_control_turns"] if control else 0.0
    slack = leg_slack(ox, oy, tgt.x, tgt.y, opponents, kick,
                      theta + theta_extra, use_velocity)
    if slack <= P["plan_margin_turns"]:
        return None
    arr = geo._arrival_speed_at(kick, d_reach)
    return (tgt, kick, tgt.x, tgt.y, ux * arr, uy * arr,
            theta + theta_extra + tb)


def plan_pass(me, ball, mates, opponents, goal_center, opp_gk, use_velocity,
              game_aggr=0.0):
    """Melhor 1a perna de passe que inicia a cadeia segura de maior valor ate o
    jogador mais perto do gol, ou None (=> conduzir). MPC: so a 1a perna e'
    devolvida; replaneja no proximo turno. Profundidade por pass_lookahead.
    game_aggr (Comp 3, [-1,1]): perseguir (>0) reduz a margem p/ acionar planos
    de avanco; proteger (<0) a aumenta. 0 => sem efeito."""
    depth = 3 if P.get("pass_lookahead") == "depth3" else 2
    beam = int(round(P["plan_beam"]))
    control_opts = (False, True) if P.get("pass_control") == "on" else (False,)
    recv = [m for m in mates if m.number != GK_NUMBER]

    bvx = ball.velocity.direction.x
    bvy = ball.velocity.direction.y
    n = math.hypot(bvx, bvy)
    if n > 0 and ball.velocity.speed > 0:
        bvx, bvy = bvx / n * ball.velocity.speed, bvy / n * ball.velocity.speed
    else:
        bvx = bvy = 0.0

    hold_value = node_value(me.position.x, me.position.y, opponents, opp_gk,
                            goal_center)
    best_first = None
    # so passa se superar segurar; perseguir (game_aggr>0) reduz a margem,
    # proteger (game_aggr<0) a aumenta (Componente 3).
    best_val = hold_value + P["plan_margin_value"] * max(0.0, 1.0 - game_aggr)

    # no = (px, py, bvx, bvy, theta, first_leg, used_set)
    frontier = [(me.position.x, me.position.y, bvx, bvy, 0.0, None, frozenset())]
    for _ in range(depth):
        nxt = []
        for (px, py, cbx, cby, theta, first, used) in frontier:
            for mate in recv:
                if mate.number in used:
                    continue
                for control in control_opts:
                    leg = _make_leg(px, py, cbx, cby, theta, mate, opponents,
                                    control, use_velocity)
                    if leg is None:
                        continue
                    tgt, kick, nx, ny, nbx, nby, nth = leg
                    child_first = first or (tgt, kick)
                    tv = (node_value(nx, ny, opponents, opp_gk, goal_center)
                          - P["plan_leg_penalty"] * nth)
                    if tv > best_val:
                        best_val, best_first = tv, child_first
                    nxt.append((nx, ny, nbx, nby, nth, child_first,
                                used | {mate.number}, tv))
        if not nxt:
            break
        nxt.sort(key=lambda c: c[7], reverse=True)
        frontier = [c[:7] for c in nxt[:beam]]
    return best_first
