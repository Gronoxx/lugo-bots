"""
FRENTE 3 - qual metrica discrimina bots com pouco ruido.

Para cada replay/lado calcula um conjunto de metricas candidatas na forma
(numerador, denominador) POR BLOCO de turnos. Isso permite:
  - a metrica da partida inteira  = sum(num)/sum(den)
  - o erro-padrao dentro da partida por moving-block bootstrap

Depois:
  - sinal   = diferenca entre bots que sabemos serem diferentes
  - ruido   = desvio entre partidas do mesmo bot (var_1 x var_2) e bootstrap
  - razao   = sinal/ruido  ->  n de partidas necessarias
"""
import os
import sys
import math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_lab as M

FIELD_X = 20000.0
GOAL_C = 5000.0
BLOCK = 250            # turnos por bloco -> 24 blocos por partida
XT_THR = 0.05          # limiar fixo de "ameaca alta" (mesmo para todas as partidas)
RNG = np.random.default_rng(7)


# ------------------------------------------------------------------ chutes

def kick_events(d, side):
    """Chute = salto de velocidade da bola com a posse do lado 'side'.
    Mais robusto que exigir perda de posse (o chutador as vezes segue detendo)."""
    s = 0 if side == "home" else 1
    sp = d["bspeed"].astype(float)
    hs = d["hold_side"]
    idx = np.where((np.diff(sp) > 30) & (hs[:-1] == s))[0]
    gx = FIELD_X if side == "home" else 0.0
    out = []
    for i in idx:
        j = i + 1
        v = float(sp[j])
        ux, uy = float(d["bdx"][j]), float(d["bdy"][j])
        nrm = math.hypot(ux, uy)
        if nrm == 0:
            continue
        ux, uy = ux / nrm, uy / nrm
        x0, y0 = float(d["bx"][j]), float(d["by"][j])
        dist_goal = math.hypot(gx - x0, GOAL_C - y0)
        aim = math.degrees(math.atan2(uy, ux))
        tgt = math.degrees(math.atan2(GOAL_C - y0, gx - x0))
        err = abs((aim - tgt + 180) % 360 - 180)
        ycross = dist_line = None
        if abs(ux) > 1e-9 and (gx - x0) * ux > 0:
            tp = (gx - x0) / ux
            ycross, dist_line = y0 + uy * tp, tp
        out.append(dict(i=int(j), t=int(d["turn"][j]), x=x0, y=y0, ux=ux, uy=uy,
                        v=v, dist_goal=dist_goal, err=err, ycross=ycross,
                        dist_line=dist_line, kicker=int(d["hold_num"][i]),
                        goal=0))
    return out


def label_goals(d, side, ev):
    gts = M.goal_turns(d, side)
    for gt in gts:
        cand = [e for e in ev if 0 < gt - e["t"] <= 80]
        if cand:
            cand[-1]["goal"] = 1
    return gts


def gk_dist_to_line(d, ev, side):
    ox, oy = ("ax", "ay") if side == "home" else ("hx", "hy")
    onum = "anum" if side == "home" else "hnum"
    j = ev["i"]
    k = np.where(d[onum][j] == 1)[0]
    if len(k) == 0 or ev["dist_line"] is None:
        return np.nan
    k = k[0]
    px, py = float(d[ox][j, k]), float(d[oy][j, k])
    tp = (px - ev["x"]) * ev["ux"] + (py - ev["y"]) * ev["uy"]
    tp = max(0.0, min(tp, ev["dist_line"]))
    cx, cy = ev["x"] + ev["ux"] * tp, ev["y"] + ev["uy"] * tp
    return float(math.hypot(px - cx, py - cy))


def enrich(d, side, ev):
    for e in ev:
        e["on_goal"] = (e["ycross"] is not None
                        and 3500 <= e["ycross"] <= 6500
                        and M.reach(e["v"]) >= e["dist_line"])
        e["v_arr"] = (M.arrival_speed(e["v"], e["dist_line"])
                      if e["dist_line"] is not None else 0.0)
        e["gk"] = gk_dist_to_line(d, e, side)
    return ev


