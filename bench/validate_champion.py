#!/usr/bin/env python3
"""Valida o campeão da evolução vs o baseline v9, em WAIT (modo rigoroso do
torneio), com teste de significância. A busca roda em rush (ruidoso); só
acreditar num ganho se ele sobreviver a esta validação.

  python3 bench/validate_champion.py --reps 8 --opp lugobots/level-1:latest

Roda reps*2 partidas do campeão e reps*2 do baseline (mesmos genes nos
defaults) e imprime a diferença com erro padrão e veredito.
"""
import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evolve  # evaluate(), params  # noqa: E402


def stats(s):
    m = statistics.mean(s)
    sd = statistics.stdev(s) if len(s) > 1 else 0.0
    se = sd / (len(s) ** 0.5) if s else 0.0
    return m, sd, se


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--champion", default="results/evolve_champion.json")
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--opp", default="lugobots/level-1:latest")
    ap.add_argument("--mode", default="wait")
    ap.add_argument("--parallel", type=int, default=3)
    a = ap.parse_args()

    champ = json.load(open(os.path.join(HERE, a.champion)))
    champ_genome = champ["genome"]
    # os genes que o campeão carrega; o baseline usa os defaults desses mesmos
    evolve.GENES = list(champ_genome.keys())
    base_genome = {g: float(evolve.params.DEFAULTS[g]) for g in champ_genome}

    print(f"Validando campeao {champ['gid']} (busca rush: saldo "
          f"{champ['mean_saldo']} n={champ['n']}) vs baseline v9, em {a.mode}, "
          f"{a.reps * 2} partidas cada lado", flush=True)

    cs = evolve.evaluate(champ_genome, a.reps, a.opp, a.mode, a.parallel, "valchamp")
    bs = evolve.evaluate(base_genome, a.reps, a.opp, a.mode, a.parallel, "valbase")
    if not cs or not bs:
        print(f"ERRO: sem saldos suficientes (champ={cs} base={bs})")
        return

    cm, csd, cse = stats(cs)
    bm, bsd, bse = stats(bs)
    se = (cse ** 2 + bse ** 2) ** 0.5 or 1e-9
    d = cm - bm
    print(f"campeao : saldo {cm:+.2f} (std {csd:.2f}, n={len(cs)})  {cs}")
    print(f"baseline: saldo {bm:+.2f} (std {bsd:.2f}, n={len(bs)})  {bs}")
    print(f"diferenca campeao-baseline: {d:+.2f} (erro padrao {se:.2f})")
    if d > 1.96 * se:
        print("CONCLUSIVO: campeao e MELHOR que a v9")
    elif d < -1.96 * se:
        print("CONCLUSIVO: campeao e PIOR (regressao — NAO usar)")
    else:
        print(f"NAO conclusivo — este teste so detectaria diferencas > "
              f"{1.96 * se:.2f} gols. v9 provavelmente ja e forte nesses genes.")

    # salva o genoma do campeao num formato pronto p/ BOT_PARAMS
    out = os.path.join(HERE, "results", "champion_genome.json")
    json.dump(champ_genome, open(out, "w"), separators=(",", ":"))
    print(f"genoma do campeao (BOT_PARAMS) salvo em {out}")


if __name__ == "__main__":
    main()
