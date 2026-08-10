"""
FRENTE 3 - quanto ruido tem mesmo o xG?

Os dois estimadores discordam (DP entre partidas = 0.84; bootstrap de blocos =
1.34). Terceiro estimador independente: dividir cada partida em K pedacos e
medir a variacao entre pedacos DO MESMO BOT.
  Var(partida) = K * Var(pedaco)   se os pedacos forem independentes.
Validacao: o mesmo estimador aplicado a GOLS tem que reproduzir DP ~1.7-2.1.

Ponto chave: xG e calibrado 1:1 com gols (soma xG = soma gols no corpus, e a
razao por partida fica em 0.71-1.44). Logo "+1 gol" = "+1 xG" e o numero de
partidas necessarias e simplesmente  32 * (DP_xG / DP_gols)^2.
"""
import numpy as np
from f3_metrics import Match, FX, GOAL_C
from f3_xg import is_attempt, predict
from f3_xg2 import feat2
from f3_result import W_LOO, W_FULL, CACHE, value

OURS = [("t1", 0, "v1"), ("eval_0_norm", 0, "v2"), ("var_1", 0, "v3"),
        ("var_2", 0, "v3"), ("swap", 1, "v3"), ("v6_check", 0, "v6")]
V3 = [("var_1", 0), ("var_2", 0), ("swap", 1)]


def per_turn_events(name, side):
    m = Match(name, side)
    w = W_LOO.get(name, W_FULL)
    att = [k for k in m.kicks() if k["mine"] and is_attempt(k)]
    xg = predict(w, np.array([feat2(k) for k in att])) if att else np.array([])
    ti = np.array([k["i"] for k in att], int)
    gt = np.where(np.diff(m.us_score) > 0)[0] + 1
    return m.n, ti, xg, gt


DATA = {(n, s): per_turn_events(n, s) for n, s, _ in OURS}


def piece_stats(cases, K):
    """DP estimada da partida inteira a partir da variacao entre K pedacos."""
    xg_p, g_p = [], []
    for c in cases:
        T, ti, xg, gt = DATA[c]
        e = np.linspace(0, T, K + 1).astype(int)
        for b in range(K):
            s = (ti >= e[b]) & (ti < e[b + 1])
            xg_p.append(xg[s].sum())
            g_p.append(float(((gt >= e[b]) & (gt < e[b + 1])).sum()))
    xg_p, g_p = np.array(xg_p), np.array(g_p)
    # variancia entre pedacos, escalada para partida inteira
    return (np.sqrt(K) * xg_p.std(ddof=1), np.sqrt(K) * g_p.std(ddof=1),
            len(xg_p) - 1)


print("=" * 96)
print("ESTIMADORES DE RUIDO (DP de uma partida inteira, bot v3 x dummies)")
print("=" * 96)
print(f"{'estimador':34s}{'DP_gols':>10s}{'DP_xG':>10s}{'razao':>9s}"
      f"{'n_part(=32*razao^2)':>22s}{'gl':>5s}")
print("-" * 96)

est = []
# (1) entre as 3 partidas v3
g3 = np.array([value(CACHE[c], "gols") for c in V3])
x3 = np.array([value(CACHE[c], "xG_soma") for c in V3])
r = x3.std(ddof=1) / g3.std(ddof=1)
print(f"{'entre partidas v3 (n=3)':34s}{g3.std(ddof=1):10.2f}{x3.std(ddof=1):10.2f}"
      f"{r:9.3f}{32*r**2:22.1f}{2:5d}")
est.append(r)

# (2) pedacos de 3000, 1500, 1000, 500 turnos (so partidas v3)
for K, lab in [(2, "metades (3000t)"), (4, "quartos (1500t)"),
               (6, "sextos (1000t)"), (12, "doze (500t)")]:
    sx, sg, gl = piece_stats(V3, K)
    r = sx / sg
    print(f"{'pedacos v3: '+lab:34s}{sg:10.2f}{sx:10.2f}{r:9.3f}{32*r**2:22.1f}{gl:5d}")
    est.append(r)

# (3) pedacos usando TODAS as 6 partidas nossas (mais graus de liberdade,
#     mas mistura versoes -> so a razao interessa)
print("-" * 96)
for K, lab in [(2, "metades (3000t)"), (4, "quartos (1500t)"),
               (6, "sextos (1000t)"), (12, "doze (500t)")]:
    sx, sg, gl = piece_stats([(n, s) for n, s, _ in OURS], K)
    r = sx / sg
    print(f"{'pedacos 6 partidas: '+lab:34s}{sg:10.2f}{sx:10.2f}{r:9.3f}"
          f"{32*r**2:22.1f}{gl:5d}")

print()
print("=" * 96)
print("VALIDACAO: os estimadores de pedacos reproduzem o DP de gols conhecido?")
print("  DP(gols) observado entre as 3 partidas v3 = %.2f" % g3.std(ddof=1))
print("  DP(gols) observado entre as 6 nossas      = %.2f"
      % np.array([value(CACHE[(n, s)], "gols") for n, s, _ in OURS]).std(ddof=1))
print("  (o enunciado diz ~2,0 -> os estimadores de pedacos que derem 1.7-2.2")
print("   sao os confiaveis)")
print("=" * 96)

print()
print("INTERVALO DE CONFIANCA da razao DP_xG/DP_gols pelas 3 partidas v3")
print("  (n=3 -> 2 graus de liberdade -> IC enorme; por isso os pedacos importam)")
lo, hi = min(est), max(est)
print(f"  razao entre estimadores: {lo:.3f} .. {hi:.3f}")
print(f"  n de partidas correspondente: {32*lo**2:.1f} .. {32*hi**2:.1f}")

print()
print("=" * 96)
print("QUANTAS PARTIDAS PARA DETECTAR +1 GOL (poder 80%, alfa 5%, duas amostras)")
print("=" * 96)
for nome, dp in [("gols (DP=2.08)", 2.08), ("gols (DP=1.71)", 1.71),
                 ("xG (DP=0.84)", 0.84), ("xG (DP=1.10)", 1.10),
                 ("xG (DP=1.34)", 1.34)]:
    n = 2 * (1.96 + 0.84) ** 2 * dp ** 2 / 1.0 ** 2
    print(f"  {nome:20s} n por configuracao = {n:6.1f}")
