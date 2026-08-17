#!/usr/bin/env python3
"""Agregador DEFENSIVO sobre replays — mede o que o 0-3 vs BotAdversario1 expôs.

Junta, por conjunto de replays (um "braço" de A/B ou um corpus):
  - transição defensiva: posses nossas que COMEÇAM no terço defensivo e morrem
    por turnover (conducao tomada / passe interceptado / bola solta perdida)
    -> métrica primária `def_start_turnover_pct`;
  - tabela causa × terço das perdas;
  - gols sofridos por ORIGEM da posse adversária (contra-ataque = posse curta);
  - chutes SOFRIDOS on-goal, gols, "defesas" (on-goal sem gol) e REBOTES
    concedidos (eles retomam perto do nosso gol após o próprio chute);
  - rebotes OFENSIVOS (nós retomamos/perdemos a segunda bola do nosso chute);
  - relógio da zona do gol (turns_ball_in_goal_zone): máximo observado na NOSSA
    zona e auto-chutes disparados (contador chega a >=39 e reseta);
  - pressão do adversário (opp_danger_turns, via proxy_metric) e criação nossa
    (good_chance_rate) como guarda;
  - `camp_turns_pct` (valida o sparring: % dos nossos turnos de posse com >=2
    adversários de linha a <=8000 do nosso gol) e `coverage_gap_pct` (% dos
    turnos com camper presente SEM marcador nosso goal-side a <=1200).

Uso:
  .venv/bin/python bench/defense_report.py [--side HOME|AWAY|auto] replays...
  (auto = sufixo _home/_away no nome do arquivo)

Como biblioteca (bench/ab_transition.py): analyze_file(path, our_side) ->
dict de contagens; aggregate(list) -> somas + taxas; print_report(agg, label).
"""
import argparse
import glob
import math
import os
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import replay as R                # noqa: E402
import frente2_possession as FP   # noqa: E402
import proxy_metric as PM         # noqa: E402
import metrics_lab as M           # noqa: E402

MAX_X, MAX_Y = 20000.0, 10000.0
GOAL_C = 5000.0
TURNOVER = ("conducao tomada", "passe interceptado", "bola solta perdida")
CAMP_RANGE = 8000.0        # "no nosso campo" (mesmo default de cover_range)
MARK_NEAR = 1200.0         # marcador a <= isto do camper conta como cobertura
REBOUND_NEAR = 4000.0      # retomada a <= isto do gol apos chute = rebote
REBOUND_WIN = 40           # turnos de janela para a segunda bola


def _zone_pass(path, our_goal_x):
    """Varre os eventos e mede o relógio da zona do gol na NOSSA zona.
    Devolve (zone_max_ours, auto_kicks_ours)."""
    _cfg, events = R.load(path)
    zone_max, autos = 0, 0
    prev_cnt, prev_ours = 0, False
    seen = {}
    for e in events:
        gs = e.get("game_snapshot")
        if not gs:
            continue
        t = gs.get("turn", 0)
        seen[t] = gs
    for t in sorted(seen):
        gs = seen[t]
        cnt = gs.get("turns_ball_in_goal_zone", 0)
        bx, by = R.ball_pos(gs)
        ours = math.hypot(bx - our_goal_x, by - GOAL_C) <= 1600.0
        if ours:
            zone_max = max(zone_max, cnt)
        if prev_cnt >= 38 and cnt < 5 and prev_ours:
            autos += 1
        prev_cnt, prev_ours = cnt, ours
    return zone_max, autos


