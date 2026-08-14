#!/usr/bin/env python3
"""A/B do Componente 2 (planejador nao-guloso). Base = Fase A LIGADA nos dois
bracos (config de producao), MESMA imagem mybot:qp:

  base = Fase A on, pass_lookahead off
  plan = Fase A on + pass_lookahead=depth2 + pass_control=on

Etapa 0 mostrou que a completude ja esta no teto com a Fase A; o valor do
planejador e' PROGRESSAO / selecao de caminho. Primaria: proxy_metric
(good_chance_rate, danger_poss, best_slack, gols). Guarda: turnover
(frente2_possession) nao pode subir.

Uso: .venv/bin/python bench/ab_plan.py --reps 6 --parallel 4 --opp rival_p3:latest
"""
import argparse
import concurrent.futures as cf
import contextlib
import io
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import frente2_possession as FP   # noqa: E402
import proxy_metric as PM         # noqa: E402

FA = '"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on"'
ARMS = {
    "base": "{" + FA + "}",
    "plan": "{" + FA + ',"pass_lookahead":"depth2","pass_control":"on"}',
}
ARM_ORDER = ("base", "plan")


def short(opp):
    return re.sub(r"[^a-z0-9]+", "", opp.split("/")[-1].split(":")[0].lower())[:10]


def run_match(opp, arm, rep, side):
    genome = ARMS[arm]
    mid = f"abp2_{short(opp)}_{arm}_{side}_{rep}"
    env = dict(os.environ, TIMER_MODE="rush")
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    if side == "home":
        h, a, our = "mybot:qp", opp, "HOME"
        env["HOME_PARAMS"] = genome
    else:
        h, a, our = opp, "mybot:qp", "AWAY"
        env["AWAY_PARAMS"] = genome
    try:
        subprocess.run(["./run_match.sh", h, a, mid], cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return None
    path = os.path.join(HERE, "recordings", f"{mid}.json")
    return (opp, arm, our, path) if os.path.exists(path) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--opp", nargs="+", default=["rival_p3:latest"])
    args = ap.parse_args()

    jobs = [(opp, arm, rep, side)
            for opp in args.opp for arm in ARM_ORDER
            for rep in range(1, args.reps + 1) for side in ("home", "away")]
    print(f"A/B planejador: {len(jobs)} partidas | opp={args.opp} | "
          f"{args.reps} reps x 2 lados x 2 bracos | paralelo={args.parallel}", flush=True)

    paths = {a: [] for a in ARM_ORDER}
    causa = {a: Counter() for a in ARM_ORDER}
    nposs = {a: 0 for a in ARM_ORDER}
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = [ex.submit(run_match, *j) for j in jobs]
        for f in cf.as_completed(futs):
            done += 1
            res = f.result()
            if res is None:
                print(f"[{done}/{len(jobs)}] FALHOU", flush=True)
                continue
            opp, arm, our, path = res
            paths[arm].append(path)
            with contextlib.redirect_stdout(io.StringIO()):
                R = FP.analyze(path, our, os.path.basename(path))
            ours = [p for p in R["poss"] if p["side"] == our]
            causa[arm].update(p["causa"] for p in ours)
            nposs[arm] += len(ours)
            print(f"[{done}/{len(jobs)}] {short(opp)} {arm} {our}: {len(ours)} posses",
                  flush=True)

    print("=" * 72)
    for a in ARM_ORDER:
        n = nposs[a] or 1
        c = causa[a]
        turnover = c["conducao tomada"] + c["passe interceptado"]
        m = PM.summarize(paths[a]) if paths[a] else None
        print(f"--- {a} : {nposs[a]} posses, {len(paths[a])} replays ---")
        if m:
            print(f"    good_chance_rate={m['good_chance_rate']:.3f}  "
                  f"danger_poss={m['danger_poss']}  best_slack={m['best_slack_mean']:+.1f}  "
                  f"chances_boas={m['good_chances']}  gols={m['goals_mean']:.2f}/{m['conceded_mean']:.2f}")
        print(f"    TURNOVER(cond+intercept)={100*turnover/n:.1f}%  "
              f"(cond {100*c['conducao tomada']/n:.1f}%, intercept {100*c['passe interceptado']/n:.1f}%)  "
              f"GOL={100*c['GOL']/n:.1f}%")


if __name__ == "__main__":
    main()
