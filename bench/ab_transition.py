#!/usr/bin/env python3
"""A/B de TRANSIÇÃO DEFENSIVA vs sparring "banheira+pressing" (pós 0-3 BotAdversario1).

Dois braços (base/test) jogam contra o MESMO adversário; a métrica primária é a
falha de saída de bola (def_start_turnover_pct do bench/defense_report.py), com
o painel defensivo completo (gols sofridos por origem, rebotes, zona do gol,
opp_danger) e as guardas ofensivas (good_chance_rate, gols).

Adversário:
  --opp sparring  -> mybot:qp dos DOIS lados; o lado adversário recebe o genoma
                     SPARRING (campers altos + 5 chasers + pressão), o nosso o
                     genoma do braço. Reproduz o padrão BotAdversario1 localmente.
  --opp <imagem>  -> nosso mybot:qp (genoma do braço) vs a imagem dada.

Braços:
  base = --base (default: genoma de produção v2)
  test = base + genes de --test

Uso:
  .venv/bin/python bench/ab_transition.py --tag a1 --reps 6 --parallel 3 \
      --opp sparring --test '{"carry_gate":"on"}'
  (--test '{}' => braços idênticos: mede o ruído da régua)

Replays ficam em bench/recordings/abt_<tag>_*.json (mantidos p/ forense).
"""
import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import defense_report as DR       # noqa: E402
import proxy_metric as PM         # noqa: E402

V2 = {"pass_endpoint_race": "on", "pass_exec_speed": "on",
      "pass_touch_lead": "on", "pass_status_mode": "on", "cover_mode": "on"}

# Receita do sparring (iteração 2, sobre a base v2). Objetivo: reproduzir os
# MOMENTOS de falha do 0-3 (bola funda no nosso terço + pressing + punidores na
# nossa área). shift_x=0.8: com a bola no nosso fundo os atacantes deles vão a
# x_frac~0.92 => x~1600 = NOSSA área (banheira nos momentos que importam);
# n_chasers=5 + pressure_radius=6000 = pressing na saída; shot_min_gap=800 +
# rebound_crash=on (genes novos!) = chutam mais e caçam a segunda bola como o
# BotAdversario1; support_catch=on ajuda a punir bola dividida.
# (Iteração 1 — shift_x=0.0 — pressionava, mas não punia: 0 gols em 12.)
# Onda 2: n_chasers 4 (fidelidade — o BotAdversario1 pressiona com 4: 2/7/8/11 —
# e o press de 5 da onda 1 tornava QUALQUER escape impossível, mascarando o
# valor dos genes de saída).
SPARRING = dict(V2, **{"shift_x": 0.8, "aggression_defend": 1.0,
                       "aggression_support": 1.5, "n_chasers": 4,
                       "pressure_radius": 6000, "cover_mix": 0.0,
                       "shot_min_gap": 800, "rebound_crash": "on",
                       "rebound_zone_frac": 0.5, "support_catch": "on"})

ARM_ORDER = ("base", "test")


def compact(g):
    return json.dumps(g, separators=(",", ":"))


