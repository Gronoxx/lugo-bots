#!/usr/bin/env python3
"""DE ONDE NASCEM AS CHANCES CURTAS — auditoria da fábrica de finalização.

A curva conversão×distância (20/08) mostrou que só o chute de <2600 vale
(40–53%); acima de 3800 é doação (5%). Este relatório responde a pergunta
seguinte: a posse que termina em chute CURTO começa onde? É isso que diz qual
fábrica escalar (rebote, roubo alto, construção, reinício).

Uso: python3 bench/chance_origin.py '<glob>' [rótulo]
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import metrics_lab as M       # noqa: E402
import proxy_metric as PM     # noqa: E402

CURTO = 2600.0


def side_of(path):
    return "home" if "_home_" in os.path.basename(path) else "away"


def classify(d, side, i_shot):
    """Origem da posse que contém o turno i_shot."""
    s = 0 if side == "home" else 1
    hs = d["hold_side"]
    bx = d["bx"].astype(float)
    prog = bx if side == "home" else 20000.0 - bx
    # início da posse: recua enquanto o dono não for o adversário
    i = int(i_shot)
    j = i
    while j > 0 and hs[j - 1] != (1 - s):
        j -= 1
    p0 = prog[j]
    # rebote: o GK adversário segurou a bola nos 60 turnos anteriores ao início
    lo = max(0, j - 60)
    gk_held = bool(((hs[lo:j] == (1 - s)) & (d["hold_num"][lo:j] == 1)).any())
    if gk_held:
        return "rebote (GK deles)"
    if p0 > 13333:
        return "roubo no terço deles"
    if p0 > 10000:
        return "roubo no campo deles"
    if p0 > 6667:
        return "roubo no meio-campo"
    return "construção do nosso campo"


def main():
    files = sorted(glob.glob(sys.argv[1]))
    label = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    from collections import Counter
    tot = Counter()
    tot_goal = Counter()
    n_curto = n_gol = 0
    for path in files:
        try:
            d = PM.build_d(path)
        except Exception:
            continue
        side = side_of(path)
        ev, _ = M.mark_shots(d, side)
        for e in ev:
            if not e.get("on_goal") or e["dist_line"] > CURTO:
                continue
            n_curto += 1
            o = classify(d, side, e["i"])
            tot[o] += 1
            if e.get("goal"):
                tot_goal[o] += 1
                n_gol += 1
    print(f"== {label}: {len(files)} replays | {n_curto} chutes CURTOS (<{CURTO:.0f}) "
          f"| {n_gol} gols ==")
    print(f"{'origem da posse':28s} {'chutes':>7s} {'/jogo':>6s} {'gols':>5s} {'conv':>6s}")
    for k, v in tot.most_common():
        g = tot_goal[k]
        print(f"{k:28s} {v:7d} {v/max(1,len(files)):6.2f} {g:5d} "
              f"{100.0*g/max(1,v):5.1f}%")


if __name__ == "__main__":
    main()
