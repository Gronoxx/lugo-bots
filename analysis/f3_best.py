"""
FRENTE 3 - escolha final: variantes de xG avaliadas com o estimador de ruido
confiavel (pedacos das 3 partidas v3, 11-35 gl).

Escala: a metrica M vale em "gols equivalentes" M * (media_gols / media_M).
Para xG_soma a escala e 1 por construcao (o modelo e calibrado).
n_partidas = 32 * (DP_M_em_gols / DP_gols)^2
"""
import numpy as np
from f3_metrics import Match
from f3_xg import is_attempt, predict
from f3_xg2 import feat2
from f3_result import W_LOO, W_FULL, CACHE, value

OURS = [("t1", 0, "v1"), ("eval_0_norm", 0, "v2"), ("var_1", 0, "v3"),
        ("var_2", 0, "v3"), ("swap", 1, "v3"), ("v6_check", 0, "v6")]
V3 = [("var_1", 0), ("var_2", 0), ("swap", 1)]
DUM = [("dummies_vs_dummies", 0), ("dummies_vs_dummies", 1)]


def ev(name, side):
    m = Match(name, side)
    w = W_LOO.get(name, W_FULL)
    att = [k for k in m.kicks() if k["mine"] and is_attempt(k)]
    xg = predict(w, np.array([feat2(k) for k in att])) if att else np.array([])
    ti = np.array([k["i"] for k in att], int)
    gt = np.where(np.diff(m.us_score) > 0)[0] + 1
    return m.n, ti, xg, gt


E = {c[:2]: ev(*c[:2]) for c in OURS}
E.update({c: ev(*c) for c in DUM})

AGG = {
    "gols": None,
    "xG_soma": lambda p: p.sum(),
    "xG_cap0.5": lambda p: np.minimum(p, .5).sum(),
    "xG_cap0.3": lambda p: np.minimum(p, .3).sum(),
    "xG_cap0.2": lambda p: np.minimum(p, .2).sum(),
    "sqrt_xG": lambda p: np.sqrt(p).sum(),
    "n_chances(xG>.3)": lambda p: float((p > .3).sum()),
    "n_chances(xG>.15)": lambda p: float((p > .15).sum()),
    "n_chutes": lambda p: float(len(p)),
}


def match_val(c, f):
    T, ti, xg, gt = E[c]
    return float(len(gt)) if f is None else float(f(xg))


def piece_sd(cases, f, K):
    """DP da partida inteira estimada da variacao entre K pedacos."""
    vals = []
    for c in cases:
        T, ti, xg, gt = E[c]
        e = np.linspace(0, T, K + 1).astype(int)
        for b in range(K):
            if f is None:
                vals.append(float(((gt >= e[b]) & (gt < e[b + 1])).sum()))
            else:
                s = (ti >= e[b]) & (ti < e[b + 1])
                vals.append(float(f(xg[s])))
    return np.sqrt(K) * np.std(vals, ddof=1)


mg = np.mean([match_val(c[:2], None) for c in OURS])
sd_g = np.mean([piece_sd(V3, None, K) for K in (4, 6, 12)])
print(f"referencia: media de gols do nosso bot = {mg:.2f}, "
      f"DP(gols) por pedacos = {sd_g:.2f}  -> 32 partidas")
print()
print("=" * 122)
print(f"{'metrica':20s}" + "".join(f"{l:>7s}" for _, _, l in OURS)
      + f"{'dum':>7s}{'escala':>8s}{'DP_bruto':>10s}{'DP_gols_eq':>12s}"
      + f"{'n_part':>8s}{'ganho':>8s}{'corr_g':>8s}{'z(v1-v6)':>10s}")
print("=" * 122)

gols_v = np.array([match_val(c[:2], None) for c in OURS])
out = []
for nm, f in AGG.items():
    v = np.array([match_val(c[:2], f) for c in OURS])
    vd = np.mean([match_val(c, f) for c in DUM])
    scale = mg / v.mean() if v.mean() else 0.0     # unidades de gol por unidade de M
    sd_raw = np.mean([piece_sd(V3, f, K) for K in (4, 6, 12)])
    sd_eq = sd_raw * scale
    npart = 32.0 * (sd_eq / sd_g) ** 2
    corr = float(np.corrcoef(v, gols_v)[0, 1]) if v.std() > 0 else 0.0
    z = (v[0] - v[5]) * scale / sd_eq if sd_eq else 0.0
    out.append((nm, npart))
    print(f"{nm:20s}" + "".join(f"{x:7.2f}" for x in v)
          + f"{vd:7.2f}{scale:8.2f}{sd_raw:10.2f}{sd_eq:12.2f}"
          + f"{npart:8.1f}{32/max(npart,1e-9):8.1f}x{corr:8.2f}{z:10.1f}")

print()
print("=" * 122)
print("LEITURA")
print("  escala      = quantos gols vale 1 unidade da metrica (media_gols/media_M)")
print("  DP_gols_eq  = ruido da metrica traduzido para gols")
print("  n_part      = partidas por configuracao para detectar +1 gol")
print("  z(v1-v6)    = quantos DP a metrica separa v1 de v6. Gols dizem ~0.5.")
print("                Metrica que grita z>3 esta inventando diferenca que o A/B")
print("                de 16 partidas nao viu.")
print("=" * 122)
for nm, n in sorted(out, key=lambda t: t[1]):
    print(f"  {nm:22s} {n:6.1f} partidas")
