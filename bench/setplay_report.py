#!/usr/bin/env python3
"""Minerador de REINÍCIOS (kickoff) + SEGUNDA BOLA + slack de chute.

Evidência-base (36 replays, ago/2026): o reinício é 100% determinístico
(1º toque em reset+13; nosso #10 ganha 100% vs level-1) e hoje rende ZERO
chutes em 120 turnos; a "segunda bola" da limpeza do goleiro deles existe em
92-100% dos nossos chutes sem gol e ELES ganham 61-83% delas (déficit ~789d
na corrida no instante do chute). Este relatório mede as métricas-alvo dos
pacotes P2 (kickoff_play/init_variant) e P3 (second_ball).

Uso:  .venv/bin/python bench/setplay_report.py [--side auto] replays...
Como lib (A/Bs): analyze_file(path, our_side) / aggregate / print_report.
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
import proxy_metric as PM         # noqa: E402
import metrics_lab as M           # noqa: E402

MAX_X, MAX_Y = 20000.0, 10000.0
CENTER = (10000.0, 5000.0)
ATTACK_THIRD = 2.0 * MAX_X / 3.0      # avanço >= 13333 = terço de ataque
RESET_GAP = 30                        # turnos mínimos entre resets distintos


def _adv(bx, our_side):
    return bx if our_side == "HOME" else (MAX_X - bx)


def _resets(d):
    """Índices dos eventos de reset (kickoff): bola no centro, parada, sem dono."""
    mask = ((np.abs(d["bx"] - CENTER[0]) <= 60)
            & (np.abs(d["by"] - CENTER[1]) <= 60)
            & (d["bspeed"] < 5) & (d["hold_side"] == -1))
    idxs = np.where(mask)[0]
    out, last = [], -10**9
    for i in idxs:
        if i - last >= RESET_GAP:
            out.append(int(i))
        last = int(i)
    return out


def analyze_file(path, our_side):
    """Métricas de reinício/segunda bola de UM replay. our_side='HOME'|'AWAY'."""
    our_s = 0 if our_side == "HOME" else 1
    our_l = our_side.lower()
    d = PM.build_d(path)
    n = len(d["turn"])
    hold, num = d["hold_side"], d["hold_num"]
    adv = _adv(d["bx"].astype(float), our_side)
    our_sc = d["sc_home"] if our_side == "HOME" else d["sc_away"]
    their_sc = d["sc_away"] if our_side == "HOME" else d["sc_home"]

    ev_ours, _ = M.mark_shots(d, our_l)
    our_shot_idx = np.array(sorted(e["i"] for e in ev_ours if e.get("on_goal")),
                            dtype=np.int64)

    out = Counter()
    extra = {"rob2fin_dt": []}
    out["n_files"] = 1

    # ---------------- kickoffs
    reset_idx = _resets(d)
    reset_zone = set()
    for r0 in reset_idx:
        reset_zone.update(range(r0, min(r0 + 30, n)))
    for i0 in reset_idx:
        out["kickoffs"] += 1
        j = i0 + 1
        while j < n and hold[j] < 0:
            j += 1
        if j >= n:
            continue
        out["ko_touch_dt"] += j - i0
        # v7: gols em até 200t (10s) do reset — a janela da cascata de
        # kickoff dos tops (BotAdversario1 antigo: 3×0 em ~23s; BotAdversario2: gol aos 7s)
        g200 = min(i0 + 200, n - 1)
        if their_sc[g200] > their_sc[i0]:
            out["ko_ga200"] += 1
        if our_sc[g200] > our_sc[i0]:
            out["ko_gf200"] += 1
        if hold[j] != our_s:
            out["ko_lost"] += 1
            # v7 (kickoff_race): re-roubo em ≤100t (5s) do kickoff perdido
            w100_end = min(j + 100, n)
            for k in range(j, w100_end):
                if hold[k] == our_s:
                    out["ko_steal100"] += 1
                    break
            continue
        out["ko_won"] += 1
        out[f"ko_taker_{int(num[j])}"] += 1
        w60 = slice(j, min(j + 60, n))
        w120_end = min(j + 120, n)
        if np.any(adv[w60] >= ATTACK_THIRD):
            out["ko_third60"] += 1
        if np.any((our_shot_idx >= j) & (our_shot_idx < w120_end)):
            out["ko_shot120"] += 1
        k40 = min(j + 40, n - 1)
        out["ko_disp40"] += int(adv[k40] - adv[i0])
        # guarda: gol SOFRIDO em até 60 turnos do reset (buraco defensivo)
        g60 = min(i0 + 60, n - 1)
        if their_sc[g60] > their_sc[i0]:
            out["ko_ga60"] += 1
        if our_sc[g60] > our_sc[i0]:
            out["ko_gf60"] += 1

    # ---------------- segunda bola (após NOSSO chute on-goal sem gol)
    for e in ev_ours:
        if not e.get("on_goal") or e.get("goal"):
            continue
        i = e["i"]
        kicker = int(d["hold_num"][max(0, i - 1)])
        out["sb_events"] += 1
        winner = None
        for k in range(i + 1, min(i + 40, n)):
            if hold[k] < 0 or num[k] == 1:
                continue
            if adv[k] < ATTACK_THIRD:
                continue
            winner = ("ours" if hold[k] == our_s else "theirs", k)
            break
        if winner is None:
            out["sb_none"] += 1
            continue
        who, k = winner
        out["sb_won" if who == "ours" else "sb_lost"] += 1
        # v7 (swarm_rebound): rebote APROVEITADO = novo chute on-goal nosso
        # em ≤60t (3s) após ganhar a segunda bola (o rechute do cerco)
        if who == "ours" and np.any((our_shot_idx > k)
                                    & (our_shot_idx <= min(k + 60, n))):
            out["sb_reshot60"] += 1
        # corrida: dist do nosso NÃO-chutador mais próximo ao ponto da futura
        # reposse, medida NO turno do chute (vs o deles mais próximo)
        px, py = float(d["bx"][k]), float(d["by"][k])
        mx, my, mnum = (("hx", "hy", "hnum") if our_side == "HOME"
                        else ("ax", "ay", "anum"))
        ox, oy, onum = (("ax", "ay", "anum") if our_side == "HOME"
                        else ("hx", "hy", "hnum"))
        m_ok = (d[mnum][i] > 0) & (d[mnum][i] != 1) & (d[mnum][i] != kicker)
        o_ok = (d[onum][i] > 0) & (d[onum][i] != 1)
        if m_ok.any():
            dm = np.hypot(d[mx][i] - px, d[my][i] - py)[m_ok].min()
            out["sb_dist_ours"] += int(dm)
        if o_ok.any():
            do = np.hypot(d[ox][i] - px, d[oy][i] - py)[o_ok].min()
            out["sb_dist_theirs"] += int(do)

    # ---------------- roubo -> finalização (transição ofensiva, v7)
    # "roubo" = posse ESTABELECIDA nossa (>=MIN_RUN turnos com dono) que
    # sucede posse estabelecida deles — sem isso o flicker da disputa conta
    # centenas de micro-trocas por jogo.
    their_s = 1 - our_s
    MIN_RUN = 5
    runs = []                           # (side, start, last)
    cur_side = cur_start = last_seen = None
    for k in range(n):
        h_ = int(hold[k])
        if h_ < 0:
            continue
        if cur_side is None or h_ != cur_side:
            if cur_side is not None:
                runs.append((cur_side, cur_start, last_seen))
            cur_side, cur_start = h_, k
        last_seen = k
    if cur_side is not None:
        runs.append((cur_side, cur_start, last_seen))
    steal_at = []
    for ri in range(1, len(runs)):
        ps, p0, p1 = runs[ri - 1]
        cs, c0, c1 = runs[ri]
        if cs != our_s or ps != their_s:
            continue
        if (p1 - p0) < MIN_RUN or (c1 - c0) < MIN_RUN:
            continue
        if c0 in reset_zone:
            continue
        steal_at.append(c0)
    out["steals_total"] += len(steal_at)
    for k in steal_at:
        # primeiro on-goal nosso APÓS o roubo e ANTES da próxima posse deles
        nxt_theirs = n
        for k2 in range(k + 1, n):
            if int(hold[k2]) == their_s:
                nxt_theirs = k2
                break
        cand = our_shot_idx[(our_shot_idx > k) & (our_shot_idx < nxt_theirs)]
        if len(cand):
            dt = int(cand[0] - k)
            out["tr_fin"] += 1
            extra["rob2fin_dt"].append(dt)
            if dt <= 100:
                out["tr_fin_le100"] += 1

    # ---------------- slack dos chutes tomados (P1)
    pr = PM.proxy_for_replay(d, our_l)
    ss = pr["shot_slacks"]
    out["shots_with_slack"] = len(ss)
    out["shots_slack_pos"] = sum(1 for x in ss if x > 0)
    out["gf"] = pr["our_goals"]
    out["ga"] = pr["conceded"]
    return dict(out), extra


def aggregate(results):
    agg = Counter()
    dts = []
    for out, extra in results:
        agg.update(out)
        if extra:
            dts += extra.get("rob2fin_dt", [])
    a = dict(agg)
    ko = max(1, a.get("kickoffs", 0))
    kw = max(1, a.get("ko_won", 0))
    a["ko_won_pct"] = 100.0 * a.get("ko_won", 0) / ko
    a["ko_touch_dt_mean"] = a.get("ko_touch_dt", 0) / ko
    a["ko_third60_pct"] = 100.0 * a.get("ko_third60", 0) / kw
    a["ko_shot120_pct"] = 100.0 * a.get("ko_shot120", 0) / kw
    a["ko_disp40_mean"] = a.get("ko_disp40", 0) / kw
    sbe = max(1, a.get("sb_events", 0))
    dec = max(1, a.get("sb_won", 0) + a.get("sb_lost", 0))
    a["sb_won_pct"] = 100.0 * a.get("sb_won", 0) / dec
    a["sb_dist_ours_mean"] = a.get("sb_dist_ours", 0) / max(1, dec)
    a["sb_dist_theirs_mean"] = a.get("sb_dist_theirs", 0) / max(1, dec)
    a["shots_slack_pos_pct"] = (100.0 * a.get("shots_slack_pos", 0)
                                / max(1, a.get("shots_with_slack", 0)))
    # v7: métricas dos genes novos
    a["ko_steal100_pct"] = (100.0 * a.get("ko_steal100", 0)
                            / max(1, a.get("ko_lost", 0)))
    a["sb_reshot60_pct"] = (100.0 * a.get("sb_reshot60", 0)
                            / max(1, a.get("sb_won", 0)))
    a["tr_fin_rate_pct"] = (100.0 * a.get("tr_fin", 0)
                            / max(1, a.get("steals_total", 0)))
    a["tr_fin_dt_med"] = float(np.median(dts)) if dts else float("nan")
    return a


def print_report(a, label):
    n = a.get("n_files", 0)
    print(f"--- {label} ({n} replays) ---")
    print(f"  KICKOFFS: {a.get('kickoffs', 0)} | ganhos {a['ko_won_pct']:.0f}% "
          f"(1º toque em {a['ko_touch_dt_mean']:.1f}t) | perdidos {a.get('ko_lost', 0)}")
    print(f"    dos ganhos: chega ao terço ≤60t {a['ko_third60_pct']:.0f}% | "
          f"chute ≤120t {a['ko_shot120_pct']:.0f}% | desloc. médio +40t "
          f"{a['ko_disp40_mean']:+.0f}d")
    print(f"    GUARDA: gols sofridos ≤60t pós-reset = {a.get('ko_ga60', 0)} | "
          f"pró = {a.get('ko_gf60', 0)}")
    takers = {k: v for k, v in a.items() if k.startswith("ko_taker_")}
    if takers:
        top = ", ".join(f"#{k.split('_')[-1]}×{v}"
                        for k, v in sorted(takers.items(), key=lambda x: -x[1])[:4])
        print(f"    tomadores: {top}")
    print(f"  SEGUNDA BOLA: {a.get('sb_events', 0)} chutes s/ gol | ganha "
          f"{a['sb_won_pct']:.0f}% ({a.get('sb_won', 0)}/{a.get('sb_won', 0) + a.get('sb_lost', 0)}) "
          f"| sem reposse {a.get('sb_none', 0)}")
    print(f"    corrida no instante do chute: nosso mais próximo "
          f"{a['sb_dist_ours_mean']:.0f}d vs deles {a['sb_dist_theirs_mean']:.0f}d "
          f"(déficit {a['sb_dist_ours_mean'] - a['sb_dist_theirs_mean']:+.0f}d)")
    # v7: kickoff_race / swarm_rebound / transição vertical
    print(f"  v7: re-roubo ≤100t do kickoff perdido {a['ko_steal100_pct']:.0f}% "
          f"({a.get('ko_steal100', 0)}/{a.get('ko_lost', 0)}) | gols ≤200t "
          f"pós-reset: pró {a.get('ko_gf200', 0)} sofridos {a.get('ko_ga200', 0)}")
    print(f"  v7: rebote aproveitado (rechute ≤60t) {a['sb_reshot60_pct']:.0f}% "
          f"({a.get('sb_reshot60', 0)}/{a.get('sb_won', 0)}) | roubos "
          f"{a.get('steals_total', 0)} → finalização {a['tr_fin_rate_pct']:.0f}% "
          f"(dt mediano {a['tr_fin_dt_med']:.0f}t; ≤100t: {a.get('tr_fin_le100', 0)})")
    print(f"  SLACK: {a['shots_slack_pos_pct']:.0f}% dos chutes com folga>0 "
          f"(n={a.get('shots_with_slack', 0)}) | gols {a.get('gf', 0)}x{a.get('ga', 0)}")


def side_of(path):
    return "AWAY" if "_away" in os.path.basename(path) else "HOME"


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
