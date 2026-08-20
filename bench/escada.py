#!/usr/bin/env python3
"""ESCADA DE GOLEADA — mede o TETO ofensivo contra os bots oficiais.

Regra do usuário (18/08): fazer 10×0 EM REGRA contra o level-1; alcançado,
sobe-se o degrau (mais tempo/teto) para simular adversário mais forte.

Adaptação necessária: o servidor NÃO tem flag de duração (6000 turnos é
fixo). O que ele tem é `--knockout-score-diff` (default 10 = a regra de
misericórdia oficial, que encerra o jogo). Então a escada vira RITMO DE GOL
na partida de 6000 turnos, que é equivalente a "mais gols em mais tempo":

  degrau 1: 10 gols/partida   (= o teto oficial; ritmo 1 gol / 600 turnos)
  degrau 2: 15 gols/partida   (+50%, "com juros" sobre o ritmo)
  degrau 3: 22 gols/partida   (+50% de novo)

"EM REGRA" = mediana >= alvo E pelo menos 60% das partidas >= alvo.

Uso:
  python bench/escada.py --genome bot/genome_v8_candidate.json --n 8 \\
      --opp lugobots/level-1:latest --alvo 10
"""
import argparse
import concurrent.futures as cf
import json
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import proxy_metric as PM      # noqa: E402
import metrics_lab as M        # noqa: E402


def run_one(genome_json, opp, mid, side, timer, knockout):
    env = dict(os.environ, TIMER_MODE=timer, KNOCKOUT_DIFF=str(knockout))
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    if side == "home":
        h, a, our = "mybot:qp", opp, "HOME"
        env["HOME_PARAMS"] = genome_json
    else:
        h, a, our = opp, "mybot:qp", "AWAY"
        env["AWAY_PARAMS"] = genome_json
    try:
        subprocess.run(["./run_match.sh", h, a, mid], cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=2400)
    except subprocess.TimeoutExpired:
        return None
    path = os.path.join(HERE, "recordings", f"{mid}.json")
    return (path, our) if os.path.exists(path) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genome", required=True)
    ap.add_argument("--opp", default="lugobots/level-1:latest")
    ap.add_argument("--n", type=int, default=8, help="repetições por lado")
    ap.add_argument("--tag", default="esc")
    ap.add_argument("--alvo", type=int, default=10)
    ap.add_argument("--knockout", type=int, default=99,
                    help="teto de knockout do servidor (99 = praticamente sem)")
    ap.add_argument("--mode", default="rush", choices=["rush", "wait"])
    ap.add_argument("--parallel", type=int, default=2)
    args = ap.parse_args()

    # docker-compose REJEITA nome de projeto com maiuscula (ja custou 64
    # partidas em 18/08 e outras 16 hoje): normalizar aqui, de uma vez.
    args.tag = args.tag.lower()

    genome = open(args.genome).read().strip()
    jobs = [(genome, args.opp, f"esc_{args.tag}_{side}_{r}", side, args.mode,
             args.knockout)
            for r in range(1, args.n + 1) for side in ("home", "away")]
    print(f"ESCADA [{args.tag}] {os.path.basename(args.genome)} vs {args.opp} "
          f"| {len(jobs)} partidas | knockout={args.knockout} | alvo={args.alvo}",
          flush=True)

    results = []
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = [ex.submit(run_one, *j) for j in jobs]
        for i, f in enumerate(cf.as_completed(futs), 1):
            res = f.result()
            if res is None:
                print(f"[{i}/{len(jobs)}] FALHOU", flush=True)
                continue
            path, our = res
            try:
                d = PM.build_d(path)
                sc_our = d["sc_home"] if our == "HOME" else d["sc_away"]
                sc_opp = d["sc_away"] if our == "HOME" else d["sc_home"]
                gf, ga = int(sc_our[-1]), int(sc_opp[-1])
                ev, _ = M.mark_shots(d, our.lower())
                shots = sum(1 for e in ev if e.get("on_goal"))
                results.append((gf, ga, shots, len(d["turn"])))
                print(f"[{i}/{len(jobs)}] {gf}x{ga}  ({shots} finalizações, "
                      f"{len(d['turn'])} turnos)", flush=True)
            except Exception as e:
                print(f"[{i}/{len(jobs)}] erro na análise: {e}", flush=True)

    if not results:
        print("nenhuma partida completou")
        return
    gfs = [r[0] for r in results]
    gas = [r[1] for r in results]
    shots = [r[2] for r in results]
    med = statistics.median(gfs)
    frac = sum(1 for g in gfs if g >= args.alvo) / len(gfs)
    print("=" * 70)
    print(f"GOLS: média {statistics.mean(gfs):.2f} | mediana {med:.1f} | "
          f"min {min(gfs)} max {max(gfs)}")
    print(f"SOFRIDOS: média {statistics.mean(gas):.2f} | max {max(gas)}")
    print(f"FINALIZAÇÕES: média {statistics.mean(shots):.1f} | "
          f"conversão {100.0*statistics.mean(gfs)/max(1e-9, statistics.mean(shots)):.0f}%")
    print(f"placares: {sorted(gfs, reverse=True)}")
    ok = med >= args.alvo and frac >= 0.6
    print(f"DEGRAU {args.alvo}: mediana {med:.1f} (alvo {args.alvo}) | "
          f"{100*frac:.0f}% das partidas >= {args.alvo} (precisa 60%) "
          f"=> {'ALCANÇADO' if ok else 'NÃO alcançado'}")


if __name__ == "__main__":
    main()
