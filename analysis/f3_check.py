"""FRENTE 3 - sanidade: chutes detectados batem com os gols reais?"""
import numpy as np
from f3_metrics import Match

CASES = [("var_1", 0, 6), ("var_2", 0, 2), ("t1", 0, 6), ("eval_0_norm", 0, 4),
         ("swap", 1, 3), ("v6_check", 0, 5), ("dummies_vs_dummies", 0, 0),
         ("smoke_rival", 0, 46), ("p_rival_p2_home_1", 0, 16)]

for name, side, gols in CASES:
    m = Match(name, side)
    ks = m.kicks()
    mine = [k for k in ks if k["mine"]]
    gk = [k for k in mine if k["goal"]]
    ot = [k for k in mine if k["on_target"]]
    print(f"{name:28s} lado={side} placar={m.us_score[-1]}x{m.them_score[-1]} "
          f"chutes+passes(nossos)={len(mine):4d} no_alvo={len(ot):4d} "
          f"gols_detectados={len(gk):3d} (real {gols})")
