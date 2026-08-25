#!/usr/bin/env python3
"""Testa empiricamente a 'parede no gol': 11 defensores parados/reativos vs
chutes fortes. Física verificada: bola avança v-5/turno, desacelera 10/turno,
para em v<=2; captura = bola a <= raio do defensor NAQUELE turno (goleiro 560,
linha 300); gol = cruzar x=0 dentro da boca y in [3500,6500]. Sem colisão.

Chuta-se a v0=400 (o mais rápido = pior caso p/ a parede). Defensor pode ser
estático (a parede literal) ou reativo (anda 100/turno rumo à bola).
"""
import math

MOUTH = (3500.0, 6500.0)
CAP_LINE, CAP_GK = 300.0, 560.0


def sim(origin, target, defs, react=False, v0=400.0):
    """defs: lista de [x, y, raio]. Retorna 'GOAL' | 'save' | 'out'."""
    ox, oy = origin
    dx, dy = target[0] - ox, target[1] - oy
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    x, y, v = ox, oy, v0
    D = [list(p) for p in defs]
    for _ in range(200):
        for p in D:                                  # captura neste turno
            if math.hypot(x - p[0], y - p[1]) <= p[2]:
                return "save"
        if v <= 2:
            return "out"
        adv = v - 5.0
        nx, ny = x + ux * adv, y + uy * adv
        if x > 0 and nx <= 0:                         # cruzou a linha do gol
            fr = x / (x - nx)
            yc = y + (ny - y) * fr
            if MOUTH[0] <= yc <= MOUTH[1]:
                return "GOAL"
            nx, ux = -nx, -ux                          # bate na linha de fundo
        x, y, v = nx, ny, v - 10.0
        if y < 0:
            y, uy = -y, -uy
        elif y > 10000:
            y, uy = 20000 - y, -uy
        if react:
            for p in D:
                a = math.atan2(y - p[1], x - p[0])
                p[0] += 100 * math.cos(a)
                p[1] += 100 * math.sin(a)
    return "out"


def gk(y=5000.0):
    return [0.0, y, CAP_GK]


def wall_on_line():
    d = [gk()]
    for k in range(10):
        d.append([0.0, 3500 + k * (3000 / 9), CAP_LINE])   # 10 na linha, ~333 de vão
    return d


def wall_block():
    d = [gk()]
    for k in range(5):                                     # fileira 1 em x=250
        d.append([250.0, 3600 + k * 700, CAP_LINE])
    for k in range(5):                                     # fileira 2 em x=550 (deslocada)
        d.append([550.0, 3250 + k * 875, CAP_LINE])
    return d


def sweep(defs, react=False):
    goals = tot = 0
    for ox in (1500, 2500, 3500, 5000, 7000):
        for oy in (2500, 4000, 5000, 6000, 7500):
            for ty in (3600, 4250, 5000, 5750, 6400):
                r = sim((ox, oy), (0.0, ty), defs, react)
                tot += 1
                goals += (r == "GOAL")
    return goals, tot


for name, defs in (("11 na LINHA (x=0)", wall_on_line()),
                   ("bloco denso à frente", wall_block())):
    g, t = sweep(defs, react=False)
    gr, _ = sweep([list(p) for p in defs], react=True)
    print(f"{name:<24}: estático {g:>3}/{t} gols ({100*g/t:4.1f}%) | "
          f"reativo {gr:>3}/{t} ({100*gr/t:4.1f}%)")
