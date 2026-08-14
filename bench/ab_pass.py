#!/usr/bin/env python3
"""A/B da TAXA DE ACERTO DE PASSE: mybot:fa com os genes de Fase A OFF vs ON,
MESMA imagem (isola o efeito dos genes), vs um ou mais oponentes, alternando
lados. Metrica densa (~150-350 passes/partida) => poucas partidas ja dao IC
apertado. A extracao reusa analysis/frente2c_gate.run.

Uso: .venv/bin/python bench/ab_pass.py --reps 4 --parallel 3 \
        --opp rival_p1 rival_p3
"""
import argparse
import concurrent.futures as cf
import contextlib
import io
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import frente2c_gate as G  # noqa: E402

ARMS = {
    "off": "{}",
    "on": ('{"pass_endpoint_race":"on","pass_exec_speed":"on",'
           '"pass_touch_lead":"on"}'),
}


def short(opp):
    return re.sub(r"[^a-z0-9]+", "", opp.split("/")[-1].split(":")[0].lower())[:10]


def run_match(opp, arm, rep, side):
    """Roda UMA partida e devolve (opp, arm, our_side, replay_path) ou None."""
    genome = ARMS[arm]
    mid = f"abp_{short(opp)}_{arm}_{side}_{rep}"
    env = dict(os.environ, TIMER_MODE="rush")
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    if side == "home":
        h, a, our = "mybot:fa", opp, "HOME"
        if genome != "{}":
            env["HOME_PARAMS"] = genome
    else:
        h, a, our = opp, "mybot:fa", "AWAY"
        if genome != "{}":
            env["AWAY_PARAMS"] = genome
    try:
        subprocess.run(["./run_match.sh", h, a, mid], cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=1200)
    except subprocess.TimeoutExpired:
        return None
    path = os.path.join(HERE, "recordings", f"{mid}.json")
    return (opp, arm, our, path) if os.path.exists(path) else None


def report(name, agg):
    """agg: {arm: [npass, ok, bad]} -> imprime linha por braco + delta + z."""
    print(f"--- {name} ---")
    for a in ("off", "on"):
        npass, ok, bad = agg[a]
        res = ok + bad
        r2 = 100.0 * ok / res if res else 0.0
        lost = 100.0 * bad / npass if npass else 0.0
        print(f"  {a.upper():<4} passes={npass:>5} ok={ok:>5} adv={bad:>4}  "
              f"acerto_resolvido={r2:5.1f}%  perda_p/adv={lost:4.1f}%")
    o_np, o_ok, o_bad = agg["off"]
    n_np, n_ok, n_bad = agg["on"]
    o_res, n_res = o_ok + o_bad, n_ok + n_bad
    if o_res and n_res:
        p1, p2 = o_ok / o_res, n_ok / n_res
        p = (o_ok + n_ok) / (o_res + n_res)
        se = math.sqrt(p * (1 - p) * (1 / o_res + 1 / n_res))
        z = (p2 - p1) / se if se else 0.0
        sig = "SIG" if abs(z) > 1.96 else "n/s"
        print(f"  delta acerto (ON-OFF) = {100*(p2-p1):+.2f} pp  (z={z:.2f}, {sig})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--opp", nargs="+", default=["lugobots/level-1:latest"])
    args = ap.parse_args()

    jobs = [(opp, arm, rep, side)
            for opp in args.opp
            for arm in ("off", "on")
            for rep in range(1, args.reps + 1)
            for side in ("home", "away")]
    print(f"A/B passe: {len(jobs)} partidas | oponentes={args.opp} | "
          f"{args.reps} reps x 2 lados x 2 bracos | paralelo={args.parallel}",
          flush=True)

    def z0():
        return {"off": [0, 0, 0], "on": [0, 0, 0]}
    per_opp = {opp: z0() for opp in args.opp}
    overall = z0()
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
            print(f"[{done}/{len(jobs)}] {short(opp)} {arm} {our}: "
                  f"+{r['npass']} passes (+{r['okp']} ok, +{r['badp']} adv)",
                  flush=True)

    print("=" * 72)
    for opp in args.opp:
        report(short(opp), per_opp[opp])
    report("GERAL", overall)


if __name__ == "__main__":
    main()
