#!/usr/bin/env python3
"""
Avalia um bot em uma série de partidas e reporta o placar agregado.

  python3 evaluate.py --home mybot:v2 --away lugobots/the-dummies-go:latest -n 4

Joga metade das partidas com os lados trocados, porque HOME e AWAY não são
simétricos na prática (posições iniciais, ordem de processamento das ordens).
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "analysis"))
import replay  # noqa: E402


def run(home, away, match_id):
    out = subprocess.run(
        [str(HERE / "run_match.sh"), home, away, match_id],
        capture_output=True, text=True, timeout=1800)
    if out.returncode != 0:
        print(f"  ERRO em {match_id}: {out.stderr[-400:]}")
        return None
    return out.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="mybot:v1")
    ap.add_argument("--away", default="lugobots/the-dummies-go:latest")
    ap.add_argument("-n", type=int, default=2, help="partidas por lado")
    a = ap.parse_args()

    results = []
    for i in range(a.n):
        for swap in (False, True):
            h, aw = (a.away, a.home) if swap else (a.home, a.away)
            mid = f"eval_{i}_{'swap' if swap else 'norm'}"
            print(f"[{mid}] {h} (home) vs {aw} (away) ...", flush=True)
            path = run(h, aw, mid)
            if not path or not Path(path).exists():
                continue
            st, cfg = replay.analyze(path)
            # normaliza para a perspectiva do bot testado
            if swap:
                mine, theirs = st.goals_away, st.goals_home
                poss = 100 - st.possession_pct_home
            else:
                mine, theirs = st.goals_home, st.goals_away
                poss = st.possession_pct_home
            results.append((mine, theirs, poss))
            print(f"    -> {mine} x {theirs}  (posse {poss:.0f}%)")

    if not results:
        print("nenhuma partida completou")
        return
    gf = sum(r[0] for r in results)
    ga = sum(r[1] for r in results)
    w = sum(1 for r in results if r[0] > r[1])
    d = sum(1 for r in results if r[0] == r[1])
    l = sum(1 for r in results if r[0] < r[1])
    poss = sum(r[2] for r in results) / len(results)
    print(f"\n=== {len(results)} partidas: {w}V {d}E {l}D | "
          f"gols {gf}-{ga} | posse média {poss:.0f}% ===")


if __name__ == "__main__":
    main()
