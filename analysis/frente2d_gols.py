#!/usr/bin/env python3
"""
FRENTE 2d — de onde vieram os gols e o que abriria o portão do chute.

(1) Para cada gol nosso: o último chute nosso antes dele (distância, v0, se o
    portão do bot estaria aberto naquele turno). Serve para validar o detector
    de finalização e para saber se marcamos "de propósito" ou de rebote.
(2) Contrafactuais do portão: quanto ele abriria se
      A) ignorássemos os 2 primeiros pontos de amostragem (adversário colado
         no chutador, que na prática está ATRÁS da bola);
      B) só considerássemos adversários À FRENTE (projeção >= 0.25 da linha);
      C) usássemos margem geométrica (450d da linha) em vez do teste temporal.
"""
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frente2_possession import (MATCHES, REC, MAX_X, GOAL_MIN_Y, GOAL_MAX_Y,
                                load_turns, detect_kicks, classify_kick,
                                segment_possessions, dist, seg_point_dist, pct)
from frente2c_gate import (turns_for_ball, turns_for_player, gate,
                           BALL_MAX_SPEED, GK_HALF, GK_JUMP_SPEED,
                           GK_JUMP_DUR, PLAYER_SPEED, GOALKEEPER,
                           SHOT_POST_MARGIN, SHOT_RANGE, MAX_KICK_RANGE)


def gate_variant(me, opps, gk, goal_x, mode):
    for i in range(9):
        frac = i / 8
        y = GOAL_MIN_Y + SHOT_POST_MARGIN + frac * (
            GOAL_MAX_Y - GOAL_MIN_Y - 2 * SHOT_POST_MARGIN)
        target = (goal_x, y)
        d = dist(me, target)
        if d > MAX_KICK_RANGE:
            continue
        if _blocked(me, target, opps, mode):
            continue
        t_ball = turns_for_ball(BALL_MAX_SPEED, d)
        if t_ball == math.inf:
            continue
        if gk is not None:
            jt = min(t_ball, GK_JUMP_DUR)
            reach = GK_JUMP_SPEED * jt + PLAYER_SPEED * max(0, t_ball - jt)
            if dist(gk, target) - GK_HALF <= reach:
                continue
        return True
    return False


def _blocked(origin, target, opps, mode):
    total = dist(origin, target)
    if total == 0:
        return False
    if mode == "C":                     # margem geométrica
        for o in opps:
            # só conta quem está entre o chutador e o alvo
            ax, ay = origin
            bx, by = target
            t = ((o[0]-ax)*(bx-ax) + (o[1]-ay)*(by-ay)) / (total*total)
            if 0.05 <= t <= 1.0 and seg_point_dist(origin, target, o) <= 450:
                return True
        return False
    lo = 3 if mode == "A" else 1        # A: pula os 2 primeiros pontos
    for i in range(lo, 9):
        frac = i / 8
        px = origin[0] + (target[0] - origin[0]) * frac
        py = origin[1] + (target[1] - origin[1]) * frac
        t_ball = turns_for_ball(BALL_MAX_SPEED, total * frac)
        if t_ball == math.inf:
            return True
        for o in opps:
            if mode == "B":
                ax, ay = origin
                bx, by = target
                tt = ((o[0]-ax)*(bx-ax) + (o[1]-ay)*(by-ay)) / (total*total)
                if tt < 0.25:
                    continue
            if turns_for_player(dist((px, py), o)) <= t_ball:
                return True
    return False


def run(path, our_side, label):
    turns, goals = load_turns(path)
    their = "AWAY" if our_side == "HOME" else "HOME"
    attack_x = {"HOME": MAX_X, "AWAY": 0}
    gx = attack_x[our_side]
    goal_c = (gx, 5000)
    idx_of_turn = {T["turn"]: i for i, T in enumerate(turns)}

    kicks = detect_kicks(turns)
    for k in kicks:
        k["tipo"] = classify_kick(k, turns, attack_x)
    ours = [k for k in kicks if k["side"] == our_side]

    print("=" * 78)
    print(f"{label}  ({os.path.basename(path)})")
    print("=" * 78)
    my_goals = [t for s, t in goals if s == our_side]
    print(f"gols nossos: {len(my_goals)}")
    for gt in my_goals:
        gi = idx_of_turn.get(gt, 0)
        prev = [k for k in ours if k["i"] <= gi]
        if not prev:
            print(f"  turno {gt}: nenhum chute nosso antes (?)")
            continue
        k = prev[-1]
        d = dist(k["pos"], goal_c)
        T = turns[k["i"]]
        me = T["players"][our_side].get(k["num"], k["pos"])
        opps = T["players"][their]
        ok, why, _ = gate(me, [p for n_, p in opps.items() if n_ != GOALKEEPER],
                          opps.get(GOALKEEPER), gx)
        print(f"  turno {gt}: último chute nosso no turno {turns[k['i']]['turn']} "
              f"({gt - turns[k['i']]['turn']} turnos antes), tipo={k['tipo']}, "
              f"v0={k['v0']:.0f}, dist ao gol={d:.0f}d, "
              f"portão do bot naquele instante: "
              f"{'ABERTO' if ok else 'FECHADO (' + str(why) + ')'}")

    shots = [k for k in ours if k["tipo"] == "chute"]
    if shots:
        ds = sorted(dist(k["pos"], goal_c) for k in shots)
        print(f"\nfinalizações detectadas: {len(shots)} | distância ao gol: "
              f"mediana {ds[len(ds)//2]:.0f}d, min {ds[0]:.0f}, max {ds[-1]:.0f} | "
              f"{sum(1 for d in ds if d<=6000)} dentro de 6000d")

    # contrafactuais do portão
    tot = 0
    cnt = Counter()
    for T in turns:
        h = T["holder"]
        if not h or h[0] != our_side:
            continue
        if dist(T["ball"], goal_c) > SHOT_RANGE:
            continue
        tot += 1
        me = T["players"][our_side].get(h[1], T["ball"])
        opps = T["players"][their]
        gkp = opps.get(GOALKEEPER)
        others = [p for n_, p in opps.items() if n_ != GOALKEEPER]
        ok, _, _ = gate(me, others, gkp, gx)
        if ok:
            cnt["atual"] += 1
        for mode in ("A", "B", "C"):
            if gate_variant(me, others, gkp, gx, mode):
                cnt[mode] += 1
    print(f"\nportão em {tot} turnos com bola nossa a <=6000d:")
    for m, nome in (("atual", "regra atual"),
                    ("A", "A: ignora 2 pontos junto ao chutador"),
                    ("B", "B: só adversários à frente (proj>=0.25)"),
                    ("C", "C: margem geométrica 450d")):
        print(f"  {nome:<42} aberto {cnt[m]:>5} ({pct(cnt[m], max(1,tot)):>5.1f}%)")
    print()
    return dict(label=label, tot=tot, cnt=cnt, goals=len(my_goals),
                shots=len(shots))


if __name__ == "__main__":
    sel = sys.argv[1:]
    rows = []
    for fn, side, label in MATCHES:
        if sel and not any(s in fn for s in sel):
            continue
        p = os.path.join(REC, fn)
        if os.path.exists(p):
            rows.append(run(p, side, label))
    print("=" * 100)
    print(f"{'partida':<32}{'t/zona':>8}{'atual':>9}{'A':>9}{'B':>9}{'C':>9}")
    for r in rows:
        t = max(1, r["tot"])
        print(f"{r['label']:<32}{r['tot']:>8}" +
              "".join(f"{pct(r['cnt'][m], t):>8.1f}%" for m in ("atual", "A", "B", "C")))
