#!/usr/bin/env python3
"""Forense da decisao de passe: reconstroi _best_pass (com os genes da Fase A)
sobre um turno do replay e explica por que cada companheiro foi aceito/rejeitado.

Modos:
  why_pass.py <replay> timeline <t0> <t1>      # linha do tempo de posse
  why_pass.py <replay> decide <T>              # analisa a decisao do portador em T

Le os genes de BOT_PARAMS (mesmos do jogo). Lado NOSSO = HOME.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "analysis"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "bot", "src"))
import replay as R
import geometry as geo
from params import P

GK = 1
MAXKR = geo.MAX_KICK_RANGE
GOAL = geo.point(20000, 5000)          # HOME ataca +X
USE_VEL = (P.get("use_velocity") == "on")


class D:  # objeto leve com atributos pontilhados que geometry.py espera
    def __init__(self, **k): self.__dict__.update(k)


def vel_of(d):
    v = d.get("velocity") or {}
    dr = v.get("direction") or {}
    return D(direction=D(x=dr.get("x", 0.0), y=dr.get("y", 0.0)),
             speed=v.get("speed", 0.0))


def player_obj(p):
    x, y = R.pt(p.get("position"))
    return D(number=p.get("number", 0), position=D(x=x, y=y), velocity=vel_of(p))


def ball_obj(gs):
    bx, by = R.ball_pos(gs)
    return D(position=D(x=bx, y=by), velocity=vel_of(R.ball(gs)))


def listening_at(events, T):
    best = None
    for gs in R.snapshots(events):
        if gs.get("turn", 0) == T:
            best = gs
            if gs.get("state") == "LISTENING":
                return gs
    return best


def pressure_on(pos, opps):
    s = 0.0
    for o in opps:
        d = geo.dist(pos, o.position)
        if d < P["pressure_radius"]:
            s += (P["pressure_radius"] - d) / P["pressure_radius"]
    return s


def analyze(gs):
    hold = R.holder(gs)
    if not hold or hold[0] != "HOME":
        print(f"  (turno {gs.get('turn')}: portador nao e HOME: {hold})")
        return
    hnum = hold[1]
    home = [player_obj(p) for p in R.players(gs, "home")]
    opps = [player_obj(p) for p in R.players(gs, "away")]
    me = next(p for p in home if p.number == hnum)
    ball = ball_obj(gs)
    mates = [p for p in home if p.number != hnum]
    my_gain = geo.dist(me.position, GOAL)
    pressure = pressure_on(me.position, opps)

    print(f"== turno {gs.get('turn')}: portador HOME #{hnum} "
          f"pos=({me.position.x:.0f},{me.position.y:.0f}) "
          f"pressao={pressure:.2f}  d_gol={my_gain:.0f} ==")
    print(f"   genes: endpoint_race={P.get('pass_endpoint_race')} "
          f"exec_speed={P.get('pass_exec_speed')} "
          f"touch_lead={P.get('pass_touch_lead')} "
          f"use_velocity={P.get('use_velocity')} "
          f"pass_w_intercept={P['pass_w_intercept']}")
    hdr = (f"  {'#':>2} {'dist':>6} {'d_gol':>6} {'avanco':>7} {'veto':>16} "
           f"{'folga':>6} {'presRx':>6} {'score':>9}  status")
    print(hdr)
    rows = []
    for mate in sorted(mates, key=lambda m: m.number):
        num = mate.number
        d = geo.dist(me.position, mate.position)
        tag = ""
        if num == GK:
            print(f"  {num:>2} {'-':>6} (goleiro: ignorado)"); continue
        if d < P["pass_min_dist"] or d > MAXKR:
            rng = "curto" if d < P["pass_min_dist"] else "LONGE>8000"
            print(f"  {num:>2} {d:>6.0f} {'':>6} {'':>7} {'FORA_ALCANCE':>16} "
                  f"{'':>6} {'':>6} {'':>9}  ({rng})")
            continue
        speed = min(geo.BALL_MAX_SPEED,
                    geo.speed_for_distance(d) * P["pass_speed_mult"])
        d_reach = d
        if P.get("pass_touch_lead") == "on":
            d_reach = max(1.0, d - geo.TOUCH_RADIUS)
        t_ball = geo.turns_for_ball(speed, d_reach)
        if t_ball == math.inf:
            print(f"  {num:>2} {d:>6.0f} nao alcanca"); continue
        target = geo.lead_target(mate, t_ball)

        kick_speed = speed
        if P.get("pass_exec_speed") == "on":
            v_exec = geo.achievable_shot_speed(None, me, ball, target)
            kick_speed = min(speed, v_exec)

        veto = "ok"
        # endpoint race
        if P.get("pass_endpoint_race") == "on":
            t_recv = geo.turns_for_player(geo.dist(mate.position, target))
            worst = min((geo.turns_for_player(geo.dist(o.position, target))
                         for o in opps), default=math.inf)
            if worst <= t_recv + P["pass_endpoint_margin"]:
                veto = "ENDPOINT_RACE"
        # veto de interceptacao (default: opponent_can_intercept 8 amostras)
        if veto == "ok":
            if P["pass_w_intercept"] > 0.0:
                if geo.intercept_risk(me.position, target, opps, kick_speed, USE_VEL) <= 0:
                    veto = "INTERCEPT"
            elif geo.can_be_intercepted(me.position, target, opps, kick_speed, USE_VEL):
                veto = "INTERCEPT"

        mate_gain = geo.dist(target, GOAL)
        advance = my_gain - mate_gain
        clearance = geo.lane_clearance(me.position, target, opps)
        mate_pressure = pressure_on(mate.position, opps)
        near_opp = min((geo.dist(mate.position, o.position) for o in opps), default=9e9)
        score = (advance
                 + P["pass_w_clearance"] * clearance
                 - P["pass_w_mate_pressure"] * mate_pressure
                 + P["pass_w_pressure_bonus"] * min(1.0, pressure / 2.0)
                 - P["pass_w_overmark"] * max(0.0, mate_pressure - P["pass_mark_threshold"]))
        okmark = veto == "ok" and score > P["pass_min_score"]
        status = ("<= ESCOLHIDO?" if okmark else
                  ("veta" if veto != "ok" else "score<=min"))
        rows.append((score if veto == "ok" else -9e18, num, veto, okmark))
        print(f"  {num:>2} {d:>6.0f} {mate_gain:>6.0f} {advance:>7.0f} {veto:>16} "
              f"{clearance:>6.0f} {mate_pressure:>6.2f} {score:>9.1f}  "
              f"{status} (advmarc<={near_opp:.0f})")
    ok = [r for r in rows if r[3]]
    if ok:
        win = max(ok, key=lambda r: r[0])
        print(f"  --> _best_pass escolheria #{win[1]} (maior score entre nao-vetados)")
    else:
        print("  --> nenhum passe aceito -> cai em condução (_carry/_touch)")


class _Q:
    def __init__(self, x, y): self.x = x; self.y = y


def trace(gs, holder_num, target_num):
    home = [player_obj(p) for p in R.players(gs, "home")]
    opps = [player_obj(p) for p in R.players(gs, "away")]
    me = next(p for p in home if p.number == holder_num)
    tgtp = next(p for p in home if p.number == target_num)
    ball = ball_obj(gs)
    d = geo.dist(me.position, tgtp.position)
    speed = min(geo.BALL_MAX_SPEED, geo.speed_for_distance(d) * P["pass_speed_mult"])
    d_reach = max(1.0, d - geo.TOUCH_RADIUS) if P.get("pass_touch_lead") == "on" else d
    t_ball_total = geo.turns_for_ball(speed, d_reach)
    target = geo.lead_target(tgtp, t_ball_total)
    kick = speed
    if P.get("pass_exec_speed") == "on":
        kick = min(speed, geo.achievable_shot_speed(None, me, ball, target))
    print(f"== t={gs.get('turn')} #{holder_num}->#{target_num}: dist={d:.0f} "
          f"alvo_lead=({target.x:.0f},{target.y:.0f}) speed_plan={speed:.0f} "
          f"kick_executado={kick:.0f} ==")
    t_recv = geo.turns_for_player(geo.dist(tgtp.position, target))
    er = sorted((geo.turns_for_player(geo.dist(o.position, target)), o.number) for o in opps)
    print(f"  ENDPOINT: receptor chega ao destino em t_recv={t_recv:.1f}; "
          f"adv mais rápido ao destino: #{er[0][1]} em {er[0][0]:.1f} "
          f"(veta se <= {t_recv + P['pass_endpoint_margin']:.1f})")
    total = geo.dist(me.position, target)
    print("  INTERCEPÇÃO (8 amostras da linha; veta se t_opp <= t_ball):")
    culprit = None
    for i in range(1, 9):
        frac = i / 8; db = total * frac
        px = me.position.x + (target.x - me.position.x) * frac
        py = me.position.y + (target.y - me.position.y) * frac
        if db < geo.NO_BLOCK_NEAR_ORIGIN:
            print(f"    {frac:4.2f} d_ball={db:5.0f}  (<700, ignorado)"); continue
        tb = geo.turns_for_ball(kick, db)
        q = _Q(px, py)
        dopp, onum = sorted((geo.dist(q, o.position), o.number) for o in opps)[0]
        topp = geo.turns_for_player(dopp)
        flag = ""
        if topp <= tb:
            flag = "  <<< INTERCEPTA"
            if culprit is None:
                culprit = (frac, onum, dopp, topp, tb)
        print(f"    {frac:4.2f} ponto=({px:5.0f},{py:5.0f}) d_ball={db:5.0f} "
              f"t_ball={tb:5.1f} | adv#{onum} d={dopp:5.0f} t_opp={topp:4.1f}{flag}")
    if culprit:
        print(f"  => VETO por interceptação: adv#{culprit[1]} alcança "
              f"{culprit[0]*100:.0f}% da linha em {culprit[3]:.1f} turnos; "
              f"a bola só chega lá em {culprit[4]:.1f} turnos.")
    else:
        print("  => nenhuma amostra interceptável; se vetou, foi ENDPOINT_RACE.")


def main():
    path, mode = sys.argv[1], sys.argv[2]
    _cfg, events = R.load(path)
    if mode == "timeline":
        t0, t1 = int(sys.argv[3]), int(sys.argv[4])
        seen = set(); prev = None
        for gs in R.snapshots(events):
            t = gs.get("turn", 0)
            if t < t0 or t > t1 or t in seen:
                continue
            seen.add(t)
            h = R.holder(gs)
            bx, by = R.ball_pos(gs)
            tag = ""
            if h != prev:
                tag = "  <-- troca de posse"
            hh = "solta" if not h else f"{h[0][0]}#{h[1]}"
            print(f"  t={t:<5} posse={hh:<7} bola=({bx:.0f},{by:.0f}){tag}")
            prev = h
    elif mode == "decide":
        T = int(sys.argv[3])
        gs = listening_at(events, T)
        if gs is None:
            print("turno nao encontrado"); return
        analyze(gs)
    elif mode == "trace":
        T, hn, tn = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        gs = listening_at(events, T)
        if gs is None:
            print("turno nao encontrado"); return
        trace(gs, hn, tn)


if __name__ == "__main__":
    main()
