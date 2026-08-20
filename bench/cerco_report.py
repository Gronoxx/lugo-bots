#!/usr/bin/env python3
"""Painel dos braços da fila do cerco: gols, sofridos e CHUTES CURTOS.

Métrica primária = chutes on-goal com d<=3200/jogo. Justificativa (20/08):
73% das nossas chances curtas nascem de rebote do GK adversário, e a curva
conversão×distância mostra que só o chute curto rende (40-53% vs 5% acima de
3800). Chute curto é denso (dezenas por jogo) e por isso muito menos ruidoso
que gol.

Uso: python3 bench/cerco_report.py esc_c_base esc_c_camp ...
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


def arm(prefix):
    files = sorted(glob.glob(os.path.join(HERE, "recordings", prefix + "_*.json")))
    rows = []
    for path in files:
        try:
            d = PM.build_d(path)
        except Exception:
            continue
        side = "home" if "_home_" in os.path.basename(path) else "away"
        our = "HOME" if side == "home" else "AWAY"
        sc_our = d["sc_home"] if our == "HOME" else d["sc_away"]
        sc_opp = d["sc_away"] if our == "HOME" else d["sc_home"]
        ev, _ = M.mark_shots(d, side)
        sh = [e for e in ev if e.get("on_goal")]
        rows.append(dict(
            gf=int(sc_our[-1]), ga=int(sc_opp[-1]), fin=len(sh),
            c26=sum(1 for e in sh if e["dist_line"] <= 2600),
            c32=sum(1 for e in sh if e["dist_line"] <= 3200),
            longe=sum(1 for e in sh if e["dist_line"] > 3800),
            gols_curto=sum(1 for e in sh if e.get("goal") and e["dist_line"] <= 3200),
        ))
    return rows


def main():
    print(f"{'braço':14s} {'n':>3s} {'gf':>5s} {'ga':>5s} {'fin':>5s} "
          f"{'<=2600':>7s} {'<=3200':>7s} {'>3800':>6s} {'conv%':>6s} {'V/E/D':>9s}")
    print("-" * 84)
    for pref in sys.argv[1:]:
        r = arm(pref)
        if not r:
            print(f"{pref:14s}  (sem replays)")
            continue
        m = lambda k: float(np.mean([x[k] for x in r]))
        V = sum(1 for x in r if x["gf"] > x["ga"])
        E = sum(1 for x in r if x["gf"] == x["ga"])
        D = sum(1 for x in r if x["gf"] < x["ga"])
        conv = 100.0 * m("gf") / max(1e-9, m("fin"))
        print(f"{pref.replace('esc_c_',''):14s} {len(r):3d} {m('gf'):5.2f} {m('ga'):5.2f} "
              f"{m('fin'):5.1f} {m('c26'):7.1f} {m('c32'):7.1f} {m('longe'):6.1f} "
              f"{conv:6.1f} {V}/{E}/{D}")


if __name__ == "__main__":
    main()