def _rebounds(d, ev_side, side_idx, goal_x, regain_side_idx):
    """Conta rebotes após chutes on-goal SEM gol do lado `ev_side` (string).
    regain_side_idx = quem retomando caracteriza o rebote 'ganho' pelo chutador.
    Devolve (rebotes_do_chutador, retomadas_do_outro)."""
    ev, _ = M.mark_shots(d, ev_side)
    hold = d["hold_side"]
    bx, by = d["bx"], d["by"]
    n = len(hold)
    won = lost = 0
    for e in ev:
        if not e.get("on_goal") or e.get("goal"):
            continue
        i = e["i"]
        for j in range(i + 1, min(i + REBOUND_WIN, n)):
            if hold[j] < 0:
                continue
            near = math.hypot(bx[j] - goal_x, by[j] - GOAL_C) <= REBOUND_NEAR
            if hold[j] == regain_side_idx:
                if near:
                    won += 1
                break
            else:
                break
    # perdido = chutes on-goal sem gol cuja 1a retomada foi do OUTRO lado
    for e in ev:
        if not e.get("on_goal") or e.get("goal"):
            continue
        i = e["i"]
        for j in range(i + 1, min(i + REBOUND_WIN, n)):
            if hold[j] < 0:
                continue
            if hold[j] != regain_side_idx:
                lost += 1
            break
    return won, lost


def analyze_file(path, our_side):
    """Métricas defensivas de UM replay. our_side = 'HOME'|'AWAY'."""
    their_side = "AWAY" if our_side == "HOME" else "HOME"
    our_l, their_l = our_side.lower(), their_side.lower()
    our_s = 0 if our_side == "HOME" else 1
    their_s = 1 - our_s
    our_goal_x = 0.0 if our_side == "HOME" else MAX_X
    their_goal_x = MAX_X - our_goal_x

    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        A = FP.analyze(path, our_side, os.path.basename(path))
    ours = [p for p in A["poss"] if p["side"] == our_side]
    theirs = [p for p in A["poss"] if p["side"] == their_side]

    out = Counter()
    out["n_files"] = 1
    out["poss_ours"] = len(ours)
    out["gf"] = sum(1 for s, _ in A["goals"] if s == our_side)
    out["ga"] = sum(1 for s, _ in A["goals"] if s == their_side)

    # ---- transição defensiva (o padrão dos gols 2/3)
    causa_terco = Counter()
    for p in ours:
        causa_terco[(p["causa"], p["reg"][0])] += 1
        if p["reg_start"][0] == "def":
            out["def_start"] += 1
            if p["causa"] in TURNOVER:
                out["def_start_turnover"] += 1
                if p["reg"][0] == "def":
                    out["def_start_turnover_in_def"] += 1
            if p["xbest"] >= MAX_X / 3 + 1500:
                out["def_start_escape"] += 1
        if p["reg"][0] == "def" and p["causa"] in TURNOVER:
            out["loss_in_def"] += 1
    out["turnover_total"] = sum(1 for p in ours if p["causa"] in TURNOVER)

    # ---- gols sofridos por origem
    for p in theirs:
        if p["causa"] == "GOL":
            out["ga_poss"] += 1
            out[f"ga_start_{p['reg_start'][0]}"] += 1
            if p["dur"] <= 40:
                out["ga_fast"] += 1

    # ---- chutes sofridos / nosso goleiro / rebotes
    d = PM.build_d(path)
    ev_theirs, _ = M.mark_shots(d, their_l)
    on_goal = [e for e in ev_theirs if e.get("on_goal")]
    out["shots_against"] = len(ev_theirs)
    out["shots_against_on_goal"] = len(on_goal)
    out["goals_against_shots"] = sum(1 for e in on_goal if e.get("goal"))
    out["saves"] = len(on_goal) - out["goals_against_shots"]
    reb_c, _ = _rebounds(d, their_l, their_s, our_goal_x, their_s)
    out["rebotes_concedidos"] = reb_c
    reb_w, reb_l = _rebounds(d, our_l, our_s, their_goal_x, our_s)
    out["rebotes_ofensivos_ganhos"] = reb_w
    out["rebotes_ofensivos_perdidos"] = reb_l

    # ---- nossos chutes/passes (volume)
    our_k = [k for k in A["kicks"] if k["side"] == our_side]
    kt = Counter(k["tipo"] for k in our_k)
    ev_ours, _ = M.mark_shots(d, our_l)
    out["our_shots_on_goal"] = sum(1 for e in ev_ours if e.get("on_goal"))
    out["our_passes"] = kt["passe"]

    # ---- camping / cobertura (numpy por turno)
    ox, oy, onum = (("ax", "ay", "anum") if our_side == "HOME"
                    else ("hx", "hy", "hnum"))
    mx, my, mnum = (("hx", "hy", "hnum") if our_side == "HOME"
                    else ("ax", "ay", "anum"))
    t_dgoal = np.hypot(d[ox] - our_goal_x, d[oy] - GOAL_C)
    t_line = (d[onum] > 0) & (d[onum] != 1)
    campers = t_line & (t_dgoal <= CAMP_RANGE)
    we_hold = d["hold_side"] == our_s
    # banheira DE VERDADE: nós seguramos a bola já no campo DELES e mesmo assim
    # >=2 jogadores de linha deles ficam fundos no NOSSO campo (padrão BotAdversario1).
    ball_adv = d["bx"] if our_side == "HOME" else (MAX_X - d["bx"])
    we_attack = we_hold & (ball_adv >= MAX_X / 2)
    out["hold_turns"] = int(we_attack.sum())
    out["camp_turns"] = int((we_attack & (campers.sum(axis=1) >= 2)).sum())

    m_dgoal = np.hypot(d[mx] - our_goal_x, d[my] - GOAL_C)
    m_line = (d[mnum] > 0) & (d[mnum] != 1)
    gap_turns = turns_with_camper = 0
    idx = np.where(we_hold & (campers.sum(axis=1) >= 1))[0]
    for i in idx:
        turns_with_camper += 1
        gap = False
        for j in np.where(campers[i])[0]:
            cx, cy, cd = d[ox][i, j], d[oy][i, j], t_dgoal[i, j]
            dd = np.hypot(d[mx][i] - cx, d[my][i] - cy)
            marked = np.any(m_line[i] & (dd <= MARK_NEAR) & (m_dgoal[i] < cd))
            if not marked:
                gap = True
                break
        if gap:
            gap_turns += 1
    out["camper_turns"] = turns_with_camper
    out["coverage_gap_turns"] = gap_turns

    # ---- pressão/criação (proxy) + zona do gol
    pr = PM.proxy_for_replay(d, our_l)
    out["opp_danger_turns"] = pr["opp_danger"]
    out["danger_poss"] = pr["danger_poss"]
    out["good_chances"] = pr["good_chances"]
    zone_max, autos = _zone_pass(path, our_goal_x)
    out["zone_max_ours"] = max(out.get("zone_max_ours", 0), zone_max)
    out["auto_kicks_ours"] = autos

    return dict(out), causa_terco


