#!/usr/bin/env python3
"""Metrica PROXY densa para avaliar heuristicas com BAIXO RUIDO (item 1 do plano
results/PLANO_HEURISTICAS_2026-08-12.md).

Em vez de contar gols (~1/jogo, sigma~0,9 -> precisa de ~centenas de jogos),
medimos a FOLGA TEMPORAL do goleiro por CHANCE (muitas amostras/jogo):

    slack = |alvo.y - gk.y| - (560 + 200 * t_bola)      ; >0 => goleiro nao cobre

onde 560 = meia-extensao efetiva do goleiro e 200*t = quanto ele anda em t turnos
ate a bola chegar. Do NOSSO lado, a partir dos replays, reporta:

  CRIACAO DE CHANCE (independe da decisao de chute -> mede movimentacao/tatica):
    sobre os turnos em que seguramos a bola a <=6000d do gol, o MELHOR slack
    entre 9 miras com lane livre. => media, fracao>0, posses-perigo, chances boas.
  SELECAO DE CHUTE: slack dos chutes que de fato tomamos (media, fracao>0, n).
  FUSIVEL defensivo (guarda o zero sofrido): turnos em que o ADVERSARIO segura a
    bola a <=6000d do NOSSO gol.

O lado do nosso bot vem do nome do replay (_home / _away).

Uso: .venv/bin/python bench/proxy_metric.py ["recordings/fin_*.json"]
"""
import glob
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import replay as R          # noqa: E402
import metrics_lab as M     # noqa: E402

GK_HALF = 560.0
# CALIBRADO contra 127 chutes rotulados (fin_*.json vs level-1): gk_speed=75 dá
# AUC 0,868 do slack vs gol (slack>0 converte 43%, slack<=0 converte 0%). O 200
# do plano era o erro pessimista da v6/v8 (AUC 0,814); o medido no HANDOFF era
# ~100/turno. 75 é o ótimo empírico e supera o modelo logistico de 4 features
# (AUC 0,81). Ver a calibracao em fit_finishing/proxy.
GK_SPEED = 75.0
DANGER = 6000.0
GOAL_LO, GOAL_HI = 3500.0, 6500.0
GOAL_C = 5000.0
LANE_MARGIN = 450.0
TARGETS = [GOAL_LO + 250 + i * (GOAL_HI - GOAL_LO - 500) / 8 for i in range(9)]


def turns_for_ball(v0, d):
    """Turnos para a bola cobrir d (fisica trapezoidal do servidor). inf se nao."""
    v0 = min(v0, 400.0)
    trav, v, t = 0.0, v0, 0
    while v > 2.0:
        trav += max(0.0, v - 5.0)
        v -= 10.0
        t += 1
        if trav >= d:
            return t
    return math.inf