# ------------------------------------------------------------------ metricas

def gk_xy(d, side):
    """Posicao do goleiro ADVERSARIO (numero 1) em todos os turnos."""
    ox, oy = ("ax", "ay") if side == "home" else ("hx", "hy")
    onum = "anum" if side == "home" else "hnum"
    nums = d[onum]
    n = len(d["turn"])
    k = np.argmax(nums == 1, axis=1)
    rows = np.arange(n)
    return d[ox][rows, k].astype(float), d[oy][rows, k].astype(float)


def chance_disponivel(d, side, xg_w, ntgt=9, vkick=390.0):
    """Para CADA turno, o xG do melhor chute em linha reta disponivel a partir
    da posicao da bola (independente do bot ter chutado ou nao).
    Mede QUANTAS boas situacoes de gol o bot fabrica, com ~6000 amostras/partida."""
    gx = FIELD_X if side == "home" else 0.0
    x0, y0 = d["bx"].astype(float), d["by"].astype(float)
    gx1, gy1 = gk_xy(d, side)
    tys = np.linspace(3600.0, 6400.0, ntgt)
    best = np.zeros(len(x0))
    rmax = M.reach(vkick)
    for ty in tys:
        vx, vy = gx - x0, ty - y0
        dist = np.hypot(vx, vy)
        ok = (dist > 1) & (dist <= rmax)
        ux, uy = vx / np.maximum(dist, 1e-9), vy / np.maximum(dist, 1e-9)
        v_arr = np.sqrt(np.maximum(vkick ** 2 - 20 * dist, 0.0))
        tp = np.clip((gx1 - x0) * ux + (gy1 - y0) * uy, 0.0, dist)
        cx, cy = x0 + ux * tp, y0 + uy * tp
        gk = np.minimum(np.hypot(gx1 - cx, gy1 - cy), 3000.0)
        X = np.column_stack([dist / 1000.0, v_arr / 100.0, gk / 1000.0,
                             np.full(len(x0), abs(ty - GOAL_C) / 1000.0)])
        p = M.xg_predict(xg_w, X) * ok
        best = np.maximum(best, p)
    return best


def xt_features(d, side):
    """Features POR TURNO para o modelo de ameaca posicional (xThreat)."""
    s = 0 if side == "home" else 1
    hs = d["hold_side"]
    bx, by = d["bx"].astype(float), d["by"].astype(float)
    gx = FIELD_X if side == "home" else 0.0
    prog = bx if side == "home" else FIELD_X - bx
    dg = np.hypot(gx - bx, GOAL_C - by)
    px = d["hx"] if side == "home" else d["ax"]
    pprog = px if side == "home" else FIELD_X - px
    n_atq = (pprog > 2 * FIELD_X / 3).sum(1).astype(float)   # nossos no terco atq
    ox = d["ax"] if side == "home" else d["hx"]
    oprog = ox if side == "home" else FIELD_X - ox
    n_def = (oprog > 2 * FIELD_X / 3).sum(1).astype(float)   # deles defendendo
    return np.column_stack([
        prog / 5000.0,
        dg / 5000.0,
        np.abs(by - GOAL_C) / 5000.0,
        (hs == s).astype(float),
        (hs == (1 - s)).astype(float),
        n_atq / 5.0,
        n_def / 5.0,
    ])


def xt_labels(d, side, horizon=100):
    """1 se o lado marca nos proximos `horizon` turnos."""
    gts = M.goal_turns(d, side)
    n = len(d["turn"])
    y = np.zeros(n)
    for g in gts:
        j = int(np.searchsorted(d["turn"], g))
        y[max(0, j - horizon):j] = 1.0
    return y


