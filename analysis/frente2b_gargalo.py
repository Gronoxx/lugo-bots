#!/usr/bin/env python3
"""
FRENTE 2b — o gargalo é chegar ou é finalizar depois de chegar?

Mede, por partida:
  - quantas posses nossas chegam a <= dangerous_shot_range (6000d) do gol;
  - quantos turnos passamos SEGURANDO a bola dentro dessa faixa;
  - quantas finalizações saem disso  -> taxa de disparo por turno em zona;
  - o que acontece logo depois de cada perda (a bola realmente muda de mão?);
  - reproduz a contagem antiga de "finalizações" (compare_sides.py) para
    mostrar de onde vinha o 43-81.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay  # noqa: E402
from frente2_possession import (MATCHES, REC, MAX_X, GOAL_MIN_Y, GOAL_MAX_Y,
                                load_turns, detect_kicks, classify_kick,
                                segment_possessions, dist, ball_range, pct)  # noqa: E402


def run(path, our_side, label):
    turns, goals = load_turns(path)
    n = len(turns)
    their = "AWAY" if our_side == "HOME" else "HOME"
    attack_x = {"HOME": MAX_X, "AWAY": 0}
    gx = attack_x[our_side]
    goal_c = (gx, 5000)

    kicks = detect_kicks(turns)
    for k in kicks:
        k["tipo"] = classify_kick(k, turns, attack_x)
    our_shots = [k for k in kicks if k["side"] == our_side and k["tipo"] == "chute"]
    shot_i = {k["i"] for k in our_shots}

    # --- turnos com a bola em nossa posse dentro / fora do alcance de chute
    inzone = outzone = 0
    inzone_free = 0        # em zona e SEM adversário a menos de 1200d
    d_hist = []
    for T in turns:
        h = T["holder"]
        if not h or h[0] != our_side:
            continue
        d = dist(T["ball"], goal_c)
        d_hist.append(d)
        if d <= 6000:
            inzone += 1
            dmin = min((dist(T["ball"], p) for p in T["players"][their].values()),
                       default=1e9)
            if dmin > 1200:
                inzone_free += 1
        else:
            outzone += 1

    # --- posses: chegou à zona? finalizou?
    poss = segment_possessions(turns)
    ours = [p for p in poss if p["side"] == our_side]
    reached = shot_from_reached = 0
    zone_turns_per_poss = []
    for p in ours:
        seg = turns[p["i0"]:p["i1"] + 1]
        zt = sum(1 for T in seg
                 if T["holder"] and T["holder"][0] == our_side
                 and dist(T["ball"], goal_c) <= 6000)
        zone_turns_per_poss.append(zt)
        if zt > 0:
            reached += 1
            if any(p["i0"] <= i <= p["i1"] + 4 for i in shot_i):
                shot_from_reached += 1

    # --- distância mínima ao gol atingida por posse (com a bola sob controle)
    dmin_poss = []
    for p in ours:
        seg = turns[p["i0"]:p["i1"] + 1]
        dd = [dist(T["ball"], goal_c) for T in seg
              if T["holder"] and T["holder"][0] == our_side]
        dmin_poss.append(min(dd) if dd else 1e9)
    dmin_poss = [d for d in dmin_poss if d < 1e9]
    buckets = Counter()
    for d in dmin_poss:
        b = int(d // 2000) * 2000
        buckets[b] += 1

    # --- o que acontece depois de uma perda: a bola vira mesmo?
    flips = []
    for a, b in zip(ours, ours[1:]):
        j = b["i0"]              # início da próxima posse nossa
        i = a["i1"]
        if j - i <= 0:
            continue
        flips.append(j - i)
    flips.sort()

    # --- contagem ANTIGA de finalização (compare_sides.py), por snapshot
    _cfg, events = replay.load(path)
    old = 0
    prev_hold = None
    for gs in replay.snapshots(events):
        bx, by = replay.ball_pos(gs)
        h = replay.holder(gs)
        sp = replay.ball_speed(gs)
        if h is None and sp > 250 and GOAL_MIN_Y - 500 <= by <= GOAL_MAX_Y + 500:
            if abs(bx - gx) < 7000 and prev_hold is not None:
                old += 1
        prev_hold = h

    gf = len([1 for s, _ in goals if s == our_side])
    print("=" * 78)
    print(f"{label}  ({os.path.basename(path)})  gols {gf}")
    print("=" * 78)
    print(f"turnos com a bola sob nosso controle: {inzone + outzone}")
    print(f"  DENTRO do alcance de chute (<=6000d do gol): {inzone} "
          f"({pct(inzone, inzone + outzone):.0f}%) — desses, "
          f"{inzone_free} ({pct(inzone_free, max(1,inzone)):.0f}%) sem "
          f"adversário a menos de 1200d")
    print(f"  finalizações a gol detectadas: {len(our_shots)}  -> "
          f"{pct(len(our_shots), max(1,inzone)):.2f} chutes por 100 turnos "
          f"em zona ({inzone} turnos em zona por {len(our_shots)} chutes = "
          f"1 chute a cada {inzone/max(1,len(our_shots)):.0f} turnos)")
    print(f"  contagem ANTIGA (compare_sides.py, 'bola solta rápida na faixa "
          f"do gol'): {old}")
    print(f"\nposses nossas: {len(ours)} | chegaram à zona de chute: {reached} "
          f"({pct(reached, len(ours)):.0f}%) | dessas, finalizaram: "
          f"{shot_from_reached} ({pct(shot_from_reached, max(1,reached)):.0f}%)")
    print(f"  turnos em zona por posse que chegou: "
          f"{sum(zone_turns_per_poss)/max(1,reached):.1f}")
    print("  distância mínima ao gol alcançada com a bola, por posse:")
    for b in sorted(buckets):
        print(f"    {b:>6}-{b+2000:<6}: {buckets[b]:>3} "
              f"({pct(buckets[b], len(dmin_poss)):>4.0f}%)")
    if flips:
        print(f"\napós perder, voltamos a ter a bola em mediana "
              f"{flips[len(flips)//2]} turnos "
              f"(p25={flips[len(flips)//4]}, p75={flips[3*len(flips)//4]}); "
              f"{sum(1 for f in flips if f <= 5)}/{len(flips)} perdas são "
              f"recuperadas em <=5 turnos")
    print()
    return dict(label=label, inzone=inzone, shots=len(our_shots), old=old,
                gf=gf, poss=len(ours), reached=reached,
                shot_reached=shot_from_reached, inzone_free=inzone_free)


if __name__ == "__main__":
    sel = sys.argv[1:]
    rows = []
    for fn, side, label in MATCHES:
        if sel and not any(s in fn for s in sel):
            continue
        p = os.path.join(REC, fn)
        if os.path.exists(p):
            rows.append(run(p, side, label))
    print("=" * 108)
    print(f"{'partida':<32}{'gols':>5}{'posses':>7}{'chegam':>8}{'%fin':>7}"
          f"{'t/zona':>8}{'livre':>7}{'chutes':>8}{'antigo':>8}{'conv%':>7}")
    for r in rows:
        print(f"{r['label']:<32}{r['gf']:>5}{r['poss']:>7}{r['reached']:>8}"
              f"{pct(r['shot_reached'], max(1,r['reached'])):>7.0f}"
              f"{r['inzone']:>8}{r['inzone_free']:>7}{r['shots']:>8}"
              f"{r['old']:>8}{pct(r['gf'], max(1,r['shots'])):>7.0f}")
