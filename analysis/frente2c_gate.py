#!/usr/bin/env python3
"""
FRENTE 2c — o portão do chute e a qualidade dos passes.

(1) Reexecuta a lógica de _best_shot_target sobre os replays, turno a turno,
    em cada turno em que estamos com a bola a <= 6000d do gol, e conta quantas
    vezes o portão abre e, quando fecha, POR QUÊ (linha bloqueada x goleiro).
    Quando a linha bloqueia, registra a que distância do CHUTADOR está o
    adversário que bloqueou — para separar "marcador colado" de "defensor na
    frente do gol".

(2) Taxa de acerto dos nossos passes e o que os passes rendem.

Reimplementa geometry.py aqui (mesmas fórmulas) para não depender do lugo4py.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frente2_possession import (MATCHES, REC, MAX_X, GOAL_MIN_Y, GOAL_MAX_Y,
                                load_turns, detect_kicks, classify_kick,
                                segment_possessions, dist, pct)  # noqa: E402

BALL_MAX_SPEED = 400.0
BALL_DECEL = 10.0
BALL_MIN_SPEED = 2.0
PLAYER_SPEED = 100.0
TOUCH_RADIUS = 300.0
GK_HALF = 560.0
GK_JUMP_SPEED, GK_JUMP_DUR = 200.0, 3
GOALKEEPER = 1
SHOT_POST_MARGIN = 200.0
SHOT_RANGE = 6000.0
MAX_KICK_RANGE = 8000.0


def ball_step(v):
    return max(0.0, v - BALL_DECEL / 2)


def turns_for_ball(v0, d):
    v0 = min(v0, BALL_MAX_SPEED)
    trav, v, t = 0.0, v0, 0
    while v > BALL_MIN_SPEED:
        trav += ball_step(v)
        v -= BALL_DECEL
        t += 1
        if trav >= d:
            return t
    return math.inf


def turns_for_player(d):
    return max(0.0, d - TOUCH_RADIUS) / PLAYER_SPEED


def blocking_opponent(origin, target, opps, kick_speed):
    """Retorna (bloqueou?, adversário mais 'culpado', frac onde bloqueou)."""
    total = dist(origin, target)
    if total == 0:
        return False, None, 0
    for i in range(1, 9):
        frac = i / 8
        px = origin[0] + (target[0] - origin[0]) * frac
        py = origin[1] + (target[1] - origin[1]) * frac
        t_ball = turns_for_ball(kick_speed, total * frac)
        if t_ball == math.inf:
            return True, None, frac
        for o in opps:
            if turns_for_player(dist((px, py), o)) <= t_ball:
                return True, o, frac
    return False, None, 0


def gate(me, opps, gk, goal_x):
    """Reproduz _best_shot_target. Retorna (aberto?, motivo, detalhe)."""
    reasons = Counter()
    detail = []
    for i in range(9):
        frac = i / 8
        y = GOAL_MIN_Y + SHOT_POST_MARGIN + frac * (
            GOAL_MAX_Y - GOAL_MIN_Y - 2 * SHOT_POST_MARGIN)
        target = (goal_x, y)
        d = dist(me, target)
        if d > MAX_KICK_RANGE:
            reasons["fora de alcance"] += 1
            continue
        blocked, who, fr = blocking_opponent(me, target, opps, BALL_MAX_SPEED)
        if blocked:
            reasons["linha bloqueada"] += 1
            detail.append(("linha", dist(me, who) if who else -1, fr))
            continue
        t_ball = turns_for_ball(BALL_MAX_SPEED, d)
        if t_ball == math.inf:
            reasons["fora de alcance"] += 1
            continue
        if gk is not None:
            jt = min(t_ball, GK_JUMP_DUR)
            reach = GK_JUMP_SPEED * jt + PLAYER_SPEED * max(0, t_ball - jt)
            if dist(gk, target) - GK_HALF <= reach:
                reasons["goleiro alcança"] += 1
                detail.append(("gk", dist(gk, target), t_ball))
                continue
        return True, None, None
    top = reasons.most_common(1)[0][0] if reasons else "?"
    return False, top, detail


def run(path, our_side, label):
    turns, goals = load_turns(path)
    their = "AWAY" if our_side == "HOME" else "HOME"
    attack_x = {"HOME": MAX_X, "AWAY": 0}
    gx = attack_x[our_side]
    goal_c = (gx, 5000)

    kicks = detect_kicks(turns)
    for k in kicks:
        k["tipo"] = classify_kick(k, turns, attack_x)

    open_n = 0
    closed = Counter()
    block_dists = []
    block_fracs = Counter()
    total = 0
    for T in turns:
        h = T["holder"]
        if not h or h[0] != our_side:
            continue
        if dist(T["ball"], goal_c) > SHOT_RANGE:
            continue
        total += 1
        me = T["players"][our_side].get(h[1], T["ball"])
        opps = T["players"][their]
        gkp = opps.get(GOALKEEPER)
        others = [p for num, p in opps.items() if num != GOALKEEPER]
        ok, why, det = gate(me, others, gkp, gx)
        if ok:
            open_n += 1
        else:
            closed[why] += 1
            for kind, dd, fr in (det or []):
                if kind == "linha" and dd >= 0:
                    block_dists.append(dd)
                    block_fracs[round(fr * 8)] += 1

    # ---------------- passes
    our_pass = [k for k in kicks if k["side"] == our_side and k["tipo"] == "passe"]
    ok_pass = bad_pass = 0
    gain = []
    for k in our_pass:
        i = k["i"]
        res = None
        for j in range(i + 1, min(i + 60, len(turns))):
            hh = turns[j]["holder"]
            if hh:
                res = hh[0]
                break
        if res == our_side:
            ok_pass += 1
            adv = (turns[j]["ball"][0] - k["pos"][0])
            gain.append(adv if gx == MAX_X else -adv)
        elif res is not None:
            bad_pass += 1

    # ---------------- condução: quanto tempo cada portador segura
    streaks = []
    cur = None
    ln = 0
    for T in turns:
        h = T["holder"]
        key = h if h and h[0] == our_side else None
        if key and key == cur:
            ln += 1
        else:
            if cur:
                streaks.append(ln)
            cur, ln = key, 1 if key else 0
    if cur:
        streaks.append(ln)
    streaks.sort()

    print("=" * 78)
    print(f"{label}  ({os.path.basename(path)})")
    print("=" * 78)
    print(f"turnos com a bola nossa dentro de 6000d do gol: {total}")
    if total:
        print(f"  PORTÃO DO CHUTE ABERTO em {open_n} ({pct(open_n, total):.1f}%)")
        for r, v in closed.most_common():
            print(f"    fechado por {r:<20} {v:>5} ({pct(v, total):>5.1f}%)")
        if block_dists:
            block_dists.sort()
            m = block_dists[len(block_dists) // 2]
            print(f"  quando a linha bloqueia: distância do adversário "
                  f"bloqueador ao CHUTADOR — mediana {m:.0f}d, "
                  f"p25={block_dists[len(block_dists)//4]:.0f}, "
                  f"p75={block_dists[3*len(block_dists)//4]:.0f}; "
                  f"{pct(sum(1 for d in block_dists if d < 1500), len(block_dists)):.0f}%"
                  f" a menos de 1500d (marcador colado, não defensor no gol)")
            print(f"  ponto da linha onde o bloqueio é detectado (1=colado no "
                  f"chutador, 8=gol): "
                  + " ".join(f"{i}:{pct(block_fracs[i], sum(block_fracs.values())):.0f}%"
                             for i in sorted(block_fracs)))
    print(f"\npasses nossos: {len(our_pass)} | chegaram a um companheiro "
          f"{ok_pass} ({pct(ok_pass, max(1,len(our_pass))):.0f}%) | "
          f"foram para o adversário {bad_pass} "
          f"({pct(bad_pass, max(1,len(our_pass))):.0f}%)")
    if gain:
        gain.sort()
        print(f"  avanço em x do passe completado: mediana "
              f"{gain[len(gain)//2]:+.0f}d, média {sum(gain)/len(gain):+.0f}d")
    if streaks:
        print(f"\ncondução: {len(streaks)} sequências de um mesmo jogador com "
              f"a bola | mediana {streaks[len(streaks)//2]} turnos, "
              f"média {sum(streaks)/len(streaks):.1f}, máx {streaks[-1]}")
    print()
    return dict(label=label, total=total, open_n=open_n, closed=closed,
                npass=len(our_pass), okp=ok_pass, badp=bad_pass,
                blockclose=pct(sum(1 for d in block_dists if d < 1500),
                               max(1, len(block_dists))))


if __name__ == "__main__":
    sel = sys.argv[1:]
    rows = []
    for fn, side, label in MATCHES:
        if sel and not any(s in fn for s in sel):
            continue
        p = os.path.join(REC, fn)
        if os.path.exists(p):
            rows.append(run(p, side, label))
    print("=" * 100)
    print(f"{'partida':<32}{'t/zona':>8}{'portão aberto':>15}{'lin.bloq':>10}"
          f"{'gk':>8}{'passes':>8}{'ok%':>6}{'p/adv%':>8}")
    for r in rows:
        t = max(1, r["total"])
        print(f"{r['label']:<32}{r['total']:>8}"
              f"{r['open_n']:>7} ({pct(r['open_n'],t):>4.1f}%)"
              f"{pct(r['closed']['linha bloqueada'],t):>9.0f}%"
              f"{pct(r['closed']['goleiro alcança'],t):>7.0f}%"
              f"{r['npass']:>8}{pct(r['okp'],max(1,r['npass'])):>6.0f}"
              f"{pct(r['badp'],max(1,r['npass'])):>8.0f}")