def build_d(path):
    """Replay -> dict de arrays por turno (mesma logica de fit_finishing)."""
    cfg, ev = R.load(path)
    snaps = [e["game_snapshot"] for e in ev if "game_snapshot" in e]
    by_turn, score_by_turn = {}, {}
    for s in snaps:
        t = s.get("turn", 0)
        h, a = R.score(s, "home"), R.score(s, "away")
        prev = score_by_turn.get(t, (0, 0))
        score_by_turn[t] = (max(prev[0], h), max(prev[1], a))
        if s.get("state") == "LISTENING" or t not in by_turn:
            by_turn[t] = s
    turns = sorted(by_turn)
    n = len(turns)
    out = {
        "turn": np.zeros(n, np.int32),
        "bx": np.zeros(n, np.float32), "by": np.zeros(n, np.float32),
        "bspeed": np.zeros(n, np.float32),
        "bdx": np.zeros(n, np.float32), "bdy": np.zeros(n, np.float32),
        "hold_side": np.zeros(n, np.int8), "hold_num": np.zeros(n, np.int8),
        "sc_home": np.zeros(n, np.int16), "sc_away": np.zeros(n, np.int16),
        "hx": np.zeros((n, 11), np.float32), "hy": np.zeros((n, 11), np.float32),
        "ax": np.zeros((n, 11), np.float32), "ay": np.zeros((n, 11), np.float32),
        "hnum": np.zeros((n, 11), np.int8), "anum": np.zeros((n, 11), np.int8),
    }
    for i, t in enumerate(turns):
        s = by_turn[t]
        out["turn"][i] = t
        bx, by = R.ball_pos(s)
        out["bx"][i], out["by"][i] = bx, by
        vel = (R.ball(s).get("velocity") or {})
        out["bspeed"][i] = vel.get("speed", 0)
        dirn = vel.get("direction") or {}
        out["bdx"][i], out["bdy"][i] = dirn.get("x", 0), dirn.get("y", 0)
        hold = R.holder(s)
        if hold is None:
            out["hold_side"][i] = -1
        else:
            out["hold_side"][i] = 1 if hold[0] == "AWAY" else 0
            out["hold_num"][i] = hold[1]
        h, a = score_by_turn[t]
        out["sc_home"][i], out["sc_away"][i] = h, a
        for side, kx, ky, kn in (("home", "hx", "hy", "hnum"),
                                 ("away", "ax", "ay", "anum")):
            for j, p in enumerate(R.players(s, side)[:11]):
                px, py = R.pt(p.get("position"))
                out[kx][i, j], out[ky][i, j] = px, py
                out[kn][i, j] = p.get("number", 0)
    return out


def _dist_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    tt = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + tt * vx), py - (ay + tt * vy))


def proxy_for_replay(d, side):
    s = 0 if side == "home" else 1
    gx = 20000.0 if side == "home" else 0.0      # gol que ATACAMOS
    own_gx = 0.0 if side == "home" else 20000.0  # NOSSO gol
    ox, oy, onum = (("ax", "ay", "anum") if side == "home" else ("hx", "hy", "hnum"))
    n = len(d["turn"])
    hold, bx, by = d["hold_side"], d["bx"], d["by"]

    segs = M.possessions(d, side)
    seg_start = np.array([a for a, b in segs], dtype=np.int64) if segs else np.array([], np.int64)
    seg_end = np.array([b for a, b in segs], dtype=np.int64) if segs else np.array([], np.int64)

    def poss_of(i):
        for k in range(len(seg_start)):
            if seg_start[k] <= i <= seg_end[k]:
                return k
        return -1

    best_slacks = []
    danger_poss, good_chance_poss = set(), set()
    opp_danger = 0
    for i in range(n):
        if hold[i] == s and math.hypot(gx - bx[i], GOAL_C - by[i]) <= DANGER:
            k = np.where(d[onum][i] == 1)[0]
            gk_y = float(d[oy][i, k[0]]) if len(k) else GOAL_C
            opps = [(float(d[ox][i, j]), float(d[oy][i, j]))
                    for j in range(11) if d[onum][i, j] > 0 and d[onum][i, j] != 1]
            best = -1e9
            for ty in TARGETS:
                dd = math.hypot(gx - bx[i], ty - by[i])
                t = turns_for_ball(400.0, dd)
                if t == math.inf:
                    continue
                if any(_dist_seg(px, py, bx[i], by[i], gx, ty) < LANE_MARGIN
                       for px, py in opps):
                    continue
                sl = abs(ty - gk_y) - (GK_HALF + GK_SPEED * t)
                if sl > best:
                    best = sl
            if best > -1e8:
                best_slacks.append(best)
                pid = poss_of(i)
                if pid >= 0:
                    danger_poss.add(pid)
                    if best > 0:
                        good_chance_poss.add(pid)
        if hold[i] == (1 - s) and math.hypot(own_gx - bx[i], GOAL_C - by[i]) <= DANGER:
            opp_danger += 1

    ev, _ = M.mark_shots(d, side)
    shot_slacks = []
    for e in [x for x in ev if x.get("on_goal")]:
        if e["dist_line"] is None:
            continue
        t = turns_for_ball(e["v"], e["dist_line"])
        if t == math.inf:
            continue
        j = e["i"]
        k = np.where(d[onum][j] == 1)[0]
        gk_y = float(d[oy][j, k[0]]) if len(k) else GOAL_C
        shot_slacks.append(abs(e["ycross"] - gk_y) - (GK_HALF + GK_SPEED * t))

    our_goals = int(d["sc_home"][-1]) if side == "home" else int(d["sc_away"][-1])
    conceded = int(d["sc_away"][-1]) if side == "home" else int(d["sc_home"][-1])
    return dict(best_slacks=best_slacks, danger_poss=len(danger_poss),
                good_chances=len(good_chance_poss), shot_slacks=shot_slacks,
                opp_danger=opp_danger, our_goals=our_goals, conceded=conceded)


