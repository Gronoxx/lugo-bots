#!/usr/bin/env python3
"""Extrator de CENAS a partir dos vídeos da plataforma (1440x810, ~16fps).

Partidas de plataforma não têm replay JSON — só o MP4 top-down. Este módulo
reconstrói o estado (posições dos 22 + bola, a ~14d/px) numa janela antes de
um gol sofrido, para re-simular o lance no fastsim (sim/scene_runner.py).

Pipeline por frame (rawvideo RGB via ffmpeg pipe, sem estourar disco):
  1. calibração: bordas do retângulo branco do campo -> transform linear
     px->campo (validada pela bola do kickoff em (10000,5000));
  2. jogadores: componentes quase-brancos compactos (área 150-700) dentro do
     campo; time pela cor do anel (média dos pixels saturados na vizinhança):
     azul-marinho = killua (HOME), magenta/rosa = adversário;
  3. bola: componente escuro pequeno sobre o campo (fora dos círculos brancos);
  4. tracking por proximidade frame a frame (movimento <= ~10px/frame), com
     herança de posição em oclusão (bolos);
  5. reamostragem 16fps -> 20Hz (turnos) e velocidades por diferença.

Identidades HOME: GK = track de x mínimo (preso à linha); os 10 de linha
recebem números por PAPEL (4 mais recuados = 2-5, 3 meio = 6-8, 3 frente =
9-11, cada grupo ordenado por y — consistente com a BASE_FORMATION v3).
Aproximação assumida: para a cena importa o papel, não a camisa exata.
"""
import json
import math
import os
import subprocess
import sys

import numpy as np

W, H = 1440, 810
FPS = 16.0
TURNS_PER_SEC = 20.0
FIELD_X, FIELD_Y = 20000.0, 10000.0
TOP_UI = 96          # faixa do placar: ignorar y < isto


def read_frames(video, t0, t1, w=W, h=H):
    """Gera arrays HxWx3 uint8 dos frames em [t0, t1) via ffmpeg pipe."""
    cmd = ["ffmpeg", "-v", "error", "-ss", str(t0), "-to", str(t1),
           "-i", video, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = w * h * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        yield np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3)
    p.stdout.close()
    p.wait()


