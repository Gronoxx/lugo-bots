#!/usr/bin/env python3
"""Evolução dos parâmetros do bot (genes contínuos) contra um adversário fixo.

Objetivo: maximizar o saldo de gols (pró − contra) vs level-1, partindo do
genoma da v9 (os DEFAULTS de params.py). Uma imagem serve qualquer genoma via
BOT_PARAMS — NÃO reconstrói imagem, só varia o ambiente.

Algoritmo: GA (μ+λ) com elitismo. Os elites são REavaliados a cada geração e
ACUMULAM partidas, então o estimador de fitness deles melhora com o tempo (o
ruído por partida vs level-1 é ~0,9 gol). Nunca regride: o melhor genoma
sobrevive. A busca roda em rush (rápido, ruidoso); o campeão final PRECISA ser
validado em wait com N adequado antes de acreditar (lição do projeto).

Robustez para rodar horas sem supervisão:
  - checkpoint do campeão a cada geração  (results/evolve_champion.json)
  - log de todo genoma avaliado           (results/evolve_log.csv)
  - orçamento de tempo (--hours) e tolera partidas com ERRO (não derruba a run)
  - cada partida limpa o próprio replay (senão o disco enche)

Uso:
  python3 bench/evolve.py --hours 7 --pop 8 --reps 3 --mode rush \
          --opp lugobots/level-1:latest --parallel 3
"""
import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bot", "src"))
import params  # noqa: E402  (DEFAULTS, BOUNDS)

GENES = [g for g in params.DEFAULTS if g in params.BOUNDS]  # contínuos evoluíveis
BOUNDS = params.BOUNDS
BASELINE = {g: float(params.DEFAULTS[g]) for g in GENES}
# genes ESTRUTURAIS (on/off, escolha de implementação) a evoluir — vazio por
# padrão (retrocompatível); preenchido por --struct. STRUCT_OPTS dá as opções.
STRUCT = []
STRUCT_OPTS = params.STRUCTURE_OPTIONS
IMAGE = "mybot:v9"


def genome_id(gm):
    blob = json.dumps({g: (round(gm[g], 4) if isinstance(gm[g], (int, float)) else gm[g])
                       for g in sorted(gm)}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:8]


def clamp(g, v):
    lo, hi = BOUNDS[g]
    return max(lo, min(hi, v))


def mutate(gm, sigma, p_mut):
    child = dict(gm)
    for g in GENES:
        if random.random() < p_mut:
            lo, hi = BOUNDS[g]
            child[g] = clamp(g, child[g] + random.gauss(0, sigma * (hi - lo)))
    for g in STRUCT:
        if random.random() < p_mut:
            child[g] = random.choice(STRUCT_OPTS[g])
    return child


def crossover(a, b):
    child = {g: (a[g] if random.random() < 0.5 else b[g]) for g in GENES}
    for g in STRUCT:
        child[g] = a[g] if random.random() < 0.5 else b[g]
    return child