def side_of(path):
    return "away" if "_away" in os.path.basename(path) else "home"


def summarize(files):
    bs, ss = [], []
    danger_poss = good = opp_danger = 0
    goals = conceded = ok = 0
    for p in files:
        try:
            d = build_d(p)
        except Exception as e:
            print(f"  {os.path.basename(p)}: erro ({e})", file=sys.stderr)
            continue
        r = proxy_for_replay(d, side_of(p))
        bs += r["best_slacks"]
        ss += r["shot_slacks"]
        danger_poss += r["danger_poss"]
        good += r["good_chances"]
        opp_danger += r["opp_danger"]
        goals += r["our_goals"]
        conceded += r["conceded"]
        ok += 1
    nb = len(bs) or 1
    ns = len(ss) or 1
    return dict(
        n_replays=ok,
        # criacao de chance (o alvo principal das heuristicas ofensivas)
        best_slack_mean=sum(bs) / nb,
        best_slack_frac_pos=sum(1 for x in bs if x > 0) / nb,
        danger_hold_turns=len(bs),
        danger_poss=danger_poss,
        good_chances=good,
        good_chance_rate=good / (danger_poss or 1),
        # selecao de chute
        shot_slack_mean=sum(ss) / ns,
        shot_slack_frac_pos=sum(1 for x in ss if x > 0) / ns,
        n_shots=len(ss),
        # fusivel
        opp_danger_turns=opp_danger,
        # gols (confirmacao final; ruidoso)
        goals_mean=goals / (ok or 1),
        conceded_mean=conceded / (ok or 1),
    )


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "recordings", "fin_*.json")
    files = sorted(glob.glob(pat))
    if not files:
        print(f"nenhum replay em {pat}")
        return
    m = summarize(files)
    print(f"=== PROXY sobre {m['n_replays']} replays ({pat}) ===")
    print("CRIACAO DE CHANCE (melhor slack disponivel quando seguramos no perigo):")
    print(f"  best_slack medio      = {m['best_slack_mean']:+.1f}")
    print(f"  fracao turnos slack>0 = {m['best_slack_frac_pos']:.3f}")
    print(f"  turnos-perigo (posse) = {m['danger_hold_turns']}")
    print(f"  posses-perigo         = {m['danger_poss']}")
    print(f"  chances boas (slack>0)= {m['good_chances']}  (taxa {m['good_chance_rate']:.3f})")
    print("SELECAO DE CHUTE (chutes tomados):")
    print(f"  shot_slack medio      = {m['shot_slack_mean']:+.1f}")
    print(f"  fracao chutes slack>0 = {m['shot_slack_frac_pos']:.3f}  (n={m['n_shots']})")
    print("FUSIVEL defensivo:")
    print(f"  turnos adversario no nosso perigo = {m['opp_danger_turns']}")
    print(f"GOLS (confirmacao, ruidoso): {m['goals_mean']:.2f} pro / {m['conceded_mean']:.2f} contra por jogo")


if __name__ == "__main__":
    main()
