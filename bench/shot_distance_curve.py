#!/usr/bin/env python3
"""Curva conversão×distância dos NOSSOS chutes nos replays A/B de hoje.

Valida o corte hybrid_close_range com dados reais: onde a conversão morre
por oponente (level-1 fraco vs sparring GK-forte), e o que o hybrid teria
cortado. Uso: python shot_distance_curve.py <glob-de-replays> [label]
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import metrics_lab as M          # noqa: E402
import proxy_metric as PM        # noqa: E402

BINS = [(0, 2000), (2000, 2600), (2600, 3200), (3200, 3800),
        (3800, 4500), (4500, 6000), (6000, 99999)]


def side_of(path):
    return "home" if "_home_" in os.path.basename(path) else "away"


def main():
    pats = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else pats
    files = sorted(glob.glob(pats))
    if not files:
        print(f"nenhum replay casa com {pats}")
        return
    shots = []
    for f in files:
        try:
            d = PM.build_d(f)
            ev, _ = M.mark_shots(d, side_of(f))
            shots += [e for e in ev if e.get("on_goal")]
        except Exception as ex:
            print(f"  pulei {os.path.basename(f)}: {ex}")
    n = len(shots)
    g = sum(e["goal"] for e in shots)
    print(f"\n== {label}: {len(files)} replays, {n} chutes on-goal, "
          f"{g} gols (conv. {100.0*g/max(1,n):.1f}%) ==")
    print(f"{'faixa d':>12} {'chutes':>7} {'gols':>5} {'conv%':>6}  cum_gols_alem")
    for lo, hi in BINS:
        b = [e for e in shots if lo <= e["dist_line"] < hi]
        bg = sum(e["goal"] for e in b)
        beyond = sum(e["goal"] for e in shots if e["dist_line"] >= lo)
        print(f"{lo:>5}-{hi:<6} {len(b):>7} {bg:>5} "
              f"{100.0*bg/max(1,len(b)):>5.1f}%  (gols com d>={lo}: {beyond})")
    for cut in (2600, 3200, 3800, 4500):
        cut_n = sum(1 for e in shots if e["dist_line"] > cut)
        cut_g = sum(e["goal"] for e in shots if e["dist_line"] > cut)
        print(f"corte em {cut}: cortaria {cut_n}/{n} chutes "
              f"({100.0*cut_n/max(1,n):.0f}%) e {cut_g}/{g} gols")


if __name__ == "__main__":
    main()
