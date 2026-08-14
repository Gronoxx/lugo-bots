#!/usr/bin/env python3
"""SELF-PLAY como REGUA FORTE: nao ha bot forte externo local, mas o NOSSO bot
(Fase A) e' forte. Aqui os dois lados sao mybot:qp; um recebe o bundle "quando
passar" (test), o outro a base Fase A. Head-to-head, mesma imagem, so os genes
mudam. Disputa competitiva (menos variancia que vs oponente fraco) e mede
DIRETAMENTE se o bundle bate a baseline.

  test = Fase A + <genes do bundle passados via --test>
  base = Fase A

Reporta o SALDO DE GOLS do lado TEST (media sobre partidas, alternando lados).
Controle: rode com --test '{}' para ver o saldo base-vs-base (~0 confirma
ausencia de vies de lado).

Uso: .venv/bin/python bench/ab_selfplay.py --reps 12 --parallel 4 \
       --test '{"pass_status_mode":"on","pass_lookahead":"depth2","pass_control":"on"}'
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
import replay as R  # noqa: E402

FA = {"pass_endpoint_race": "on", "pass_exec_speed": "on", "pass_touch_lead": "on"}


def gd(path, side):
    _c, ev = R.load(path)
    snaps = list(R.snapshots(ev))
    if not snaps:
        return None
    last = snaps[-1]
    h, a = R.score(last, "home"), R.score(last, "away")
    return (h - a) if side == "HOME" else (a - h)


def run_match(base_json, test_json, rep, test_side):
    mid = f"absp_{test_side}_{rep}"
    env = dict(os.environ, TIMER_MODE="rush")
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    if test_side == "home":
        env["HOME_PARAMS"], env["AWAY_PARAMS"] = test_json, base_json
        our = "HOME"
    else:
        env["HOME_PARAMS"], env["AWAY_PARAMS"] = base_json, test_json
        our = "AWAY"
    try:
        subprocess.run(["./run_match.sh", "mybot:qp", "mybot:qp", mid], cwd=HERE,
                       env=env, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return None
    path = os.path.join(HERE, "recordings", f"{mid}.json")
    if not os.path.exists(path):
        return None
    return gd(path, our)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--test", required=True, help="genes extra do lado TEST (JSON)")
    args = ap.parse_args()

    base = dict(FA)
    test = dict(FA); test.update(json.loads(args.test))
    base_json, test_json = json.dumps(base), json.dumps(test)
    print(f"SELF-PLAY test vs base (Fase A). test extra = {args.test}")

    jobs = [(base_json, test_json, rep, side)
            for rep in range(1, args.reps + 1) for side in ("home", "away")]
    diffs = []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {ex.submit(run_match, *j): j for j in jobs}
        for f in cf.as_completed(futs):
            done += 1
            d = f.result()
            if d is None:
                print(f"[{done}/{len(jobs)}] FALHOU", flush=True)
                continue
            diffs.append(d)
            print(f"[{done}/{len(jobs)}] saldo_test={d:+d}", flush=True)

    print("=" * 60)
    n = len(diffs)
    if n:
        mean = sum(diffs) / n
        var = sum((x - mean) ** 2 for x in diffs) / (n - 1) if n > 1 else 0.0
        se = (var / n) ** 0.5
        z = mean / se if se else 0.0
        print(f"SALDO DE GOLS do TEST vs base (Fase A): {mean:+.2f} +/- {se:.2f} "
              f"(n={n}, z={z:.2f}, {'SIG' if abs(z) > 1.96 else 'n.s.'})")
        print(f"  vitorias/empates/derrotas do test: "
              f"{sum(1 for d in diffs if d>0)}/{sum(1 for d in diffs if d==0)}/"
              f"{sum(1 for d in diffs if d<0)}")
        print(f"  saldos: {sorted(diffs)}")


if __name__ == "__main__":
    main()
