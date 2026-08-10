"""FRENTE 3 - diagnostico: quantos chutes existem de verdade? v6 e outlier?"""
import numpy as np
from f3_metrics import Match, FX, GOAL_C, travel
from f3_xg import is_attempt

CASES = [("t1", 0, "v1"), ("eval_0_norm", 0, "v2"), ("var_1", 0, "v3"),
         ("var_2", 0, "v3"), ("swap", 1, "v3aw"), ("v6_check", 0, "v6"),
         ("dummies_vs_dummies", 0, "dum")]

print(f"{'part':10s}{'ver':5s}{'toques':>7s}{'d<6k':>7s}{'d<6k&fr':>9s}"
      f"{'tent':>6s}{'alvo':>6s}{'gols':>6s}{'conv_alvo':>10s}{'conv_tent':>10s}")
for name, side, ver in CASES:
    m = Match(name, side)
    ks = [k for k in m.kicks() if k["mine"]]
    d6 = [k for k in ks if k["dist"] <= 6000]
    d6f = [k for k in d6 if k["dx"] > 0.05]
    att = [k for k in ks if is_attempt(k)]
    ot = [k for k in att if k["on_target"]]
    g = [k for k in ks if k["goal"]]
    print(f"{name[:9]:10s}{ver:5s}{len(ks):7d}{len(d6):7d}{len(d6f):9d}"
          f"{len(att):6d}{len(ot):6d}{len(g):6d}"
          f"{len(g)/max(1,len(ot)):10.2f}{len(g)/max(1,len(att)):10.2f}")

print("\n--- v6_check: todos os chutes 'no alvo' e seus desfechos ---")
m = Match("v6_check", 0)
for k in m.kicks():
    if k["mine"] and is_attempt(k):
        print(f"  t={k['turn']:5d} pos=({k['x']:6.0f},{k['y']:5.0f}) d={k['dist']:6.0f} "
              f"v={k['v']:5.0f} y_cross={k['y_cross']:8.1f} alvo={int(k['on_target'])} "
              f"gk_gap={k['gk_gap']:7.1f} t_cheg={k['t_arrive']:5.1f} GOL={int(k['goal'])}")

print("\n--- var_1: chutes no alvo que NAO viraram gol (o que salvou?) ---")
m = Match("var_1", 0)
nn = 0
for k in m.kicks():
    if k["mine"] and is_attempt(k) and k["on_target"] and not k["goal"]:
        nn += 1
        if nn <= 12:
            print(f"  t={k['turn']:5d} d={k['dist']:6.0f} v={k['v']:5.0f} "
                  f"y_cross={k['y_cross']:8.1f} gk_gap={k['gk_gap']:7.1f} "
                  f"t_cheg={k['t_arrive']:5.1f}")
print(f"  total: {nn}")