def aggregate(results):
    """Soma contagens de analyze_file e deriva taxas."""
    agg = Counter()
    ct = Counter()
    for out, causa_terco in results:
        zm = out.pop("zone_max_ours", 0)
        agg.update(out)
        agg["zone_max_ours"] = max(agg["zone_max_ours"], zm)
        ct.update(causa_terco)
    a = dict(agg)
    n = a.get("n_files", 0) or 1
    a["causa_terco"] = ct
    a["def_start_turnover_pct"] = 100.0 * a.get("def_start_turnover", 0) / max(1, a.get("def_start", 0))
    a["def_start_escape_pct"] = 100.0 * a.get("def_start_escape", 0) / max(1, a.get("def_start", 0))
    a["turnover_pct"] = 100.0 * a.get("turnover_total", 0) / max(1, a.get("poss_ours", 0))
    a["camp_turns_pct"] = 100.0 * a.get("camp_turns", 0) / max(1, a.get("hold_turns", 0))
    a["coverage_gap_pct"] = 100.0 * a.get("coverage_gap_turns", 0) / max(1, a.get("camper_turns", 0))
    a["good_chance_rate"] = a.get("good_chances", 0) / max(1, a.get("danger_poss", 0))
    for k in ("gf", "ga", "shots_against_on_goal", "saves", "rebotes_concedidos",
              "rebotes_ofensivos_ganhos", "rebotes_ofensivos_perdidos",
              "our_shots_on_goal", "our_passes", "opp_danger_turns",
              "auto_kicks_ours"):
        a[k + "_pg"] = a.get(k, 0) / n
    return a