def run_match(tag, opp, arm_name, genome_json, rep, side, timer):
    mid = f"abt_{tag}_{arm_name}_{side}_{rep}"
    env = dict(os.environ, TIMER_MODE=timer)
    env.pop("HOME_PARAMS", None)
    env.pop("AWAY_PARAMS", None)
    spar = compact(SPARRING)
    if opp == "sparring":
        h_img = a_img = "mybot:qp"
        if side == "home":
            env["HOME_PARAMS"], env["AWAY_PARAMS"] = genome_json, spar
            our = "HOME"
        else:
            env["HOME_PARAMS"], env["AWAY_PARAMS"] = spar, genome_json
            our = "AWAY"
    else:
        if side == "home":
            h_img, a_img, our = "mybot:qp", opp, "HOME"
            env["HOME_PARAMS"] = genome_json
        else:
            h_img, a_img, our = opp, "mybot:qp", "AWAY"
            env["AWAY_PARAMS"] = genome_json
    try:
        subprocess.run(["./run_match.sh", h_img, a_img, mid], cwd=HERE, env=env,
                       capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return None
    path = os.path.join(HERE, "recordings", f"{mid}.json")
    return (arm_name, our, path) if os.path.exists(path) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="prefixo dos match-ids (sem colisão)")
    ap.add_argument("--reps", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--opp", default="sparring")
    ap.add_argument("--base", default=None, help="genoma base JSON (default: v2)")
    ap.add_argument("--test", required=True, help="genes extra do braço test (JSON)")
    ap.add_argument("--mode", default="rush", choices=["rush", "wait"])
    args = ap.parse_args()

    n_orph = subprocess.run(["docker", "ps", "-q", "--filter", "name=lugo_"],
                            capture_output=True, text=True).stdout.strip()
    if n_orph:
        print(f"AVISO: já existem containers lugo_* rodando ({len(n_orph.splitlines())}) "
              f"— medição pode ficar contaminada.", flush=True)

    base = json.loads(args.base) if args.base else dict(V2)
    test = dict(base)
    test.update(json.loads(args.test))
    arms = {"base": compact(base), "test": compact(test)}
    print(f"A/B transição [{args.tag}] vs {args.opp} ({args.mode}): "
          f"{args.reps} reps x 2 lados x 2 braços = {args.reps * 4} partidas")
    print(f"  base = {arms['base']}")
    print(f"  test = {arms['test']}", flush=True)

    jobs = [(args.tag, args.opp, arm, arms[arm], rep, side, args.mode)
            for arm in ARM_ORDER
            for rep in range(1, args.reps + 1) for side in ("home", "away")]
    results = {a: [] for a in ARM_ORDER}
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
            arm, our, path = res
            try:
                results[arm].append(DR.analyze_file(path, our))
                paths[arm].append(path)
                gf = results[arm][-1][0].get("gf", 0)
                ga = results[arm][-1][0].get("ga", 0)
                print(f"[{done}/{len(jobs)}] {arm} {our}: {gf}x{ga}", flush=True)
            except Exception as e:
                print(f"[{done}/{len(jobs)}] {arm}: erro na análise ({e})", flush=True)

    print("=" * 78)
    aggs = {}
    for arm in ARM_ORDER:
        if not results[arm]:
            continue
        aggs[arm] = DR.aggregate(results[arm])
        DR.print_report(aggs[arm], f"braço {arm}")
        m = PM.summarize(paths[arm])
        print(f"  [proxy] good_chance_rate={m['good_chance_rate']:.3f} "
              f"best_slack={m['best_slack_mean']:+.0f} "
              f"shot_slack>0={m['shot_slack_frac_pos']:.2f} (n={m['n_shots']}) "
              f"gols={m['goals_mean']:.2f}/{m['conceded_mean']:.2f}\n")

    if len(aggs) == 2:
        b, t = aggs["base"], aggs["test"]
        z = DR.two_prop_z(t.get("def_start_turnover", 0), max(1, t.get("def_start", 0)),
                          b.get("def_start_turnover", 0), max(1, b.get("def_start", 0)))
        print(f"PRIMÁRIA def_start_turnover_pct: base {b['def_start_turnover_pct']:.1f}% "
              f"-> test {t['def_start_turnover_pct']:.1f}%  (z={z:+.2f}; "
              f"negativo = test melhor)")
        zi = DR.two_prop_z(
            sum(v for (c, _t2), v in t["causa_terco"].items() if c == "passe interceptado"),
            max(1, t.get("poss_ours", 0)),
            sum(v for (c, _t2), v in b["causa_terco"].items() if c == "passe interceptado"),
            max(1, b.get("poss_ours", 0)))
        print(f"  interceptados/posse: z={zi:+.2f} (não pode subir) | "
              f"ga/jogo: {b['ga_pg']:.2f} -> {t['ga_pg']:.2f} | "
              f"opp_danger: {b['opp_danger_turns_pg']:.0f} -> {t['opp_danger_turns_pg']:.0f}")


if __name__ == "__main__":
    main()
