#!/usr/bin/env python3
"""SONDA DE CERCO — qual adversário LOCAL reproduz o level-3 da plataforma?

Motivo (20/08): o vídeo do 0×0 da v10 vs level-3 mostra o jogo inteiro no
NOSSO campo (campo_adv deles 62,3%). Contra o level-1 local acontece o oposto
— acampamos no campo deles. Logo o laboratório vs level-1 NÃO mede o problema
que decide o desempate do seeding (saldo vs L3). Esta sonda mede, para cada
adversário local disponível, a GEOGRAFIA da partida, e escolhe o que mais se
parece com o level-3.

Uso:
  python3 bench/siege_probe.py --genome bot/genome_v6.json \
      --opps lugobots/level-1:latest,BotAdversario2clone:latest,sparring --n 1
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import proxy_metric as PM      # noqa: E402
import metrics_lab as M        # noqa: E402
from ab_transition import SPARRING, compact   # noqa: E402


def run_one(genome_json, opp, mid, side, timer):
    env = dict(os.environ, TIMER_MODE=timer, KNOCKOUT_DIFF="99")
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    if opp == "sparring":
        h = a = "mybot:qp"
        spar = compact(SPARRING)
        if side == "home":
            env["HOME_PARAMS"], env["AWAY_PARAMS"], our = genome_json, spar, "HOME"
        else:
            env["HOME_PARAMS"], env["AWAY_PARAMS"], our = spar, genome_json, "AWAY"
    elif side == "home":
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
    p = os.path.join(HERE, "recordings", f"{mid}.json")
    return (opp, our, p) if os.path.exists(p) else None


def geo(path, our):
    d = PM.build_d(path)
    side = our.lower()
    s = 0 if side == "home" else 1
    bx = d["bx"].astype(float)
    prog = bx if side == "home" else 20000.0 - bx      # 0 = nosso gol
    sc_our = d["sc_home"] if our == "HOME" else d["sc_away"]
    sc_opp = d["sc_away"] if our == "HOME" else d["sc_home"]
    ev, _ = M.mark_shots(d, side)
    ev_o, _ = M.mark_shots(d, "away" if side == "home" else "home")
    hs = d["hold_side"]
    return dict(
        gf=int(sc_our[-1]), ga=int(sc_opp[-1]),
        shots=sum(1 for e in ev if e.get("on_goal")),
        shots_opp=sum(1 for e in ev_o if e.get("on_goal")),
        terr=100.0 * float((prog > 10000).mean()),     # bola no campo DELES
        terco=100.0 * float((prog > 13333).mean()),    # terço de ataque
        posse=100.0 * float((hs == s).sum() / max(1, (hs >= 0).sum())),
        passes=len(ev),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genome", default="bot/genome_v6.json")
    ap.add_argument("--opps", required=True)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--tag", default="siege")
    ap.add_argument("--mode", default="wait")
    ap.add_argument("--parallel", type=int, default=6)
    a = ap.parse_args()

    genome = open(os.path.join(HERE, "..", a.genome)).read().strip() \
        if not os.path.isabs(a.genome) else open(a.genome).read().strip()
    opps = a.opps.split(",")
    jobs = []
    for o in opps:
        slug = o.replace("/", "").replace(":", "").replace(".", "")[:16]
        for r in range(1, a.n + 1):
            for side in ("home", "away"):
                jobs.append((genome, o, f"sg_{a.tag}_{slug}_{side}_{r}", side, a.mode))
    print(f"SONDA DE CERCO: {len(jobs)} partidas ({a.mode})", flush=True)
    rows = {o: [] for o in opps}
    with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
        futs = [ex.submit(run_one, *j) for j in jobs]
        for i, f in enumerate(cf.as_completed(futs), 1):
            res = f.result()
            if res is None:
                print(f"[{i}/{len(jobs)}] FALHOU", flush=True)
                continue
            opp, our, path = res
            try:
                g = geo(path, our)
                rows[opp].append(g)
                print(f"[{i}/{len(jobs)}] {opp:28s} {g['gf']}x{g['ga']} "
                      f"fin={g['shots']:2d} terr={g['terr']:5.1f}% "
                      f"terco={g['terco']:5.1f}% posse={g['posse']:5.1f}%", flush=True)
            except Exception as e:
                print(f"[{i}/{len(jobs)}] erro: {e}", flush=True)
    print("\n" + "=" * 78)
    print(f"{'adversario':28s} {'n':>2s} {'gf':>5s} {'ga':>5s} {'fin':>5s} "
          f"{'finC':>5s} {'terr%':>6s} {'terco%':>7s} {'posse%':>7s}")
    for o in opps:
        v = rows[o]
        if not v:
            continue
        m = lambda k: float(np.mean([x[k] for x in v]))
        print(f"{o:28s} {len(v):2d} {m('gf'):5.2f} {m('ga'):5.2f} {m('shots'):5.1f} "
              f"{m('shots_opp'):5.1f} {m('terr'):6.1f} {m('terco'):7.1f} {m('posse'):7.1f}")
    print("\nREFERÊNCIA PLATAFORMA (v10 vs level-3): terr NOSSO ~37.7%, "
          "fin 8, gf 0 | (v6 vs level-3): fin 7, gf 3")


if __name__ == "__main__":
    main()
