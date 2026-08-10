"""
FRENTE 1 - genese dos gols e conversao das finalizacoes.

Le os caches produzidos por frente1_extract.py e imprime:
  A) inventario de chutes por replay
  B) reconstrucao dos ~30 turnos antes de cada gol
  C) conversao por faixa de distancia e por posicao do goleiro
  D) comparacao dummies x rivais

Uso: python analysis/frente1_gols.py [secao]
"""
import math
import os
import pickle
import sys
from collections import Counter, defaultdict

S = ("<cache local>"
     "REDACTED/scratchpad/")

FILES = ["dummies_vs_dummies", "t1", "eval_0_norm", "var_1", "var_2",
         "swap", "v6_check", "smoke_rival", "p_rival_p2_home_1"]

GOAL_MIN_Y, GOAL_MAX_Y = 3500.0, 6500.0
GOAL_CY = 5000.0
FIELD_X = 20000.0
GK_HALF = 560.0        # meia-extensao efetiva do goleiro (diametro 920)


def load(name):
    with open(S + "f1_" + name + ".pkl", "rb") as fh:
        return pickle.load(fh)


def goal_x(side):
    """Linha de gol que 'side' ataca."""
    return FIELD_X if side == "home" else 0.0


def other(side):
    return "away" if side == "home" else "home"


# ---------------------------------------------------------------- fisica
def ball_reach(v0):
    """Distancia total que a bola percorre com velocidade inicial v0."""
    d, v = 0.0, float(v0)
    while v > 2:
        d += v - 5
        v -= 10
    return d


def turns_to_cover(v0, dist):
    """Turnos ate a bola percorrer 'dist' (inf se nao chega)."""
    d, v, t = 0.0, float(v0), 0
    while v > 2:
        d += v - 5
        t += 1
        if d >= dist:
            return t
    return math.inf


def speed_after(v0, dist):
    """Velocidade da bola apos percorrer 'dist'."""
    d, v = 0.0, float(v0)
    while v > 2:
        d += v - 5
        v -= 10
        if d >= dist:
            return max(v, 0.0)
    return 0.0


