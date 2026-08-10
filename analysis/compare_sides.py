#!/usr/bin/env python3
"""
Compara o desempenho do nosso bot jogando como HOME vs como AWAY.

Marcamos 6 e 4 gols como HOME, mas só 3 como AWAY. Ou é ruído, ou há uma
assimetria real no bot. Este script procura a causa medindo, para cada
partida, o que o nosso time fez — sempre da NOSSA perspectiva, independente
do lado.
"""
import sys
from collections import Counter

import replay
from replay import ball_pos, ball_speed, holder, players, pt, score

MAX_X = 20000
MAX_Y = 10000
GOAL_MIN_Y, GOAL_MAX_Y = 3500, 6500


def analyze(path, our_side):
    """our_side: 'home' ou 'away'."""
    cfg, events = replay.load(path)
    snaps = list(replay.snapshots(events))
    their_side = "away" if our_side == "home" else "home"

    # o gol que atacamos
    our_attack_x = MAX_X if our_side == "home" else 0
    our_defend_x = 0 if our_side == "home" else MAX_X

    stats = Counter()
    n = 0
    prev_hold = None
    prev_speed = 0

    for gs in snaps:
        n += 1
        bx, by = ball_pos(gs)
        h = holder(gs)

        # posse
        if h is None:
            stats["loose"] += 1
        elif h[0].lower() == our_side.upper().lower() or \
                h[0].lower() == our_side:
            stats["poss_ours"] += 1
        else:
            stats["poss_theirs"] += 1

        # território: a bola está no terço de ataque nosso?
        adv = bx / MAX_X if our_side == "home" else 1 - bx / MAX_X
        if adv > 0.66:
            stats["ball_attacking_third"] += 1
        elif adv < 0.33:
            stats["ball_defending_third"] += 1
        else:
            stats["ball_middle"] += 1

        # finalizações: bola solta, rápida, indo para o gol adversário,
        # dentro da faixa vertical do gol
        sp = ball_speed(gs)
        if h is None and sp > 250 and GOAL_MIN_Y - 500 <= by <= GOAL_MAX_Y + 500:
            near_their_goal = abs(bx - our_attack_x) < 7000
            near_our_goal = abs(bx - our_defend_x) < 7000
            if near_their_goal and prev_hold is not None:
                stats["shots_ours"] += 1
            if near_our_goal and prev_hold is not None:
                stats["shots_theirs"] += 1

        # posses perdidas: tínhamos a bola e o adversário passou a ter
        if prev_hold is not None and h is not None:
            was_ours = prev_hold[0].lower() == our_side
            is_ours = h[0].lower() == our_side
            if was_ours and not is_ours:
                stats["turnovers"] += 1

        prev_hold = h
        prev_speed = sp

    last = snaps[-1]
    gf = score(last, our_side)
    ga = score(last, their_side)
    return {
        "gols_pro": gf,
        "gols_contra": ga,
        "snapshots": n,
        "posse_%": 100 * stats["poss_ours"] / max(1, stats["poss_ours"] + stats["poss_theirs"]),
        "terco_ataque_%": 100 * stats["ball_attacking_third"] / n,
        "terco_defesa_%": 100 * stats["ball_defending_third"] / n,
        "finalizacoes_nossas": stats["shots_ours"],
        "finalizacoes_deles": stats["shots_theirs"],
        "posses_perdidas": stats["turnovers"],
    }


if __name__ == "__main__":
    cases = [
        ("../bench/recordings/t1.json", "home", "v1 como HOME"),
        ("../bench/recordings/eval_0_norm.json", "home", "v2 como HOME"),
        ("../bench/recordings/swap.json", "away", "v3 como AWAY"),
    ]
    rows = []
    for path, side, label in cases:
        try:
            r = analyze(path, side)
            rows.append((label, r))
        except Exception as e:
            print(f"{label}: erro {e}")

    keys = list(rows[0][1].keys())
    w = max(len(k) for k in keys)
    print(f"{'métrica'.ljust(w)} | " + " | ".join(f"{l:>16}" for l, _ in rows))
    print("-" * (w + 3 + 19 * len(rows)))
    for k in keys:
        vals = []
        for _, r in rows:
            v = r[k]
            vals.append(f"{v:>16.1f}" if isinstance(v, float) else f"{v:>16}")
        print(f"{k.ljust(w)} | " + " | ".join(vals))
