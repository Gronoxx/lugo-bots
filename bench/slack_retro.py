#!/usr/bin/env python3
"""Retro-análise do ramo LONGE do gate hybrid nos replays existentes.

Para cada chute on-goal com dist_line > CUT (3200), recomputa a decisão do
GATE (slack = |ycross-gk_y| - (560 + v*t_ball400)) para vários gk_reach_speed
e cruza com o resultado real (gol/defesa). Responde: o slack-75 aprova
estéreis que um slack mais duro negaria? E quanto custaria vs level-1?
Uso: python slack_retro.py <glob> <label>
"""
import glob
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import numpy as np                # noqa: E402
import metrics_lab as M          # noqa: E402
import proxy_metric as PM        # noqa: E402

CUT = 3200.0
SPEEDS = (75.0, 100.0, 120.0, 140.0)


def side_of(path):
    return "home" if "_home_" in os.path.basename(path) else "away"


def main():
    files = sorted(glob.glob(sys.argv[1]))
    label = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    rows = []
    for f in files:
        try:
            d = PM.build_d(f)
            side = side_of(f)
            onum, oy = ("anum", "ay") if side == "home" else ("hnum", "hy")
            ev, _ = M.mark_shots(d, side)
            for e in ev:
                if not e.get("on_goal") or e["dist_line"] is None:
                    continue
                if e["dist_line"] <= CUT:
                    continue
                t = PM.turns_for_ball(400.0, e["dist_line"])
                if t == math.inf:
                    continue
                j = e["i"]
                k = np.where(d[onum][j] == 1)[0]
                gk_y = float(d[oy][j, k[0]]) if len(k) else 5000.0
                gap = abs(e["ycross"] - gk_y)
                rows.append(dict(gap=gap, t=t, goal=e["goal"]))
        except Exception as ex:
            print(f"  pulei {os.path.basename(f)}: {ex}")
    n = len(rows)
    g = sum(r["goal"] for r in rows)
    print(f"\n== {label}: {n} chutes LONGE (d>{CUT:.0f}) on-goal, {g} gols ==")
    print(f"{'gk_speed':>9} {'aprova':>7} {'%':>5} {'gols_aprov':>10} {'nega':>5} {'gols_negados':>12}")
    for v in SPEEDS:
        ap = [r for r in rows if r["gap"] - (560.0 + v * r["t"]) > 0.0]
        ng = n - len(ap)
        ga = sum(r["goal"] for r in ap)
        print(f"{v:>9.0f} {len(ap):>7} {100.0*len(ap)/max(1,n):>4.0f}% "
              f"{ga:>10} {ng:>5} {g-ga:>12}")


if __name__ == "__main__":
    main()