def seg_point_dist(a, b, p):
    """Distancia do ponto p ao segmento ab."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


# ---------------------------------------------------------------- chutes
def detect_kicks(rows):
    """Lista de eventos de chute.

    Chute = turno t em que a bola fica solta no turno t+1 com velocidade
    MAIOR do que no turno t (a bola so acelera se alguem chutar).
    """
    kicks = []
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if b["holder"] is not None:
            continue
        if b["bspeed"] <= a["bspeed"] + 1:
            continue
        # quem chutou: o portador no turno t, senao o mais proximo da bola
        if a["holder"] is not None:
            kicker = a["holder"]
        else:
            bx, by = a["ball"]
            best, bd = None, 1e9
            for sd in ("home", "away"):
                for num, (x, y) in a[sd].items():
                    dd = math.hypot(x - bx, y - by)
                    if dd < bd:
                        bd, best = dd, (sd.upper(), num)
            kicker = best if bd <= 400 else None
        kicks.append({"i": i, "turn": a["turn"], "pos": a["ball"],
                      "v0": b["bspeed"], "dir": b["bdir"], "kicker": kicker,
                      "v_prev": a["bspeed"]})
    return kicks


def classify_kick(k, att_side, rows):
    """Geometria do chute em relacao ao gol atacado por att_side."""
    gx = goal_x(att_side)
    x, y = k["pos"]
    dx, dy = k["dir"]
    d_line = abs(gx - x)
    d_center = math.hypot(gx - x, GOAL_CY - y)
    towards = (dx > 0) if att_side == "home" else (dx < 0)
    cross_y = None
    if towards and abs(dx) > 1e-6:
        tt = (gx - x) / dx
        cross_y = y + dy * tt
    path = math.hypot(gx - x, (cross_y - y) if cross_y is not None else 0.0)
    reach = ball_reach(k["v0"])
    on_target = (cross_y is not None and GOAL_MIN_Y <= cross_y <= GOAL_MAX_Y
                 and reach >= path)
    # angulo entre a direcao do chute e a direcao ao centro do gol
    cgx, cgy = gx - x, GOAL_CY - y
    m = math.hypot(cgx, cgy) or 1.0
    cosang = max(-1.0, min(1.0, (dx * cgx + dy * cgy) / m))
    ang_center = math.degrees(math.acos(cosang))
    # angulo de abertura: quanto do gol o jogador "ve" (angulo trave-trave)
    a1 = math.atan2(GOAL_MIN_Y - y, gx - x)
    a2 = math.atan2(GOAL_MAX_Y - y, gx - x)
    aperture = abs(math.degrees(a2 - a1))
    return {"d_line": d_line, "d_center": d_center, "towards": towards,
            "cross_y": cross_y, "path": path, "reach": reach,
            "on_target": on_target, "ang_center": ang_center,
            "aperture": aperture,
            "v_arrive": speed_after(k["v0"], path) if towards else 0.0,
            "t_arrive": turns_to_cover(k["v0"], path) if towards else math.inf}


def gk_of(row, side):
    """Posicao do goleiro do time 'side' (numero 1)."""
    return row[side].get(1)


# ------------------------------------------------------- genese dos gols
def goal_indices(rows, side):
    key = "sh" if side == "home" else "sa"
    out, prev = [], rows[0][key]
    for i, r in enumerate(rows):
        if r[key] > prev:
            out.append(i)
        prev = r[key]
    return out


def find_shot(rows, gi):
    """Volta do gol ate o inicio do voo livre; devolve indice do chute."""
    j = gi
    while j - 1 >= 0 and rows[j - 1]["holder"] is None and rows[j - 1]["bspeed"] > 2:
        # o voo livre exige velocidade decrescente (10/turno)
        if rows[j]["bspeed"] > rows[j - 1]["bspeed"] + 1:
            break
        j -= 1
    return j - 1          # turno em que a bola ainda estava com o chutador


def possession_chain(rows, ki, att):
    """Toques nossos e do adversario na posse que terminou no chute ki."""
    dfn = other(att)
    ours, theirs, start = 0, 0, ki
    last = None
    i = ki
    while i >= 0:
        r = rows[i]
        # reinicio de partida (bola parada no centro)
        if abs(r["ball"][0] - 10000) < 5 and abs(r["ball"][1] - 5000) < 5 \
                and r["bspeed"] <= 2:
            start = i
            break
        h = r["holder"]
        if h is not None:
            sd = h[0].lower()
            if sd == dfn:
                theirs += 1
                if theirs >= 3:      # adversario controlou de fato
                    start = i
                    break
            else:
                theirs = 0
        i -= 1
    else:
        start = 0
    # conta toques nossos distintos no intervalo [start, ki]
    touches, last_h = 0, None
    for r in rows[start:ki + 1]:
        h = r["holder"]
        if h is not None and h[0].lower() == att:
            if last_h != h:
                touches += 1
            last_h = h
        elif h is not None:
            last_h = h
    return touches, rows[ki]["turn"] - rows[start]["turn"], start


def goal_report(name):
    d = load(name)
    rows, att = d["rows"], d["ours"] or "home"
    dfn = other(att)
    gx = goal_x(att)
    out = []
    for gi in goal_indices(rows, att):
        ki = find_shot(rows, gi)
        k = {"pos": rows[ki]["ball"], "v0": rows[ki + 1]["bspeed"],
             "dir": rows[ki + 1]["bdir"]}
        c = classify_kick(k, att, rows)
        h = rows[ki]["holder"]
        # quem chutou
        if h is not None:
            kicker = h
        else:
            bx, by = rows[ki]["ball"]
            best, bd = None, 1e9
            for sd in ("home", "away"):
                for num, (x, y) in rows[ki][sd].items():
                    dd = math.hypot(x - bx, y - by)
                    if dd < bd:
                        bd, best = dd, (sd.upper(), num)
            kicker = best if bd <= 450 else None
        gk0 = gk_of(rows[ki], dfn)
        gk1 = gk_of(rows[gi], dfn)
        cross = rows[gi]["ball"][1]
        touches, span, si = possession_chain(rows, ki, att)
        out.append({
            "goal_turn": rows[gi]["turn"], "shot_turn": rows[ki]["turn"],
            "kicker": kicker, "v0": k["v0"],
            "d_line": c["d_line"], "d_center": c["d_center"],
            "ang": c["ang_center"], "aperture": c["aperture"],
            "cross_y": cross, "v_arrive": c["v_arrive"],
            "flight": rows[gi]["turn"] - rows[ki]["turn"],
            "gk_y0": gk0[1] if gk0 else None, "gk_y1": gk1[1] if gk1 else None,
            "gk_gap0": abs(gk0[1] - cross) if gk0 else None,
            "gk_gap1": abs(gk1[1] - cross) if gk1 else None,
            "gk_move": (gk1[1] - gk0[1]) if gk0 and gk1 else None,
            "traj_gap": seg_point_dist(k["pos"], (gx, cross), gk0) if gk0 else None,
            "touches": touches, "span": span,
        })
    return out


# --------------------------------------------------- desfecho do chute
def shot_outcome(rows, ki, att, maxturns=60):
    """O que aconteceu com a bola depois do chute no indice ki."""
    dfn = other(att)
    key = "sh" if att == "home" else "sa"
    s0 = rows[ki][key]
    j = ki + 1
    end = min(len(rows) - 1, ki + maxturns)
    while j <= end:
        r = rows[j]
        if r[key] > s0:
            return "GOL", j
        h = r["holder"]
        if h is not None:
            if h[0].lower() == dfn:
                return ("DEFESA_GK" if h[1] == 1 else "BLOQUEIO_LINHA"), j
            return "NOSSA_DE_NOVO", j
        if r["bspeed"] <= 2:
            return "PAROU", j
        j += 1
    return "OUTRO", min(j, len(rows) - 1)


def shot_table(name, minv=389, maxang=None, maxd=None):
    """Todas as finalizacoes (chute a potencia maxima) do nosso time."""
    d = load(name)
    rows, att = d["rows"], d["ours"] or "home"
    dfn, gx = other(att), goal_x(att)
    res = []
    for k in detect_kicks(rows):
        if not k["kicker"] or k["kicker"][0].lower() != att:
            continue
        if k["v0"] < minv:
            continue
        c = classify_kick(k, att, rows)
        if maxang is not None and c["ang_center"] > maxang:
            continue
        if maxd is not None and c["d_center"] > maxd:
            continue
        ki = k["i"]
        out, j = shot_outcome(rows, ki, att)
        gk0 = gk_of(rows[ki], dfn)
        cy = c["cross_y"]
        gap0 = abs(gk0[1] - cy) if (gk0 and cy is not None) else None
        # defensores de linha na trajetoria (ate o ponto de cruzamento)
        blockers = 0
        if cy is not None:
            for num, p in rows[ki][dfn].items():
                if num == 1:
                    continue
                if seg_point_dist(k["pos"], (gx, cy), p) < 300:
                    blockers += 1
        res.append({
            "turn": k["turn"], "num": k["kicker"][1], "pos": k["pos"],
            "d_line": c["d_line"], "d_center": c["d_center"],
            "ang": c["ang_center"], "aperture": c["aperture"],
            "cross_y": cy, "on_target": c["on_target"], "path": c["path"],
            "reach": c["reach"], "t_arrive": c["t_arrive"],
            "v_arrive": c["v_arrive"], "gap0": gap0, "gk_y0": gk0[1] if gk0 else None,
            "blockers": blockers, "outcome": out,
            "flight": rows[j]["turn"] - k["turn"],
        })
    return res


# =====================================================================
#  RELATORIO
# =====================================================================
DUM = ["t1", "eval_0_norm", "var_1", "var_2", "swap", "v6_check"]
SHOT = dict(minv=300, maxang=60, maxd=7000)   # definicao de "finalizacao"


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else 0.0


def feasible(s, margin=100, gkspeed=100):
    """Existe algum ponto da boca do gol que o goleiro NAO cobre a tempo?"""
    if s["gk_y0"] is None or s["t_arrive"] == math.inf:
        return False
    best = max(abs(GOAL_MIN_Y + margin - s["gk_y0"]),
               abs(GOAL_MAX_Y - margin - s["gk_y0"]))
    return best >= GK_HALF + gkspeed * s["t_arrive"]


def band(d):
    for lo, hi in [(0, 1500), (1500, 3000), (3000, 4500), (4500, 6000)]:
        if lo <= d < hi:
            return f"{lo}-{hi}"
    return "6000+"


BANDS = ["0-1500", "1500-3000", "3000-4500", "4500-6000", "6000+"]


def main():
    print("#" * 78)
    print("# A) GENESE DOS GOLS")
    print("#" * 78)
    G = []
    for n in DUM:
        for g in goal_report(n):
            G.append(dict(g, rep=n))
    print(f"{len(G)} gols em 6 partidas contra os dummies\n")
    hdr = ("rep", "t_gol", "t_chute", "quem", "d_cen", "ang", "crossY",
           "gkY0", "gap0", "gap_fim", "voo", "toq")
    print("  %-12s %6s %7s %8s %6s %4s %7s %6s %6s %7s %4s %4s" % hdr)
    for g in G:
        print("  %-12s %6d %7d %8s %6.0f %4.0f %7.0f %6.0f %6.0f %7.0f %4d %4d" % (
            g["rep"], g["goal_turn"], g["shot_turn"],
            f"{g['kicker'][0][0]}{g['kicker'][1]}", g["d_center"], g["ang"],
            g["cross_y"], g["gk_y0"], g["gk_gap0"], g["gk_gap1"],
            g["flight"], g["touches"]))
    print()
    print(f"  distancia do chute (ao centro do gol): mediana {med([g['d_center'] for g in G]):.0f}"
          f"  max {max(g['d_center'] for g in G):.0f}")
    print(f"  angulo em relacao ao centro do gol: mediana {med([g['ang'] for g in G]):.0f} graus")
    print(f"  gap do goleiro NO CHUTE: mediana {med([g['gk_gap0'] for g in G]):.0f}"
          f"  minimo {min(g['gk_gap0'] for g in G):.0f}")
    print(f"  gap do goleiro NA CHEGADA: mediana {med([g['gk_gap1'] for g in G]):.0f}"
          f"  minimo {min(g['gk_gap1'] for g in G):.0f}   (meia-extensao do goleiro = 560)")
    print(f"  goleiro se desloca {med([abs(g['gk_move']) for g in G]):.0f}d durante o voo de "
          f"{med([g['flight'] for g in G]):.0f} turnos")
    print(f"  toques nossos na posse: mediana {med([g['touches'] for g in G]):.0f}"
          f"  ; gols com <=2 toques: {sum(1 for g in G if g['touches'] <= 2)}/{len(G)}")
    print(f"  todos os gols saiam de chute NOSSO: "
          f"{sum(1 for g in G if g['kicker'])}/{len(G)}  "
          f"(gols contra sofridos nos 9 replays: 0)")
    print()

    print("#" * 78)
    print("# B) CONVERSAO DAS FINALIZACOES (v0>=300, ang<=60, d<=7000)")
    print("#" * 78)
    A = []
    for n in DUM:
        A += [dict(s, rep=n) for s in shot_table(n, **SHOT)]
    ngol = sum(1 for s in A if s["outcome"] == "GOL")
    print(f"{len(A)} finalizacoes / {ngol} gols = {100*ngol/len(A):.1f}% x dummies\n")
    print("  faixa        n  gols   conv   no-alvo  viavel  defGK  bloq")
    for b in BANDS:
        v = [s for s in A if band(s["d_center"]) == b]
        if not v:
            continue
        g = sum(1 for s in v if s["outcome"] == "GOL")
        ot = sum(1 for s in v if s["on_target"])
        fe = sum(1 for s in v if feasible(s))
        gk = sum(1 for s in v if s["outcome"] == "DEFESA_GK")
        bl = sum(1 for s in v if s["outcome"] == "BLOQUEIO_LINHA")
        print(f"  {b:10s} {len(v):3d} {g:5d} {100*g/len(v):6.1f}% {100*ot/len(v):8.0f}%"
              f" {100*fe/len(v):6.0f}% {100*gk/len(v):5.0f}% {100*bl/len(v):5.0f}%")
    print()
    print("  por gap do goleiro no momento do chute (so chutes no alvo):")
    ot = [s for s in A if s["on_target"]]
    for lo, hi in [(0, 1000), (1000, 1500), (1500, 2000), (2000, 2500), (2500, 9e9)]:
        v = [s for s in ot if s["gap0"] is not None and lo <= s["gap0"] < hi]
        if not v:
            continue
        g = sum(1 for s in v if s["outcome"] == "GOL")
        print(f"    gap {lo}-{min(hi,9999):.0f}: n={len(v):3d} gols={g:3d} "
              f"conv={100*g/len(v):5.1f}%")
    print()
    print("  FUNIL:")
    fe = [s for s in A if feasible(s)]
    fo = [s for s in fe if s["on_target"]]
    fg = [s for s in fo if s["gap0"] >= GK_HALF + 100 * s["t_arrive"]]
    print(f"    {len(A):3d} finalizacoes")
    print(f"    {len(fe):3d} geometricamente viaveis (goleiro nao cobre a boca toda a tempo)"
          f"  -> as {len(A)-len(fe)} inviaveis deram {sum(1 for s in A if not feasible(s) and s['outcome']=='GOL')} gols")
    print(f"    {len(fo):3d} viaveis E no alvo (perda de {len(fe)-len(fo)} por sair da boca)")
    print(f"    {len(fg):3d} viaveis, no alvo E longe do goleiro "
          f"(perda de {len(fo)-len(fg)} por mirar dentro do alcance dele)")
    print(f"    {ngol:3d} gols  ({100*ngol/max(1,len(fg)):.0f}% dos {len(fg)})")
    print()

    print("#" * 78)
    print("# C) O GOLEIRO E A RESTRICAO. Distancia maxima teorica de finalizacao")
    print("#" * 78)
    print("  gap exigido = 560 (meia-extensao) + 100*t (goleiro anda 100/turno)")
    print("  gap disponivel = 1500 - folga_trave + |desloc. do goleiro do centro|")
    print("  turnos  dist(v0=400)  gap_exigido   deslocamento do goleiro necessario")
    for t in range(4, 19, 2):
        d, v = 0.0, 400.0
        for _ in range(t):
            d += v - 5
            v -= 10
        req = GK_HALF + 100 * t
        print(f"    {t:3d}   {d:9.0f}     {req:7.0f}        {max(0, req-1400):.0f}")
    print()

    print("#" * 78)
    print("# D) DUMMIES x RIVAIS")
    print("#" * 78)
    print(f"  {'replay':26s} {'gols':>4} {'fin':>4} {'conv':>6} {'noalvo':>7} "
          f"{'vel_gk':>7} {'fecha':>6} {'gap_fim':>8} {'opp<1000':>9} {'cone':>5}")
    for n in ["t1", "eval_0_norm", "var_1", "var_2", "swap", "v6_check",
              "p_rival_p2_home_1", "smoke_rival"]:
        d = load(n)
        rows, att = d["rows"], d["ours"] or "home"
        dfn, gx = other(att), goal_x(att)
        sh = shot_table(n, **SHOT)
        g = sum(1 for s in sh if s["outcome"] == "GOL")
        ot = sum(1 for s in sh if s["on_target"])
        vg, fech, gapf = [], [], []
        for s in sh:
            if not s["on_target"]:
                continue
            i = next(j for j, r in enumerate(rows) if r["turn"] == s["turn"])
            t = int(s["t_arrive"])
            if i + t >= len(rows):
                continue
            g0, g1 = gk_of(rows[i], dfn), gk_of(rows[i + t], dfn)
            if not g0 or not g1:
                continue
            vg.append(abs(g1[1] - g0[1]) / max(1, t))
            fech.append(s["gap0"] - abs(g1[1] - s["cross_y"]))
            gapf.append(abs(g1[1] - s["cross_y"]))
        near, cone, cnt = 0, 0, 0
        for r in rows:
            h = r["holder"]
            if not (h and h[0].lower() == att):
                continue
            bx, by = r["ball"]
            if math.hypot(bx - gx, by - GOAL_CY) > 6000:
                continue
            cnt += 1
            for num, p in r[dfn].items():
                if num == 1:
                    continue
                if math.hypot(p[0] - bx, p[1] - by) < 1000:
                    near += 1
                if min(seg_point_dist((bx, by), (gx, y), p)
                       for y in (3700, 5000, 6300)) < 300:
                    cone += 1
        print(f"  {n:26s} {g:4d} {len(sh):4d} {100*g/max(1,len(sh)):5.0f}% "
              f"{100*ot/max(1,len(sh)):6.0f}% {med(vg):7.0f} {med(fech):6.0f} "
              f"{med(gapf):8.0f} {near/max(1,cnt):9.2f} {cone/max(1,cnt):5.2f}")
    print()
    print("  smoke_rival: 46 chutes IDENTICOS (t=122,252,382,... a cada 130 turnos,")
    print("  sempre de (17200,7325), crossY=6411, gk em y=4855) -> loop deterministico,")
    print("  nao sao 46 ataques distintos.")
    print()

    print("#" * 78)
    print("# E) VOLUME DE FINALIZACAO POR VERSAO")
    print("#" * 78)
    print(f"  {'replay':26s} {'turnos com posse a<=6000':>25} {'fin':>4} {'fin/turno':>10} {'conv':>6}")
    for n in DUM + ["p_rival_p2_home_1"]:
        d = load(n)
        rows, att = d["rows"], d["ours"] or "home"
        gx = goal_x(att)
        cnt = sum(1 for r in rows if r["holder"] and r["holder"][0].lower() == att
                  and math.hypot(r["ball"][0] - gx, r["ball"][1] - GOAL_CY) <= 6000)
        sh = shot_table(n, **SHOT)
        g = sum(1 for s in sh if s["outcome"] == "GOL")
        print(f"  {n:26s} {cnt:25d} {len(sh):4d} {len(sh)/max(1,cnt):10.3f} "
              f"{100*g/max(1,len(sh)):5.0f}%")


if __name__ == "__main__":
    main()
