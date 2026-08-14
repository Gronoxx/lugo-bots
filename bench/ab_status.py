#!/usr/bin/env python3
"""A/B do Componente 1 ("quando passar" / status por jogador). Mede se ligar
pass_status_mode REDUZ o turnover de CONDUCAO (portador desarmado driblando),
convertendo-o em reciclo seguro por passe, SEM inflar passe interceptado nem
derrubar a criacao de chance. Base = Fase A LIGADA nos DOIS bracos (config de
producao), na MESMA imagem mybot:qp (que tem Fase A E o gene de status; isola o
efeito de ligar pass_status_mode):

  base   = Fase A on
  status = Fase A on + pass_status_mode on

Primaria: composicao de perda de posse (analysis/frente2_possession.analyze),
com foco em "conducao tomada" e "passe interceptado".
Guarda: proxy_metric good_chance_rate/danger_poss nao pode cair.

Uso: .venv/bin/python bench/ab_status.py --reps 5 --parallel 4 --opp rival_p3:latest
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
    "base":   "{" + FA + "}",
    "status": "{" + FA + ',"pass_status_mode":"on"}',
}
ARM_ORDER = ("base", "status")
KEYS = ["conducao tomada", "passe interceptado", "bola solta perdida",
        "chute perdido/bloqueado", "shot clock", "GOL", "fim de jogo"]


def short(opp):
    return re.sub(r"[^a-z0-9]+", "", opp.split("/")[-1].split(":")[0].lower())[:10]


def run_match(opp, arm, rep, side):
    genome = ARMS[arm]
    mid = f"abs_{short(opp)}_{arm}_{side}_{rep}"
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


def report(name, causa, nposs, paths):
    print(f"### {name} ###")
    for a in ARM_ORDER:
        n = nposs[a] or 1
        c = causa[a]
        turnover = c["conducao tomada"] + c["passe interceptado"]
        print(f"--- {a:<7} {nposs[a]} posses nossas ---")
        for k in KEYS:
            print(f"    {k:<26} {c[k]:>4}  {100*c[k]/n:5.1f}%")
        print(f"    >> TURNOVER (cond+intercept) {turnover:>4}  {100*turnover/n:5.1f}%")
        if paths[a]:
            m = PM.summarize(paths[a])
            print(f"    >> good_chance_rate={m['good_chance_rate']:.3f} "
                  f"danger_poss={m['danger_poss']} best_slack={m['best_slack_mean']:+.1f} "
                  f"gols={m['goals_mean']:.2f}/{m['conceded_mean']:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--opp", nargs="+", default=["rival_p3:latest"])
    args = ap.parse_args()

    jobs = [(opp, arm, rep, side)
            for opp in args.opp for arm in ARM_ORDER
            for rep in range(1, args.reps + 1) for side in ("home", "away")]
    print(f"A/B status: {len(jobs)} partidas | opp={args.opp} | "
          f"{args.reps} reps x 2 lados x 2 bracos | paralelo={args.parallel}", flush=True)

    causa = {a: Counter() for a in ARM_ORDER}
    nposs = {a: 0 for a in ARM_ORDER}
    paths = {a: [] for a in ARM_ORDER}
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
            with contextlib.redirect_stdout(io.StringIO()):
                R = FP.analyze(path, our, os.path.basename(path))
            ours = [p for p in R["poss"] if p["side"] == our]
            causa[arm].update(p["causa"] for p in ours)
            nposs[arm] += len(ours)
            paths[arm].append(path)
            print(f"[{done}/{len(jobs)}] {short(opp)} {arm} {our}: {len(ours)} posses",
                  flush=True)

    print("=" * 72)
    report("GERAL", causa, nposs, paths)


if __name__ == "__main__":
    main()