# ---- avaliação: reps*2 partidas via eval_genome.sh (paralelismo bash) --------
def evaluate(genome, reps, opp, mode, parallel, tag):
    """Saldos de reps*2 partidas do genoma vs opp. Delega o paralelismo ao
    eval_genome.sh (bash) — o padrão comprovado; threads Python + docker se
    mostraram instáveis."""
    payload = {g: round(genome[g], 4) for g in GENES}
    payload.update({g: genome[g] for g in STRUCT})   # estruturais: string crua
    gj = json.dumps(payload, separators=(",", ":"))  # compacto: ": " quebraria o YAML
    full_tag = f"{tag}_{genome_id(genome)}"
    try:
        r = subprocess.run(["./eval_genome.sh", gj, str(reps), opp, mode,
                            str(parallel), full_tag],
                           cwd=HERE, capture_output=True, text=True, timeout=3600)
    except Exception as e:
        print(f"  eval {full_tag}: EXCEPTION {e}", file=sys.stderr, flush=True)
        return []
    saldos = []
    for tok in r.stdout.split():
        try:
            saldos.append(int(tok))
        except ValueError:
            pass
    if not saldos:
        print(f"  eval {full_tag}: 0 saldos (stderr={r.stderr[-200:]!r})",
              file=sys.stderr, flush=True)
    return saldos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=7.0)
    ap.add_argument("--pop", type=int, default=8)
    ap.add_argument("--elite", type=int, default=3)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mode", default="rush", choices=["rush", "wait"])
    ap.add_argument("--opp", default="lugobots/level-1:latest")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--sigma", type=float, default=0.15)
    ap.add_argument("--pmut", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--min-n", type=int, default=8,
                    help="mínimo de partidas p/ um genoma poder ser campeão")
    ap.add_argument("--genes", default="",
                    help="genes a evoluir (vírgula); vazio = todos os contínuos. "
                         "Os não-listados ficam no default da v9 (params.py)")
    ap.add_argument("--struct", default="",
                    help="genes ESTRUTURAIS a evoluir (vírgula): use_velocity, "
                         "pass_retain, support_mode, far_post_run... (STRUCTURE_OPTIONS)")
    ap.add_argument("--log", default="results/evolve_log.csv")
    ap.add_argument("--champion", default="results/evolve_champion.json")
    a = ap.parse_args()
    random.seed(a.seed)

    # restringe o conjunto de genes evoluíveis (o resto fica no default da v9,
    # porque o BOT_PARAMS só carrega o subconjunto e params.py completa o resto)
    global GENES, BASELINE, STRUCT
    if a.genes:
        req = [g.strip() for g in a.genes.split(",") if g.strip()]
        unknown = [g for g in req if g not in BOUNDS]
        if unknown:
            print(f"AVISO: genes ignorados (sem bounds): {unknown}", flush=True)
        GENES = [g for g in req if g in BOUNDS]
        BASELINE = {g: float(params.DEFAULTS[g]) for g in GENES}
    if a.struct:
        req = [g.strip() for g in a.struct.split(",") if g.strip()]
        unknown = [g for g in req if g not in STRUCT_OPTS]
        if unknown:
            print(f"AVISO: estruturais ignorados (sem opções): {unknown}", flush=True)
        STRUCT = [g for g in req if g in STRUCT_OPTS]
        BASELINE.update({g: params.STRUCTURE_DEFAULTS[g] for g in STRUCT})

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    t_end = time.time() + a.hours * 3600
    store = {}  # gid -> {"genome":gm, "saldos":[...], "gen":g}

    def record(gm, saldos, gen):
        gid = genome_id(gm)
        e = store.setdefault(gid, {"genome": gm, "saldos": [], "gen": gen})
        e["saldos"].extend(saldos)
        return gid

    def mean(gid):
        s = store[gid]["saldos"]
        return (sum(s) / len(s)) if s else -999.0

    def n_of(gid):
        return len(store[gid]["saldos"])

    logf = open(os.path.join(HERE, a.log), "w", newline="")
    logw = csv.writer(logf)
    logw.writerow(["gen", "gid", "n", "mean_saldo"] + GENES + STRUCT)
    logf.flush()

    base_gid = genome_id(BASELINE)
    pop = [dict(BASELINE)] + [mutate(BASELINE, a.sigma, a.pmut)
                              for _ in range(a.pop - 1)]
    gen = 0
    sigma = a.sigma
    print(f"genes evoluíveis: {len(GENES)} | baseline gid={base_gid} | "
          f"orçamento {a.hours}h | pop={a.pop} reps={a.reps} mode={a.mode}",
          flush=True)

    while time.time() < t_end:
        gen += 1
        for gm in pop:
            if time.time() >= t_end:
                break
            saldos = evaluate(gm, a.reps, a.opp, a.mode, a.parallel, f"g{gen}")
            gid = record(gm, saldos, gen)
            logw.writerow([gen, gid, n_of(gid), round(mean(gid), 3)]
                          + [round(gm[g], 4) for g in GENES]
                          + [gm[g] for g in STRUCT])
            logf.flush()

        # ranqueia por média acumulada; campeão precisa de min_n partidas
        qualified = [g for g in store if n_of(g) >= a.min_n]
        pool = qualified if qualified else [g for g in store if n_of(g) > 0]
        ranked = sorted(pool, key=mean, reverse=True)
        best = ranked[0]
        json.dump({"gid": best, "mean_saldo": round(mean(best), 3),
                   "n": n_of(best), "gen": gen,
                   "baseline_mean": round(mean(base_gid), 3) if base_gid in store else None,
                   "baseline_n": n_of(base_gid) if base_gid in store else 0,
                   "genome": store[best]["genome"]},
                  open(os.path.join(HERE, a.champion), "w"), indent=2)

        elite_gids = sorted([g for g in store if n_of(g) > 0],
                            key=mean, reverse=True)[:a.elite]
        elites = [store[g]["genome"] for g in elite_gids]
        offspring = []
        while len(offspring) < max(0, a.pop - len(elites)):
            p1, p2 = random.choice(elites), random.choice(elites)
            offspring.append(mutate(crossover(p1, p2), sigma, a.pmut))
        pop = elites + offspring
        sigma = max(0.03, sigma * 0.92)

        bm = mean(best)
        base_txt = (f"base={mean(base_gid):.2f}(n{n_of(base_gid)})"
                    if base_gid in store else "base=?")
        print(f"[gen {gen}] campeão {best} saldo={bm:.2f}(n{n_of(best)}) {base_txt} "
              f"sigma={sigma:.3f} genomas={len(store)} "
              f"resta={(t_end - time.time()) / 3600:.2f}h", flush=True)

    logf.close()
    ranked = sorted([g for g in store if n_of(g) >= a.min_n],
                    key=mean, reverse=True)
    print("\n=== TOP 8 genomas (n >= min_n) ===", flush=True)
    for g in ranked[:8]:
        print(f"  {g}: saldo={mean(g):.2f}  n={n_of(g)}", flush=True)
    if base_gid in store:
        print(f"baseline v9: saldo={mean(base_gid):.2f}  n={n_of(base_gid)}", flush=True)
    print(f"campeão em {a.champion} | log em {a.log}", flush=True)


if __name__ == "__main__":
    main()
