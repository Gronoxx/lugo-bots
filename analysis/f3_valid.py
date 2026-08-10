"""
FRENTE 3 - validade: a metrica de baixo ruido MEDE FORCA ou so volume?

Teste decisivo: as metricas territoriais dizem que v1 >> v6 (v1 tem 2,5x mais
tempo na area e 5,7x mais chutes). O A/B de 16 partidas diz que v6 >= v3 ~ v1.
Uma metrica que erra esse ordenamento nao serve para otimizacao evolutiva.
"""
import numpy as np
from f3_result import CACHE, KEYS, value, tab, OURS, V3, boot_sd

gols = np.array([value(CACHE[(n, s)], "gols") for n, s, _ in OURS])
lbl = [l for _, _, l in OURS]

print("=" * 108)
print("CORRELACAO COM GOLS entre as 6 partidas do nosso bot (v1,v2,v3,v3,v3,v6)")
print("e RAZAO v1/v6 - as duas versoes mais opostas em estilo")
print("=" * 108)
print(f"{'metrica':20s}{'corr_gols':>11s}{'v1':>10s}{'v6':>10s}{'v1/v6':>9s}"
      f"{'n_part(B)':>11s}{'valido?':>10s}")
print("-" * 108)

rows = []
for k in KEYS:
    v = np.array([value(CACHE[(n, s)], k) for n, s, _ in OURS])
    c = float(np.corrcoef(v, gols)[0, 1]) if v.std() > 0 else 0.0
    v1, v6 = v[0], v[5]
    ratio = v1 / v6 if v6 != 0 else np.inf
    rows.append((k, c, v1, v6, ratio, tab[k]["nB"]))

for k, c, v1, v6, ratio, nB in sorted(rows, key=lambda r: -r[1]):
    # valido = correlaciona com gols E nao inverte v1 x v6 grosseiramente
    ok = "sim" if (c > 0.5 and 0.4 < abs(ratio) < 2.5) else "NAO"
    print(f"{k:20s}{c:11.3f}{v1:10.2f}{v6:10.2f}{ratio:9.2f}{nB:11.1f}{ok:>10s}")

print()
print("=" * 108)
print("TESTE v1 x v6: quantos desvios-padrao de RUIDO separa as duas versoes?")
print("(o A/B de 16 partidas nao achou diferenca entre v3 e v6; v1 e v3 tem")
print(" placares parecidos. Uma metrica que grita 'v1 e 5x melhor' esta errada.)")
print("=" * 108)
print(f"{'metrica':20s}{'v1':>10s}{'v6':>10s}{'ruido_B':>10s}{'z=(v1-v6)/ruido':>18s}")
print("-" * 108)
for k in KEYS:
    v1 = value(CACHE[("t1", 0)], k)
    v6 = value(CACHE[("v6_check", 0)], k)
    ru = np.mean([boot_sd(CACHE[c], k) for c in V3])
    z = (v1 - v6) / max(ru, 1e-9)
    print(f"{k:20s}{v1:10.2f}{v6:10.2f}{ru:10.2f}{z:18.1f}")

print()
print("=" * 108)
print("METRICA COMBINADA: xG_soma e o unico com garantia de calibracao.")
print("Testando variantes que podem baixar o ruido sem perder a calibracao.")
print("=" * 108)
from f3_metrics import Match
from f3_xg import is_attempt, logistic_fit, predict
from f3_xg2 import feat2
from f3_result import W_LOO, W_FULL

def shots_xg(name, side):
    m = Match(name, side)
    att = [k for k in m.kicks() if k["mine"] and is_attempt(k)]
    w = W_LOO.get(name, W_FULL)
    return predict(w, np.array([feat2(k) for k in att])) if att else np.array([])


VAR = {
    "xG_soma": lambda p: p.sum(),
    "xG_cap0.5": lambda p: np.minimum(p, 0.5).sum(),
    "xG_cap0.3": lambda p: np.minimum(p, 0.3).sum(),
    "sqrt_xG_soma": lambda p: np.sqrt(p).sum(),
    "n_xG>0.3": lambda p: float((p > 0.3).sum()),
    "n_xG>0.1": lambda p: float((p > 0.1).sum()),
    "xG_medio_top5": lambda p: float(np.sort(p)[-5:].mean()) if len(p) else 0.0,
}
print(f"{'variante':16s}" + "".join(f"{l+str(i):>9s}" for i, (_, _, l) in enumerate(OURS))
      + f"{'DP_v3':>9s}{'media':>9s}{'corr_g':>8s}{'D':>7s}{'n_part':>8s}")
P = {(n, s): shots_xg(n, s) for n, s, _ in OURS}
PD = {(n, s): shots_xg(n, s) for n, s in [("dummies_vs_dummies", 0), ("dummies_vs_dummies", 1)]}
gD = tab["gols"]["DA"]
for nm, f in VAR.items():
    v = np.array([f(P[(n, s)]) for n, s, _ in OURS])
    vd = np.array([f(PD[c]) for c in PD])
    v3v = np.array([v[2], v[3], v[4]])
    sd3 = v3v.std(ddof=1)
    sig = v.mean() - vd.mean()
    D = abs(sig) / max(sd3, 1e-9)
    c = float(np.corrcoef(v, gols)[0, 1])
    npart = 32.0 * (gD / D) ** 2
    print(f"{nm:16s}" + "".join(f"{x:9.2f}" for x in v)
          + f"{sd3:9.2f}{v.mean():9.2f}{c:8.2f}{D:7.2f}{npart:8.1f}")