def calibrate(frame):
    """Bordas do retângulo branco do campo -> (x0, x1, y0, y1) em px."""
    white = frame.min(axis=2) > 190
    mid_row = white[H // 2 + 60, :]        # evita círculo central: +60px
    xs = np.where(mid_row)[0]
    x0, x1 = int(xs.min()), int(xs.max())
    mid_col = white[:, W // 4]             # coluna a 1/4 (sem círculo)
    ys = np.where(mid_col[TOP_UI:])[0] + TOP_UI
    y0, y1 = int(ys.min()), int(ys.max())
    return x0, x1, y0, y1


def px_to_field(cal, px, py):
    x0, x1, y0, y1 = cal
    fx = (px - x0) / max(1, (x1 - x0)) * FIELD_X
    fy = (py - y0) / max(1, (y1 - y0)) * FIELD_Y
    return float(np.clip(fx, 0, FIELD_X)), float(np.clip(fy, 0, FIELD_Y))


def _components(mask, min_area, max_area):
    """Componentes conexos 4-viz (BFS iterativo, numpy-friendly p/ máscaras
    esparsas). Retorna lista de (cy, cx, area)."""
    visited = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.where(mask)
    coords = set(zip(ys.tolist(), xs.tolist()))
    for y, x in zip(ys.tolist(), xs.tolist()):
        if visited[y, x]:
            continue
        stack = [(y, x)]
        visited[y, x] = True
        acc_y = acc_x = n = 0
        while stack:
            cy, cx = stack.pop()
            acc_y += cy
            acc_x += cx
            n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if (ny, nx) in coords and not visited[ny, nx]:
                    visited[ny, nx] = True
                    stack.append((ny, nx))
        if min_area <= n <= max_area:
            out.append((acc_y / n, acc_x / n, n))
    return out


def detect(frame, cal):
    """(homes, aways, ball) em px do frame. Times pela cor do anel."""
    x0, x1, y0, y1 = cal
    r = frame[:, :, 0].astype(np.int16)
    g = frame[:, :, 1].astype(np.int16)
    b = frame[:, :, 2].astype(np.int16)
    infield = np.zeros((H, W), dtype=bool)
    infield[max(TOP_UI, y0 - 26):y1 + 26, max(0, x0 - 26):x1 + 26] = True
    # margem generosa: o GK fica NA linha (metade do círculo pode sair do
    # retângulo) — sem ela ele some e a numeração por papel desloca tudo

    # jogadores: miolo quase-branco compacto (as linhas do campo são finas ->
    # área pequena por componente; o filtro de área remove)
    white = (np.minimum(np.minimum(r, g), b) > 185) & infield
    players = _components(white, 90, 900)   # 90: GK parcialmente cortado

    dets = []                      # (x, y, cls) com cls in {"H","A","?"}
    for cy, cx, area in players:
        iy, ix = int(round(cy)), int(round(cx))
        y_lo, y_hi = max(0, iy - 14), min(H, iy + 15)
        x_lo, x_hi = max(0, ix - 14), min(W, ix + 15)
        rr = r[y_lo:y_hi, x_lo:x_hi]
        gg = g[y_lo:y_hi, x_lo:x_hi]
        bb = b[y_lo:y_hi, x_lo:x_hi]
        # anel: pixels saturados (nem brancos nem campo ciano nem escuros)
        sat = ((np.maximum(np.maximum(rr, gg), bb)
                - np.minimum(np.minimum(rr, gg), bb)) > 60)
        not_cyan = ~((gg > 120) & (bb > 120) & (rr < 110))
        sel = sat & not_cyan
        if sel.sum() < 8:
            continue
        mr, mg, mb = rr[sel].mean(), gg[sel].mean(), bb[sel].mean()
        # classificação CONSERVADORA (ambíguo = "?" — o tracking decide):
        # magenta = R alto e comparável a B; azul-marinho = B >> R e R baixo
        if mr > 140 and mr > 0.75 * mb and mr > mg + 50:
            cls = "A"
        elif mb > 100 and mr < 0.55 * mb and mr < 110:
            cls = "H"
        else:
            cls = "?"
        dets.append((cx, cy, cls))
    homes = [(x, y) for x, y, c in dets if c == "H"]
    aways = [(x, y) for x, y, c in dets if c == "A"]
    alldet = dets

    # bola: componente escuro pequeno fora dos círculos brancos — devolve
    # TODOS os candidatos (o caminho é resolvido por DP em extract()).
    # SÓ dentro do retângulo do campo: a margem externa (p/ o GK) é fundo
    # escuro e viraria candidato falso estático.
    infield_ball = np.zeros((H, W), dtype=bool)
    infield_ball[y0 + 2:y1 - 2, x0 + 2:x1 - 2] = True
    dark = (np.maximum(np.maximum(r, g), b) < 80) & infield_ball
    # excluir números (escuros DENTRO de círculo branco): dilatar white 3px
    wd = white.copy()
    for _ in range(3):
        wd[1:, :] |= wd[:-1, :]
        wd[:-1, :] |= wd[1:, :]
        wd[:, 1:] |= wd[:, :-1]
        wd[:, :-1] |= wd[:, 1:]
    dark &= ~wd
    balls = [(bx, by) for by, bx, _n in _components(dark, 15, 220)]
    # fração de campo visível (animação de gol cobre o campo)
    cyan = ((g > 110) & (b > 110) & (r < 120))[y0:y1, x0:x1]
    frac_cyan = float(cyan.mean()) if cyan.size else 0.0
    return homes, aways, balls, frac_cyan, alldet


def _match_tracks(tracks, dets, max_jump=28.0):
    """Casa tracks (lista de [x,y]) com detecções por proximidade gulosa;
    detecção sobrando vira nada; track sem detecção herda a posição."""
    used = set()
    new = []
    for tx, ty in tracks:
        best, bd = None, max_jump
        for k, (dx, dy) in enumerate(dets):
            if k in used:
                continue
            d = math.hypot(dx - tx, dy - ty)
            if d < bd:
                bd, best = d, k
        if best is None:
            new.append([tx, ty])
        else:
            used.add(best)
            new.append([dets[best][0], dets[best][1]])
    return new


def extract(video, t_goal, pre=7.0, post=1.0):
    """Extrai a cena: janela [t_goal-pre, t_goal+post]. Nós = HOME (esquerda).
    Retorna dict pronto p/ JSON."""
    t0, t1 = max(0.0, t_goal - pre), t_goal + post
    frames = list(read_frames(video, t0, t1))
    if len(frames) < 10:
        raise RuntimeError(f"janela vazia ({len(frames)} frames)")
    cal = calibrate(frames[0])

    # detecta tudo por frame; TRUNCA no 1º frame de animação (campo coberto)
    dets = []
    for f in frames:
        hs, as_, bls, frac, alld = detect(f, cal)
        if frac < 0.45 and dets:
            break                          # animação de gol: fim da cena
        dets.append((hs, as_, bls, alld))
    if len(dets) < 10:
        raise RuntimeError("cena curta demais após truncar animação")

    # 1º frame utilizável: 10+10 CLASSIFICADOS e >=1 candidato de bola
    # (fallback 9+9: bolos no início da janela — o track duplicado se
    # separa sozinho quando o bolo abre)
    start = None
    for need in (10, 9):
        for i, (hs, as_, bls, _al) in enumerate(dets[:12]):
            if len(hs) >= need and len(as_) >= need and bls:
                start = i
                break
        if start is not None:
            break
    if start is None:
        raise RuntimeError("não achei 10+10+bola nos frames iniciais")
    dets = dets[start:]

    h0 = list(dets[0][0])
    a0 = list(dets[0][1])
    while len(h0) < 11:
        h0.append(h0[-1])
    while len(a0) < 11:
        a0.append(a0[-1])
    # TRACKING CONJUNTO: 22 tracks com identidade de time FIXA (do 1º frame);
    # matching global guloso contra TODAS as detecções, com a classe de cor
    # como restrição (track H nunca gruda em detecção A inequívoca) — imune
    # ao vazamento por classificação flutuante nos bolos.
    tracks = ([{"team": "H", "x": x, "y": y} for x, y in h0[:11]]
              + [{"team": "A", "x": x, "y": y} for x, y in a0[:11]])

    traj_h, traj_a = [], []
    for _hs, _as, _bls, alld in dets:
        cand = list(alld)
        pairs = []
        for ti, tr in enumerate(tracks):
            for k, (dx, dy, cls) in enumerate(cand):
                if cls != "?" and cls != tr["team"]:
                    continue
                d = math.hypot(dx - tr["x"], dy - tr["y"])
                if d <= 22.0:
                    pairs.append((d, ti, k))
        pairs.sort()
        used_t, used_k = set(), set()
        for d, ti, k in pairs:
            if ti in used_t or k in used_k:
                continue
            used_t.add(ti)
            used_k.add(k)
            tracks[ti]["x"], tracks[ti]["y"] = cand[k][0], cand[k][1]
        traj_h.append([px_to_field(cal, t["x"], t["y"])
                       for t in tracks[:11]])
        traj_a.append([px_to_field(cal, t["x"], t["y"])
                       for t in tracks[11:]])

    # BOLA por programação dinâmica sobre os candidatos: minimiza a soma dos
    # saltos, com opção "gap" (bola oculta; custo fixo, posição herdada) —
    # imune a detecções falsas isoladas e a oclusões no bolo.
    GAP = 55.0                      # custo de pular um frame sem detecção
    n_fr = len(dets)
    nodes = []                      # nodes[t] = [(x,y), ...] + [None] (gap)
    for _hs, _as, bls, _al in dets:
        nodes.append(list(bls[:6]) + [None])
    INF = 1e18
    cost = [dict() for _ in range(n_fr)]
    back = [dict() for _ in range(n_fr)]
    for k, nd in enumerate(nodes[0]):
        cost[0][k] = 0.0 if nd is not None else GAP
    pos_of = [dict() for _ in range(n_fr)]     # posição efetiva do nó
    for k, nd in enumerate(nodes[0]):
        pos_of[0][k] = nd
    for t in range(1, n_fr):
        for k, nd in enumerate(nodes[t]):
            best_c, best_p = INF, None
            for pk, pc in cost[t - 1].items():
                ppos = pos_of[t - 1][pk]
                if nd is None:
                    c = pc + GAP
                elif ppos is None:
                    c = pc + 10.0          # sai do gap: barato
                else:
                    d = math.hypot(nd[0] - ppos[0], nd[1] - ppos[1])
                    if d > 70.0:           # acima do físico (400 d/turno)
                        c = pc + 400.0 + d # possível mas caríssimo
                    else:
                        c = pc + d
                if c < best_c:
                    best_c, best_p = c, pk
            cost[t][k] = best_c
            back[t][k] = best_p
            pos_of[t][k] = nd if nd is not None else pos_of[t - 1][best_p]
    k = min(cost[-1], key=lambda kk: cost[-1][kk])
    path = [None] * n_fr
    for t in range(n_fr - 1, -1, -1):
        path[t] = pos_of[t][k]
        if t > 0:
            k = back[t][k]
    # preencher gaps iniciais e converter
    first = next(p for p in path if p is not None)
    cur = first
    traj_b = []
    for p in path:
        if p is not None:
            cur = p
        traj_b.append(px_to_field(cal, cur[0], cur[1]))

    # reamostragem 16fps -> 20Hz
    n_f = len(traj_b)
    n_t = int(n_f * TURNS_PER_SEC / FPS)
    def resample(seq):     # seq: [frame][...][2]
        arr = np.asarray(seq, dtype=np.float64)
        src = np.arange(n_f) / FPS
        dst = np.arange(n_t) / TURNS_PER_SEC
        flat = arr.reshape(n_f, -1)
        out = np.stack([np.interp(dst, src, flat[:, k])
                        for k in range(flat.shape[1])], axis=1)
        return out.reshape((n_t,) + arr.shape[1:])
    R_h, R_a, R_b = resample(traj_h), resample(traj_a), resample(traj_b)

    # identidades HOME: papéis pelo T0 da cena (as trajetórias nossas do
    # vídeo só alimentam o estado inicial — no runner os 11 são o my_bot
    # VIVO; médias da janela distorceriam com tracks ocluídos)
    mean_x = R_h[0, :, 0]
    mean_y = R_h[0, :, 1]
    gk = int(np.argmin(mean_x))
    if mean_x[gk] > 600.0:
        # GK não detectado (some na linha): o slot duplicado vira GK sintético
        # em x=0 (o fastsim o prende à linha de qualquer forma; o y importa
        # pouco — o my_bot vivo o reposiciona no 1º turno)
        dists = [math.hypot(R_h[0, i, 0] - R_h[0, j, 0],
                            R_h[0, i, 1] - R_h[0, j, 1])
                 for i in range(11) for j in range(i + 1, 11)]
        pairs = [(i, j) for i in range(11) for j in range(i + 1, 11)]
        dup_i, dup_j = pairs[int(np.argmin(dists))]
        R_h[:, dup_j, 0] = 30.0
        R_h[:, dup_j, 1] = FIELD_Y / 2.0
        mean_x = R_h[:, :, 0].mean(axis=0)
        mean_y = R_h[:, :, 1].mean(axis=0)
        gk = int(dup_j)
    rest = [i for i in range(11) if i != gk]
    rest.sort(key=lambda i: mean_x[i])
    defs = sorted(rest[:4], key=lambda i: mean_y[i])
    mids = sorted(rest[4:7], key=lambda i: mean_y[i])
    fwds = sorted(rest[7:], key=lambda i: mean_y[i])
    order = [gk] + defs + mids + fwds          # -> numbers 1..11
    R_h = R_h[:, order, :]
    # identidades AWAY: GK deles = x máximo; resto tanto faz (ghost)
    agk = int(np.argmax(R_a[:, :, 0].mean(axis=0)))
    aorder = [agk] + [i for i in range(11) if i != agk]
    R_a = R_a[:, aorder, :]

    # eventos de chute do ghost: aceleração da bola com dono adversário.
    # Filtros: velocidade resultante física (<=450 d/turno), coalescer eventos
    # a <8 turnos do anterior (serrilhado da reamostragem), e a bola precisa
    # ir mais rápido DEPOIS do que antes (chute acelera; desvio de tracking
    # não necessariamente).
    kicks = []
    for t in range(1, n_t - 1):
        v_prev = R_b[t] - R_b[t - 1]
        v_next = R_b[t + 1] - R_b[t]
        sp_next = float(np.hypot(*v_next))
        dv = float(np.hypot(*(v_next - v_prev)))
        if dv < 120.0 or sp_next > 450.0 or sp_next < float(np.hypot(*v_prev)):
            continue
        if kicks and t - kicks[-1]["turn"] < 8:
            continue
        d_away = np.hypot(R_a[t, :, 0] - R_b[t][0],
                          R_a[t, :, 1] - R_b[t][1]).min()
        d_home = np.hypot(R_h[t, :, 0] - R_b[t][0],
                          R_h[t, :, 1] - R_b[t][1]).min()
        if d_away < d_home and d_away < 450.0:
            kicks.append({"turn": t, "vel": [float(v_next[0]),
                                             float(v_next[1])]})

    return {
        "meta": {"video": os.path.basename(video), "t_goal": t_goal,
                 "pre": pre, "post": post, "n_turns": n_t,
                 "cal": list(cal)},
        "home": R_h.tolist(),      # [turno][num-1][x,y]
        "away": R_a.tolist(),
        "ball": R_b.tolist(),
        "away_kicks": kicks,
    }


def main():
    video, t_goal, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    pre = float(sys.argv[4]) if len(sys.argv) > 4 else 7.0
    scene = extract(video, t_goal, pre=pre)
    with open(out, "w") as f:
        json.dump(scene, f)
    print(f"{out}: {scene['meta']['n_turns']} turnos, "
          f"{len(scene['away_kicks'])} chutes do ghost")


if __name__ == "__main__":
    main()