def two_prop_z(k1, n1, k2, n2):
    """z de duas proporções (k/n) — positivo = braço 1 maior."""
    if min(n1, n2) == 0:
        return 0.0
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(max(1e-12, p * (1 - p) * (1 / n1 + 1 / n2)))
    return (p1 - p2) / se


def print_report(a, label):
    n = a.get("n_files", 0)
    print(f"--- {label} ({n} replays) ---")
    print(f"  placar medio: {a['gf_pg']:.2f} x {a['ga_pg']:.2f}")
    print(f"  TRANSICAO: posses iniciadas no terco def = {a.get('def_start', 0)} | "
          f"turnover = {a.get('def_start_turnover', 0)} ({a['def_start_turnover_pct']:.1f}%) "
          f"| escapou do terco = {a['def_start_escape_pct']:.1f}%")
    print(f"    perdas por turnover no terco def (qualquer inicio): {a.get('loss_in_def', 0)} | "
          f"turnover geral: {a['turnover_pct']:.1f}% das posses")
    print(f"  GOLS SOFRIDOS: {a.get('ga', 0)} (origem def/meio/ataque = "
          f"{a.get('ga_start_def', 0)}/{a.get('ga_start_meio', 0)}/{a.get('ga_start_ataque', 0)}; "
          f"contra-ataque<=40t = {a.get('ga_fast', 0)})")
    print(f"  CHUTES SOFRIDOS on-goal: {a['shots_against_on_goal_pg']:.2f}/jogo | defesas "
          f"{a['saves_pg']:.2f} | rebotes concedidos {a['rebotes_concedidos_pg']:.2f}")
    print(f"  REBOTE OFENSIVO: ganhos {a['rebotes_ofensivos_ganhos_pg']:.2f} | perdidos "
          f"{a['rebotes_ofensivos_perdidos_pg']:.2f} | nossos chutes on-goal "
          f"{a['our_shots_on_goal_pg']:.2f}/jogo | passes {a['our_passes_pg']:.1f}/jogo")
    print(f"  ZONA DO GOL: max contador na nossa zona = {a.get('zone_max_ours', 0)} | "
          f"auto-chutes = {a.get('auto_kicks_ours', 0)}")
    print(f"  PRESSAO: opp_danger_turns = {a['opp_danger_turns_pg']:.0f}/jogo | "
          f"good_chance_rate nossa = {a['good_chance_rate']:.3f}")
    print(f"  SPARRING-CHECK: camp_turns_pct = {a['camp_turns_pct']:.1f}% | "
          f"coverage_gap_pct = {a['coverage_gap_pct']:.1f}%")
    ct = a.get("causa_terco")
    if ct:
        causas = sorted({c for c, _t in ct})
        print(f"    {'causa':<26}{'def':>7}{'meio':>7}{'ataque':>7}")
        for c in causas:
            print(f"    {c:<26}" + "".join(f"{ct.get((c, t), 0):>7}"
                                           for t in ("def", "meio", "ataque")))


def side_of(path):
    b = os.path.basename(path)
    return "AWAY" if "_away" in b else "HOME"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", default="auto", choices=["auto", "HOME", "AWAY"])
    ap.add_argument("replays", nargs="+")
    args = ap.parse_args()
    files = []
    for pat in args.replays:
        files += sorted(glob.glob(pat))
    if not files:
        print("nenhum replay")
        return
    results = []
    for p in files:
        side = side_of(p) if args.side == "auto" else args.side
        try:
            results.append(analyze_file(p, side))
        except Exception as e:
            print(f"  {os.path.basename(p)}: erro ({e})", file=sys.stderr)
    print_report(aggregate(results), f"{len(files)} replays")


if __name__ == "__main__":
    main()
