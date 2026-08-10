"""FRENTE 3 - ajuste e validacao do xG."""
import numpy as np
from f3_xg import collect_shots, logistic_fit, predict, FEAT_NAMES, is_attempt
from f3_metrics import Match

# corpus de ajuste: nosso bot vs dummies (6) + vs rival_p2 (1)
FIT = [("t1", 0), ("eval_0_norm", 0), ("var_1", 0), ("var_2", 0),
       ("swap", 1), ("v6_check", 0), ("p_rival_p2_home_1", 0)]

X, meta = collect_shots(FIT)
y = np.array([1.0 if k["goal"] else 0.0 for _, _, k in meta])
print(f"chutes (tentativas de gol) no corpus de ajuste: {len(y)}  gols: {int(y.sum())}")

# taxa bruta por faixa de distancia
dist = np.array([k["dist"] for _, _, k in meta])
for lo, hi in [(0, 2000), (2000, 4000), (4000, 6000), (6000, 8000)]:
    s = (dist >= lo) & (dist < hi)
    if s.sum():
        print(f"  dist {lo:5d}-{hi:5d}: n={s.sum():4d} gols={int(y[s].sum()):3d} "
              f"taxa={y[s].mean():.3f}")

ot = np.array([k["on_target"] for _, _, k in meta])
print(f"  no alvo (geometria): n={ot.sum()} taxa_gol={y[ot].mean():.3f}")
print(f"  fora do alvo:        n={(~ot).sum()} taxa_gol={y[~ot].mean():.3f}")

w = logistic_fit(X, y, l2=2.0)
print("\ncoeficientes:")
print(f"  intercepto      {w[0]:+.3f}")
for nm, c in zip(FEAT_NAMES, w[1:]):
    print(f"  {nm:16s}{c:+.3f}")

p = predict(w, X)


def auc(y, p):
    o = np.argsort(p)
    r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


print(f"\nAUC (in-sample): {auc(y, p):.3f}")

# validacao cruzada leave-one-match-out
names = [nm for nm, _, _ in meta]
uniq = sorted(set(names))
pcv = np.zeros(len(y))
for u in uniq:
    te = np.array([n == u for n in names])
    wcv = logistic_fit(X[~te], y[~te], l2=2.0)
    pcv[te] = predict(wcv, X[te])
print(f"AUC (leave-one-match-out): {auc(y, pcv):.3f}")

print("\ncalibracao (out-of-fold, por decil de xG):")
o = np.argsort(pcv)
for b in range(5):
    s = o[b * len(o) // 5:(b + 1) * len(o) // 5]
    print(f"  quintil {b+1}: xG_medio={pcv[s].mean():.3f}  gols_reais={y[s].mean():.3f}  n={len(s)}")

print("\nsoma de xG (out-of-fold) x gols reais por partida:")
for u in uniq:
    s = np.array([n == u for n in names])
    print(f"  {u:28s} xG={pcv[s].sum():5.2f}  gols={int(y[s].sum()):3d}  chutes={s.sum():4d}")

np.save("<cache local>", w)
