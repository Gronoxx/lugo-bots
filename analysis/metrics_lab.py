"""
FRENTE 3 - laboratorio de metricas.

Le as series compactas (extract_series.py) e calcula, para cada replay/lado:
  - metricas candidatas (posse, territorio, chutes, xG, avanco por posse, ...)
  - erro-padrao de cada metrica por moving-block bootstrap DENTRO da partida
Depois compara sinal (bots diferentes) contra ruido (mesmo bot).

Nao modifica o bot; so le os replays ja gravados.
"""
import os
import sys
import numpy as np

CACHE = "<cache local>/cache"

FIELD_X, FIELD_Y = 20000.0, 10000.0
GOAL_LO, GOAL_HI = 3500.0, 6500.0
GOAL_C = 5000.0
KICK_MIN_SPEED = 120.0   # acima da velocidade de conducao (100)


def load(name):
    return dict(np.load(os.path.join(CACHE, name + ".npz")))


def goal_x(side):
    """x do gol que 'side' ATACA."""
    return FIELD_X if side == "home" else 0.0


def reach(v):
    """Distancia total que a bola percorre saindo com velocidade v.
    v cai 10/turno, avanco por turno = v-5."""
    n = max(0, int(np.floor((v - 2) / 10.0)) + 1)
    return n * (v - 5) - 10 * n * (n - 1) / 2.0


def arrival_speed(v, d):
    """Velocidade ao percorrer distancia d (0 se nao chega)."""
    s2 = v * v - 20.0 * d
    return np.sqrt(s2) if s2 > 0 else 0.0


# ---------------------------------------------------------------- eventos

def kicks(d, side):
    """Detecta chutes/passes: quem tinha a bola solta ela com velocidade alta.

    Retorna lista de dicts com posicao, direcao, velocidade, alvo no gol, etc.
    """
    s = 0 if side == "home" else 1
    hs, sp = d["hold_side"], d["bspeed"]
    bx, by, dx, dy = d["bx"], d["by"], d["bdx"], d["bdy"]
    idx = np.where((hs[:-1] == s) & (hs[1:] != s) & (sp[1:] >= KICK_MIN_SPEED))[0]
    gx = goal_x(side)
    ev = []
    for i in idx:
        j = i + 1
        v = float(sp[j]); ux, uy = float(dx[j]), float(dy[j])
        nrm = np.hypot(ux, uy)
        if nrm == 0:
            continue
        ux, uy = ux / nrm, uy / nrm
        x0, y0 = float(bx[j]), float(by[j])
        # onde a reta do chute cruza a linha do gol atacado
        if abs(ux) < 1e-9 or (gx - x0) * ux <= 0:
            ycross, dist_line = None, None
        else:
            tpar = (gx - x0) / ux
            ycross = y0 + uy * tpar
            dist_line = tpar
        dist_goal = np.hypot(gx - x0, GOAL_C - y0)
        ev.append(dict(
            t=int(d["turn"][j]), i=int(j), x=x0, y=y0, ux=ux, uy=uy, v=v,
            ycross=ycross, dist_line=dist_line, dist_goal=dist_goal,
            kicker=int(d["hold_num"][i]),
        ))
    return ev


def goal_turns(d, side):
    key = "sc_home" if side == "home" else "sc_away"
    sc = d[key]
    return [int(d["turn"][k + 1]) for k in np.where(np.diff(sc) > 0)[0]]


def gk_block_dist(d, ev, side):
    """Menor distancia do goleiro adversario a trajetoria do chute, no
    instante do chute. Goleiro = jogador de numero 1."""
    ox, oy = ("ax", "ay") if side == "home" else ("hx", "hy")
    onum = "anum" if side == "home" else "hnum"
    j = ev["i"]
    nums = d[onum][j]
    k = np.where(nums == 1)[0]
    if len(k) == 0:
        return np.nan
    k = k[0]
    px, py = float(d[ox][j, k]), float(d[oy][j, k])
    # projecao do goleiro na semi-reta do chute
    rx, ry = px - ev["x"], py - ev["y"]
    tpar = rx * ev["ux"] + ry * ev["uy"]
    tpar = max(0.0, min(tpar, ev["dist_line"] if ev["dist_line"] else tpar))
    cx, cy = ev["x"] + ev["ux"] * tpar, ev["y"] + ev["uy"] * tpar
    return float(np.hypot(px - cx, py - cy))