def xg_feat_geom(shots):
    """Qualidade GEOMETRICA do chute, SEM o goleiro: distancia, velocidade de
    chegada e desvio lateral. Serve para separar 'criou chance' de 'o goleiro
    estava fora do lugar' (que e a parte de sorte)."""
    return np.array([[e["dist_line"] / 1000.0, e["v_arr"] / 100.0,
                      abs(e["ycross"] - GOAL_C) / 1000.0] for e in shots])


def block_stats(d, side, xg_w=None, xt_w=None, xgg_w=None):
    """Devolve dict metrica -> (num_por_bloco, den_por_bloco)."""
    s = 0 if side == "home" else 1
    hs = d["hold_side"]
    bx = d["bx"].astype(float)
    by = d["by"].astype(float)
    gx = FIELD_X if side == "home" else 0.0
    prog = bx if side == "home" else FIELD_X - bx
    dg = np.hypot(gx - bx, GOAL_C - by)
    n = len(hs)
    nb = n // BLOCK
    blk = np.minimum(np.arange(n) // BLOCK, nb - 1)

    ev = enrich(d, side, kick_events(d, side))
    gts = label_goals(d, side, ev)
    shots = [e for e in ev if e["on_goal"]]
    near = [e for e in ev if e["dist_goal"] < 7000]
    segs = M.possessions(d, side)

    def per_block_sum(vals, idxs):
        out = np.zeros(nb)
        for v, i in zip(vals, idxs):
            out[blk[min(i, n - 1)]] += v
        return out

    ones = np.ones(n)
    res = {}
    # contagens: denominador 1/nb em cada bloco -> soma = 1 -> ponto = TOTAL da partida
    inv = np.ones(nb) / nb

    def turn_ratio(name, num, den):
        res[name] = (np.bincount(blk, num, nb), np.bincount(blk, den, nb))

    turn_ratio("posse_%", (hs == s).astype(float), (hs >= 0).astype(float))
    turn_ratio("territorio_%", (prog > 2 * FIELD_X / 3).astype(float), ones)
    turn_ratio("prog_medio_bola", prog, ones)
    turn_ratio("dist_media_ao_gol", dg, ones)
    turn_ratio("t_dist<6000_%", (dg < 6000).astype(float), ones)
    turn_ratio("t_dist<4000_%", (dg < 4000).astype(float), ones)
    turn_ratio("posse_no_terco_atq_%", ((hs == s) & (prog > 2 * FIELD_X / 3)).astype(float), ones)

    gi = [np.searchsorted(d["turn"], g) for g in gts]
    res["gols"] = (per_block_sum(np.ones(len(gi)), gi), inv)
    res["chutes_ao_gol"] = (per_block_sum([1] * len(shots), [e["i"] for e in shots]),
                            inv)
    res["chutadas_perto_gol"] = (per_block_sum([1] * len(near), [e["i"] for e in near]),
                                 inv)
    res["kicks_total"] = (per_block_sum([1] * len(ev), [e["i"] for e in ev]), inv)

    if near:
        res["erro_mira_medio"] = (per_block_sum([e["err"] for e in near], [e["i"] for e in near]),
                                  per_block_sum([1] * len(near), [e["i"] for e in near]))
        res["frac_mira<10deg"] = (per_block_sum([1.0 * (e["err"] < 10) for e in near],
                                                [e["i"] for e in near]),
                                  per_block_sum([1] * len(near), [e["i"] for e in near]))
    # posses
    if segs:
        adv = [prog[b] - prog[a] for a, b in segs]
        si = [a for a, b in segs]
        res["avanco_por_posse"] = (per_block_sum(adv, si), per_block_sum([1] * len(segs), si))
        res["avanco_total"] = (per_block_sum(adv, si), inv)
        sh_i = sorted(e["i"] for e in shots)
        term = []
        for a, b in segs:
            term.append(1.0 if any(a <= i <= b + 3 for i in sh_i) else 0.0)
        res["posses_c_chute_%"] = (per_block_sum(term, si), per_block_sum([1] * len(segs), si))
        res["n_posses"] = (per_block_sum([1] * len(segs), si), inv)
    if xg_w is not None and shots:
        X = xg_feat(shots)
        p = M.xg_predict(xg_w, X)
        res["xG"] = (per_block_sum(p, [e["i"] for e in shots]), inv)
        res["xG_por_chute"] = (per_block_sum(p, [e["i"] for e in shots]),
                               per_block_sum([1] * len(shots), [e["i"] for e in shots]))
        # xG sobre TODAS as chutadas perto do gol (nao so as no alvo)
        Xa = xg_feat_all(near)
        pa = M.xg_predict(xg_w, Xa) if len(near) else np.array([])
        res["xG_amplo"] = (per_block_sum(pa, [e["i"] for e in near]), inv)
    if xgg_w is not None and shots:
        pg = M.xg_predict(xgg_w, xg_feat_geom(shots))
        res["xG_geom"] = (per_block_sum(pg, [e["i"] for e in shots]), inv)
        res["chutes_bons_geom"] = (per_block_sum([1.0 * (q > 0.35) for q in pg],
                                                 [e["i"] for e in shots]), inv)
    if xg_w is not None:
        ch = chance_disponivel(d, side, xg_w)
        mine = (hs == s).astype(float)
        turn_ratio("chance_disp_media", ch, ones)
        turn_ratio("chance_disp_c_posse", ch * mine, ones)
        turn_ratio("t_chance>0.5_%", (ch > 0.5).astype(float), ones)
        turn_ratio("t_chance>0.5_posse_%", ((ch > 0.5) & (hs == s)).astype(float), ones)
        # entradas em situacao de gol claro (transicoes 0->1), conta eventos
        cross = ((ch[1:] > 0.5) & (ch[:-1] <= 0.5) & (hs[1:] == s)).astype(float)
        res["entradas_chance_clara"] = (np.bincount(blk[1:], cross, nb), inv)
    if xt_w is not None:
        xt = M.xg_predict(xt_w, xt_features(d, side))
        turn_ratio("xThreat_medio", xt, ones)
        turn_ratio("xThreat_alto_%", (xt > XT_THR).astype(float), ones)
    res["_meta"] = dict(nb=nb, n_shots=len(shots), n_near=len(near),
                        n_goals=len(gts), n_kicks=len(ev))
    return res


def xg_feat(shots):
    X = []
    for e in shots:
        gk = e["gk"]
        gk = 3000.0 if not np.isfinite(gk) else min(gk, 3000.0)
        X.append([e["dist_line"] / 1000.0, e["v_arr"] / 100.0, gk / 1000.0,
                  abs(e["ycross"] - GOAL_C) / 1000.0])
    return np.array(X)


def xg_feat_all(near):
    """Como xg_feat mas tolerante a chutes que nem cruzam a linha do gol."""
    X = []
    for e in near:
        if e["ycross"] is None or M.reach(e["v"]) < (e["dist_line"] or 1e9):
            X.append([e["dist_goal"] / 1000.0, 0.0, 0.0, 6.0])
            continue
        gk = e["gk"]
        gk = 3000.0 if not np.isfinite(gk) else min(gk, 3000.0)
        X.append([e["dist_line"] / 1000.0, e["v_arr"] / 100.0, gk / 1000.0,
                  abs(e["ycross"] - GOAL_C) / 1000.0])
    return np.array(X)


# ------------------------------------------------------------------ bootstrap

def point(nd):
    num, den = nd
    dsum = den.sum()
    return num.sum() / dsum if dsum else np.nan


def boot_se(nd, B=2000):
    num, den = nd
    nb = len(num)
    idx = RNG.integers(0, nb, size=(B, nb))
    ns = num[idx].sum(1)
    ds = den[idx].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        vals = np.where(ds > 0, ns / np.maximum(ds, 1e-9), np.nan)
    return float(np.nanstd(vals))
