#!/usr/bin/env python3
"""A/B de combinações arbitrárias de BOT_PARAMS vs um baseline, em wait, com
teste de significância. Serve para triar genes estruturais (mudam a lógica)
ou contínuos, sem rebuild de imagem.

  python3 bench/ab_params.py --reps 6 --opp lugobots/level-1:latest \
      v9='{}' carry_touch='{"carry_mode":"touch"}' zone='{"role_mode":"zone"}'

O PRIMEIRO braço é o baseline; os demais são comparados a ele.
"""
import argparse
import os
import statistics
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))


def evalg(genome_json, reps, opp, mode, parallel, tag):
    r = subprocess.run(["./eval_genome.sh", genome_json, str(reps), opp, mode,
                        str(parallel), tag],
                       cwd=HERE, capture_output=True, text=True, timeout=10800)
    out = []
    for t in r.stdout.split():
        try:
            out.append(int(t))
        except ValueError:
            pass
    return out


def st(s):
    if not s:
        return 0.0, 0.0, 0.0
    m = statistics.mean(s)
    sd = statistics.stdev(s) if len(s) > 1 else 0.0
    return m, sd, sd / (len(s) ** 0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+", help="label=json_compacto (1o = baseline)")
    ap.add_argument("--reps", type=int, default=6)
    ap.add_argument("--opp", default="lugobots/level-1:latest")
    ap.add_argument("--mode", default="wait")
    ap.add_argument("--parallel", type=int, default=3)
    a = ap.parse_args()

    arms = [spec.split("=", 1) for spec in a.specs]
    results = {}
    for label, gj in arms:
        s = evalg(gj, a.reps, a.opp, a.mode, a.parallel, f"ab_{label}")
        results[label] = s
        m, sd, se = st(s)
        print(f"{label:16} saldo {m:+.2f} (std {sd:.2f}, n={len(s)})  {s}", flush=True)

    base_label = arms[0][0]
    bs = results[base_label]
    bm, bsd, bse = st(bs)
    print(f"\n--- diferenca vs {base_label} (baseline saldo {bm:+.2f}) ---", flush=True)
    for label, _ in arms[1:]:
        cs = results[label]
        cm, csd, cse = st(cs)
        se = (cse ** 2 + bse ** 2) ** 0.5 or 1e-9
        d = cm - bm
        verd = ("MELHOR" if d > 1.96 * se
                else ("PIOR" if d < -1.96 * se
                      else f"nao conclusivo (detectaria >{1.96 * se:.2f})"))
        print(f"  {label:16} {d:+.2f} (erro padrao {se:.2f})  {verd}", flush=True)


if __name__ == "__main__":
    main()