def mark_shots(d, side, on_target_margin=200.0):
    """Marca cada chute como 'shot' (mira o gol e tem alcance) e associa gols."""
    ev = kicks(d, side)
    gts = goal_turns(d, side)
    for e in ev:
        e["on_goal"] = False
        e["goal"] = 0
        if e["ycross"] is None:
            continue
        inside = (GOAL_LO - on_target_margin) <= e["ycross"] <= (GOAL_HI + on_target_margin)
        if inside and reach(e["v"]) >= e["dist_line"]:
            e["on_goal"] = True
            e["v_arr"] = arrival_speed(e["v"], e["dist_line"])
            e["gk"] = gk_block_dist(d, e, side)
    # atribui cada gol ao ultimo chute anterior a ele
    for gt in gts:
        cand = [e for e in ev if 0 < gt - e["t"] <= 80]
        if cand:
            cand[-1]["goal"] = 1
    return ev, gts


# ---------------------------------------------------------------- posses

def possessions(d, side):
    """Segmenta a partida em posses do lado 'side'.
    Uma posse comeca quando o lado pega a bola e termina quando o adversario
    pega (bola solta no meio nao encerra)."""
    s = 0 if side == "home" else 1
    hs = d["hold_side"]
    segs = []
    start = None
    for i, h in enumerate(hs):
        if h == s and start is None:
            start = i
        elif h == (1 - s) and start is not None:
            segs.append((start, i))
            start = None
    if start is not None:
        segs.append((start, len(hs) - 1))
    return segs


# ---------------------------------------------------------------- metricas

def all_metrics(d, side, xg_model=None):
    s = 0 if side == "home" else 1
    hs = d["hold_side"]
    bx, by = d["bx"].astype(float), d["by"].astype(float)
    gx = goal_x(side)
    n = len(hs)
    # progresso da bola no sentido do ataque (0 = proprio gol, 20000 = gol adv)
    prog = bx if side == "home" else FIELD_X - bx
    dist_goal = np.hypot(gx - bx, np.clip(by, GOAL_LO, GOAL_HI) - by)
    dist_goal = np.hypot(gx - bx, GOAL_C - by)

    ev, gts = mark_shots(d, side)
    shots = [e for e in ev if e["on_goal"]]
    segs = possessions(d, side)

    m = {}
    held = (hs >= 0).sum()
    m["gols"] = float(len(gts))
    m["posse_pct"] = 100.0 * (hs == s).sum() / max(1, held)
    m["territorio_pct"] = 100.0 * (prog > 2 * FIELD_X / 3).mean()
    m["bola_prog_medio"] = float(prog.mean())
    m["dist_media_gol"] = float(dist_goal.mean())
    m["turnos_dist<6000"] = float((dist_goal < 6000).mean() * 100)
    m["turnos_dist<4000"] = float((dist_goal < 4000).mean() * 100)
    m["chutes_ao_gol"] = float(len(shots))
    m["passes_chutes_total"] = float(len(ev))
    m["n_posses"] = float(len(segs))
    if segs:
        adv = [prog[b] - prog[a] for a, b in segs]
        m["avanco_por_posse"] = float(np.mean(adv))
        m["avanco_total"] = float(np.sum(adv))
        m["dur_posse_media"] = float(np.mean([b - a for a, b in segs]))
        # posses que terminam em chute ao gol
        sh_t = set(e["i"] for e in shots)
        ends = sum(1 for a, b in segs if any(a <= i <= b + 3 for i in sh_t))
        m["posses_c_chute_pct"] = 100.0 * ends / len(segs)
    if shots:
        m["dist_media_chute"] = float(np.mean([e["dist_line"] for e in shots]))
        m["vel_chegada_media"] = float(np.mean([e.get("v_arr", 0) for e in shots]))
        gks = [e.get("gk", np.nan) for e in shots]
        m["gk_livre_medio"] = float(np.nanmean(gks))
    if xg_model is not None and shots:
        xs = xg_features(shots)
        p = xg_predict(xg_model, xs)
        m["xG"] = float(p.sum())
        m["xG_por_chute"] = float(p.mean())
    return m, ev, shots, segs


def xg_features(shots):
    X = []
    for e in shots:
        d = e["dist_line"]
        va = e.get("v_arr", 0.0)
        gk = e.get("gk", 600.0)
        if not np.isfinite(gk):
            gk = 600.0
        lat = abs(e["ycross"] - GOAL_C)
        X.append([d / 1000.0, va / 100.0, min(gk, 3000) / 1000.0, lat / 1000.0])
    return np.array(X)


def fit_logistic(X, y, iters=4000, lr=0.05, l2=1e-3):
    X = np.hstack([np.ones((len(X), 1)), X])
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        g = X.T @ (y - p) / len(y) - l2 * w
        w += lr * g * 10
    return w


def xg_predict(w, X):
    X = np.hstack([np.ones((len(X), 1)), X])
    return 1 / (1 + np.exp(-X @ w))
