"""FRENTE 3 - o goleiro: quanto ele realmente se desloca enquanto a bola viaja?"""
import numpy as np
from f3_metrics import Match, FX, GOAL_C
from f3_xg import is_attempt

CASES = [("t1", 0), ("eval_0_norm", 0), ("var_1", 0), ("var_2", 0),
         ("swap", 1), ("v6_check", 0)]

rows = []
for name, side in CASES:
    m = Match(name, side)
    num = m.op_num
    for k in m.kicks():
        if not (k["mine"] and is_attempt(k) and k["on_target"]):
            continue
        j = k["i"] + 1
        sel = np.where(num[j] == 1)[0]
        if not len(sel):
            continue
        gi = sel[0]
        t = int(k["t_arrive"])
        if not np.isfinite(k["t_arrive"]) or t < 1 or j + t >= m.n:
            continue
        y0 = m.op_y[j, gi]
        y1 = m.op_y[j + t, gi]
        rows.append(dict(name=name, t=t, y0=y0, y1=y1, yc=k["y_cross"],
                         mov=abs(y1 - y0), gap0=abs(y0 - k["y_cross"]),
                         gap1=abs(y1 - k["y_cross"]), goal=k["goal"],
                         d=k["dist"], v=k["v"]))

mov = np.array([r["mov"] for r in rows])
t = np.array([r["t"] for r in rows], float)
gap0 = np.array([r["gap0"] for r in rows])
gap1 = np.array([r["gap1"] for r in rows])
g = np.array([r["goal"] for r in rows])
print(f"n chutes no alvo: {len(rows)}  gols: {int(g.sum())}")
print(f"velocidade do goleiro (mov/turno): mediana={np.median(mov/t):.1f} "
      f"p90={np.percentile(mov/t,90):.1f} max={np.max(mov/t):.1f}")
print(f"folga NO MOMENTO do chute:  gol={gap0[g].mean():6.0f}  defendido={gap0[~g].mean():6.0f}")
print(f"folga NA CHEGADA da bola:   gol={gap1[g].mean():6.0f}  defendido={gap1[~g].mean():6.0f}")
print()
print("taxa de gol por faixa de folga-na-chegada (gap1):")
for lo, hi in [(0, 400), (400, 600), (600, 900), (900, 1500), (1500, 9999)]:
    s = (gap1 >= lo) & (gap1 < hi)
    if s.sum():
        print(f"  gap1 {lo:5d}-{hi:5d}: n={s.sum():4d} gols={int(g[s].sum()):3d} taxa={g[s].mean():.3f}")
print()
print("taxa de gol por faixa de folga-no-chute (gap0):")
for lo, hi in [(0, 400), (400, 800), (800, 1200), (1200, 1800), (1800, 9999)]:
    s = (gap0 >= lo) & (gap0 < hi)
    if s.sum():
        print(f"  gap0 {lo:5d}-{hi:5d}: n={s.sum():4d} gols={int(g[s].sum()):3d} taxa={g[s].mean():.3f}")
print()
print("margem fisica m = gap0 - (200*t + 560)  [>0 = goleiro nao alcanca]")
marg = gap0 - (200 * t + 560)
for lo, hi in [(-9999, -1500), (-1500, -800), (-800, 0), (0, 9999)]:
    s = (marg >= lo) & (marg < hi)
    if s.sum():
        print(f"  m {lo:6d}..{hi:5d}: n={s.sum():4d} gols={int(g[s].sum()):3d} taxa={g[s].mean():.3f}")
print()
print("taxa de gol por tempo de voo (turnos):")
for lo, hi in [(0, 6), (6, 10), (10, 15), (15, 25), (25, 99)]:
    s = (t >= lo) & (t < hi)
    if s.sum():
        print(f"  t {lo:3d}-{hi:3d}: n={s.sum():4d} gols={int(g[s].sum()):3d} taxa={g[s].mean():.3f} "
              f"mov_medio_gk={mov[s].mean():.0f}")
print()
print("por partida: chutes no alvo, gols, folga media na chegada")
for name, side in CASES:
    s = np.array([r["name"] == name for r in rows])
    if s.sum():
        print(f"  {name:14s} n={s.sum():3d} gols={int(g[s].sum()):3d} "
              f"tvoo={t[s].mean():5.1f} gap0={gap0[s].mean():6.0f} gap1={gap1[s].mean():6.0f}")
