#!/usr/bin/env python3
"""Etapa 0 (Experimento-decisor) do plano "quando passar": ablacao do gene
pass_exec_speed. Dois bracos na MESMA imagem mybot:fa (isola o efeito do gene):

  execoff = pass_endpoint_race+pass_touch_lead ON, pass_exec_speed OFF
  allon   = os 3 ON

Pergunta: o pass_exec_speed (que veta o passe pela velocidade REALMENTE
executavel, apoiado no modelo inferido _apply_server_kick) esta super-vetando
redirects (first-touch) e custando PROGRESSAO? Mede-se por braco:
  - COMPLETUDE do passe (analysis/frente2c_gate): acerto_resolvido, perda_p/adv.
  - PROGRESSAO/CHANCE (bench/proxy_metric): good_chance_rate, danger_poss,
    best_slack, gols.

Leitura (decide a complexidade do Componente 2):
  execoff mantem completude E melhora progressao => first-touch e' BRANDO, o
    modelo super-veta => planejador posicao-pura (sem estado-da-bola/controle).
  execoff piora => first-touch e' REAL => estado-da-bola + aresta de controle
    sao essenciais.
  ambiguo => medir o penalty de redirect direto antes de investir.

Uso: .venv/bin/python bench/ab_ablation_exec.py --reps 4 --parallel 4 \
        --opp rival_p3 lugobots/level-1:latest
"""
import argparse
import concurrent.futures as cf
import contextlib
import glob
import io
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import frente2c_gate as G     # noqa: E402
import proxy_metric as PM     # noqa: E402

ARMS = {
    "execoff": '{"pass_endpoint_race":"on","pass_touch_lead":"on"}',
    "allon": ('{"pass_endpoint_race":"on","pass_exec_speed":"on",'
              '"pass_touch_lead":"on"}'),
}
ARM_ORDER = ("execoff", "allon")


def short(opp):
    return re.sub(r"[^a-z0-9]+", "", opp.split("/")[-1].split(":")[0].lower())[:10]


def run_match(opp, arm, rep, side):
    genome = ARMS[arm]
    mid = f"abx_{short(opp)}_{arm}_{side}_{rep}"
    env = dict(os.environ, TIMER_MODE="rush")
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    if side == "home":
        h, a, our = "mybot:fa", opp, "HOME"
        env["HOME_PARAMS"] = genome
    else:
        h, a, our = opp, "mybot:fa", "AWAY"
        env["AWAY_PARAMS"] = genome
    try:
        subprocess.run(["./run_match.sh", h, a, mid], cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return None
    path = os.path.join(HERE, "recordings", f"{mid}.json")
    return (opp, arm, our, path) if os.path.exists(path) else None


def report_completeness(agg):
    print("--- COMPLETUDE DO PASSE (frente2c_gate) ---")
    for a in ARM_ORDER:
        npass, ok, bad = agg[a]
        res = ok + bad
        r2 = 100.0 * ok / res if res else 0.0
        lost = 100.0 * bad / npass if npass else 0.0
        print(f"  {a:<8} passes={npass:>5} ok={ok:>5} adv={bad:>4}  "
              f"acerto_resolvido={r2:5.1f}%  perda_p/adv={lost:4.1f}%")
    o_np, o_ok, o_bad = agg["execoff"]
    n_np, n_ok, n_bad = agg["allon"]
    o_res, n_res = o_ok + o_bad, n_ok + n_bad
    if o_res and n_res:
        p1, p2 = o_ok / o_res, n_ok / n_res
        p = (o_ok + n_ok) / (o_res + n_res)
        se = math.sqrt(p * (1 - p) * (1 / o_res + 1 / n_res))
        z = (p1 - p2) / se if se else 0.0   # execoff - allon
        sig = "SIG" if abs(z) > 1.96 else "n/s"
        print(f"  delta acerto (execoff-allon) = {100*(p1-p2):+.2f} pp  "
              f"(z={z:.2f}, {sig})")


def report_progression(paths_by_arm):
    print("--- PROGRESSAO / CRIACAO DE CHANCE (proxy_metric) ---")
    for a in ARM_ORDER:
        paths = paths_by_arm[a]
        if not paths:
            print(f"  {a:<8} (sem replays)")
            continue
        m = PM.summarize(paths)
        print(f"  {a:<8} n={m['n_replays']:>2}  "
              f"good_chance_rate={m['good_chance_rate']:.3f}  "
              f"posses-perigo={m['danger_poss']:>4}  "
              f"best_slack={m['best_slack_mean']:+7.1f}  "
              f"gols={m['goals_mean']:.2f}/{m['conceded_mean']:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--opp", nargs="+", default=["rival_p3:latest"])
    args = ap.parse_args()

    jobs = [(opp, arm, rep, side)
            for opp in args.opp
            for arm in ARM_ORDER
            for rep in range(1, args.reps + 1)
            for side in ("home", "away")]
    print(f"ABLACAO exec_speed: {len(jobs)} partidas | oponentes={args.opp} | "
          f"{args.reps} reps x 2 lados x 2 bracos | paralelo={args.parallel}",
          flush=True)

    def z0():
        return {"execoff": [0, 0, 0], "allon": [0, 0, 0]}
    per_opp = {opp: z0() for opp in args.opp}
    overall = z0()
    paths_by_arm = {"execoff": [], "allon": []}
    paths_by_opp_arm = {opp: {"execoff": [], "allon": []} for opp in args.opp}
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
                r = G.run(path, our, os.path.basename(path))
            for tgt in (per_opp[opp][arm], overall[arm]):
                tgt[0] += r["npass"]
                tgt[1] += r["okp"]
                tgt[2] += r["badp"]
            paths_by_arm[arm].append(path)
            paths_by_opp_arm[opp][arm].append(path)
            print(f"[{done}/{len(jobs)}] {short(opp)} {arm} {our}: "
                  f"+{r['npass']} passes (+{r['okp']} ok, +{r['badp']} adv)",
                  flush=True)

    print("=" * 72)
    for opp in args.opp:
        print(f"### {short(opp)} ###")
        report_completeness(per_opp[opp])
        report_progression(paths_by_opp_arm[opp])
    print("### GERAL ###")
    report_completeness(overall)
    report_progression(paths_by_arm)


if __name__ == "__main__":
    main()
