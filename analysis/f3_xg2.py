"""
FRENTE 3 - xG v2, com features fisicas do goleiro.

Descoberta (f3_gk.py, 115 chutes no alvo, 26 gols):
  folga do goleiro ate o ponto de cruzamento NO MOMENTO DO CHUTE (gap0)
    gap0 < 1200      ->  0/58 gols
    gap0 1200-1800   -> 10/34
    gap0 > 1800      -> 16/23
  o goleiro anda ~75 d/turno mediano (max 240) e cobre ~1200-1800 lateralmente.
"""
import numpy as np
from f3_metrics import Match, FX, GOAL_C, GOAL_LO, GOAL_HI, travel
from f3_xg import logistic_fit, predict, is_attempt

FEAT2 = ["gap0/1k", "gap0^2", "t_voo/10", "dentro_gol/1k", "erro_mira/1k",
         "dist/1k", "margem/1k"]


def feat2(k):
    yc = k["y_cross"]
    if np.isfinite(yc):
        miss = max(0.0, abs(yc - GOAL_C) - (GOAL_HI - GOAL_C)) / 1000.0
        inside = max(0.0, (GOAL_HI - GOAL_C) - abs(yc - GOAL_C)) / 1000.0
    else:
        miss, inside = 5.0, 0.0
    reach = travel(k["v"]) >= k["dist"]
    if miss > 0 or not reach:
        # nao entra: forca tudo a zero pelas features
        return [0.0, 0.0, 0.0, 0.0, min(miss, 5.0) + (0.0 if reach else 5.0),
                min(k["dist"], 12000) / 1000.0, 0.0]
    gap = k["gk_gap"]
    gap = 0.0 if not np.isfinite(gap) else min(gap, 3000.0)
    t = k["t_arrive"]
    t = 60.0 if not np.isfinite(t) else min(t, 60.0)
    margin = (gap - (200.0 * t + 560.0)) / 1000.0
    return [gap / 1000.0, (gap / 1000.0) ** 2, t / 10.0, inside, 0.0,
            min(k["dist"], 12000) / 1000.0, np.clip(margin, -5, 2)]


def shots_of(name, side):
    m = Match(name, side)
    return [k for k in m.kicks() if k["mine"] and is_attempt(k)]


def build(cases):
    X, y, src = [], [], []
    for name, side in cases:
        for k in shots_of(name, side):
            X.append(feat2(k)); y.append(1.0 if k["goal"] else 0.0); src.append(name)
    return np.array(X), np.array(y), src


def auc(y, p):
    o = np.argsort(p); r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


if __name__ == "__main__":
    CASES = [("t1", 0), ("eval_0_norm", 0), ("var_1", 0), ("var_2", 0),
             ("swap", 1), ("v6_check", 0)]
    X, y, src = build(CASES)
    print(f"chutes={len(y)} gols={int(y.sum())}")
    w = logistic_fit(X, y, l2=1.0)
    print("coeficientes:")
    print(f"  intercepto  {w[0]:+.3f}")
    for nm, c in zip(FEAT2, w[1:]):
        print(f"  {nm:14s}{c:+.3f}")
    p = predict(w, X)
    print(f"AUC in-sample {auc(y,p):.3f}")

    pcv = np.zeros(len(y))
    for u in sorted(set(src)):
        te = np.array([s == u for s in src])
        pcv[te] = predict(logistic_fit(X[~te], y[~te], l2=1.0), X[te])
    print(f"AUC leave-one-match-out {auc(y,pcv):.3f}")

    print("\ncalibracao out-of-fold por quintil:")
    o = np.argsort(pcv)
    for b in range(5):
        s = o[b * len(o) // 5:(b + 1) * len(o) // 5]
        print(f"  q{b+1}: xG={pcv[s].mean():.3f} real={y[s].mean():.3f} n={len(s)}")

    print("\nxG (out-of-fold) x gols reais, por partida:")
    print(f"{'partida':16s}{'chutes':>8s}{'xG':>8s}{'gols':>7s}{'razao':>8s}")
    for u in ["t1", "eval_0_norm", "var_1", "var_2", "swap", "v6_check"]:
        s = np.array([x == u for x in src])
        print(f"{u:16s}{s.sum():8d}{pcv[s].sum():8.2f}{int(y[s].sum()):7d}"
              f"{y[s].sum()/max(pcv[s].sum(),1e-9):8.2f}")
