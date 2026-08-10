"""
FRENTE 3 - resultado: qual metrica discrimina bots com pouco ruido.

Ruido estimado de DUAS formas independentes:
  (A) entre partidas do MESMO bot v3 (var_1, var_2, swap)  -> n=3, IC largo
  (B) bootstrap de blocos moveis DENTRO de cada partida    -> muitos graus de
      liberdade, valida (A) sem depender de so 3 partidas
Sinal = media(nosso bot) - media(dummies) na mesma metrica.
"""
import numpy as np
from f3_metrics import Match, FX, GOAL_C
from f3_xg import logistic_fit, predict, is_attempt
from f3_xg2 import feat2, build

RNG = np.random.default_rng(20260802)
B = 24            # blocos de 250 turnos
NBOOT = 4000

OURS = [("t1", 0, "v1"), ("eval_0_norm", 0, "v2"), ("var_1", 0, "v3"),
        ("var_2", 0, "v3"), ("swap", 1, "v3"), ("v6_check", 0, "v6")]
V3 = [("var_1", 0), ("var_2", 0), ("swap", 1)]
DUM = [("dummies_vs_dummies", 0, "dum"), ("dummies_vs_dummies", 1, "dum")]

# ---------------------------------------------------------------- modelo xG
FITC = [(n, s) for n, s, _ in OURS]
Xf, yf, srcf = build(FITC)
W_FULL = logistic_fit(Xf, yf, l2=1.0)
W_LOO = {u: logistic_fit(Xf[np.array([s != u for s in srcf])],
                         yf[np.array([s != u for s in srcf])], l2=1.0)
         for u in set(srcf)}


# ------------------------------------------------- metricas como (num, den)
def blocks(name, side):
    """Devolve dict metrica -> (num[B], den[B]); valor = sum(num)/sum(den)."""
    m = Match(name, side)
    w = W_LOO.get(name, W_FULL)
    T = m.n
    edges = np.linspace(0, T, B + 1).astype(int)
    bi = np.zeros(T, int)
    for b in range(B):
        bi[edges[b]:edges[b + 1]] = b

    live = ~m.reset
    bx, by = m.bx, m.by
    dg = np.hypot(FX - bx, GOAL_C - by)
    ours = m.hold == 1
    theirs = m.hold == 0
    in3 = bx > FX * 2 / 3

    ks = [k for k in m.kicks() if k["mine"]]
    att = [k for k in ks if is_attempt(k)]
    xg = predict(w, np.array([feat2(k) for k in att])) if att else np.array([])
    kb = np.array([bi[k["i"]] for k in att], int)
    ot = np.array([k["on_target"] for k in att])

    gturn = np.where(np.diff(m.us_score) > 0)[0] + 1
    gb = bi[gturn] if len(gturn) else np.array([], int)

    poss = [p for p in m.possessions() if p["side"] == 1]
    pb = np.array([bi[p["start"]] for p in poss], int)
    padv = np.array([bx[p["end"]] - bx[p["start"]] for p in poss])
    kick_i = set(k["i"] for k in att)
    pshot = np.array([1.0 if any(p["start"] <= t <= p["end"] + 2 for t in kick_i)
                      else 0.0 for p in poss])

    def cnt(idx, wts=None):
        o = np.zeros(B)
        if len(idx):
            np.add.at(o, idx, 1.0 if wts is None else wts)
        return o

    def tsum(mask):
        o = np.zeros(B); np.add.at(o, bi[mask], 1.0); return o

    def tval(vals, mask):
        o = np.zeros(B); np.add.at(o, bi[mask], vals[mask]); return o

    one = np.ones(B) / B
    M = {}
    M["gols"] = (cnt(gb), one)
    M["xG_soma"] = (cnt(kb, xg), one)
    M["n_chutes"] = (cnt(kb), one)
    M["n_no_alvo"] = (cnt(kb[ot]), one)
    M["n_toques"] = (cnt(np.array([bi[k["i"]] for k in ks], int)), one)
    M["xG_por_chute"] = (cnt(kb, xg), cnt(kb))
    M["posse_pct"] = (100 * tsum(ours), tsum(ours | theirs))
    M["territorio_t3"] = (100 * tsum(live & in3), tsum(live))
    M["dist_gol_media"] = (tval(dg, live), tsum(live))
    M["bola_x_medio"] = (tval(bx, live), tsum(live))
    M["tempo_perigo"] = (100 * tsum(live & ours & (dg < 6000)), tsum(live))
    M["tempo_area"] = (100 * tsum(live & (dg < 3000)), tsum(live))
    M["n_posses"] = (cnt(pb), one)
    M["posse_p_chute"] = (100 * cnt(pb, pshot), cnt(pb))
    M["avanco_por_posse"] = (cnt(pb, padv), cnt(pb))
    M["chutes_por_posse"] = (100 * cnt(kb), cnt(pb))
    ent = in3[1:] & ~in3[:-1]
    M["entradas_t3"] = (cnt(bi[1:][ent]), one)
    return M


def value(M, k):
    n, d = M[k]
    return float(n.sum() / d.sum()) if d.sum() else 0.0


def boot_sd(M, k, nboot=NBOOT):
    n, d = M[k]
    idx = RNG.integers(0, B, size=(nboot, B))
    ns = n[idx].sum(1); ds = d[idx].sum(1)
    ok = ds != 0
    return float(np.std(ns[ok] / ds[ok], ddof=1))


CACHE = {}
for name, side, lbl in OURS + DUM:
    CACHE[(name, side)] = blocks(name, side)
KEYS = list(CACHE[(OURS[0][0], OURS[0][1])])

print("=" * 122)
print("VALORES POR PARTIDA  (perspectiva do bot analisado; xG = predicao out-of-fold)")
print("=" * 122)
print(f"{'metrica':18s}" + "".join(f"{l+'/'+n[:7]:>16s}" for n, s, l in OURS)
      + f"{'dum_H':>10s}{'dum_A':>10s}")
for k in KEYS:
    print(f"{k:18s}" + "".join(f"{value(CACHE[(n,s)],k):16.2f}" for n, s, _ in OURS)
          + "".join(f"{value(CACHE[(n,s)],k):10.2f}" for n, s, _ in DUM))

print()
print("=" * 122)
print("RUIDO: (A) entre as 3 partidas v3 x dummies   (B) bootstrap de blocos dentro da partida")
print("=" * 122)
print(f"{'metrica':18s}{'media_v3':>10s}{'DP_A(n=3)':>11s}{'DP_B_med':>10s}"
      f"{'media_nos':>10s}{'media_dum':>10s}{'sinal':>10s}{'D_A':>8s}{'D_B':>8s}"
      f"{'n_A':>8s}{'n_B':>8s}")
print("-" * 122)

N_GOLS = 32.0
tab = {}
for k in KEYS:
    v3v = np.array([value(CACHE[c], k) for c in V3])
    ourv = np.array([value(CACHE[(n, s)], k) for n, s, _ in OURS])
    dumv = np.array([value(CACHE[(n, s)], k) for n, s, _ in DUM])
    sdA = float(v3v.std(ddof=1))
    sdB = float(np.mean([boot_sd(CACHE[c], k) for c in V3]))
    sig = ourv.mean() - dumv.mean()
    tab[k] = dict(v3=v3v.mean(), sdA=sdA, sdB=sdB, our=ourv.mean(),
                  dum=dumv.mean(), sig=sig,
                  DA=abs(sig) / max(sdA, 1e-9), DB=abs(sig) / max(sdB, 1e-9))

gA, gB = tab["gols"]["DA"], tab["gols"]["DB"]
for k in KEYS:
    t = tab[k]
    nA = N_GOLS * (gA / t["DA"]) ** 2 if t["DA"] > 0 else np.inf
    nB = N_GOLS * (gB / t["DB"]) ** 2 if t["DB"] > 0 else np.inf
    t["nA"], t["nB"] = nA, nB
    print(f"{k:18s}{t['v3']:10.2f}{t['sdA']:11.2f}{t['sdB']:10.2f}{t['our']:10.2f}"
          f"{t['dum']:10.2f}{t['sig']:10.2f}{t['DA']:8.2f}{t['DB']:8.2f}"
          f"{nA:8.1f}{nB:8.1f}")

print()
print("=" * 122)
print("DECOMPOSICAO DA VARIANCIA DOS GOLS (por que xG ajuda)")
print("=" * 122)
res = []
for n, s, _ in OURS:
    M = CACHE[(n, s)]
    g, x = value(M, "gols"), value(M, "xG_soma")
    res.append((n, g, x, g - x))
res = np.array([(r[1], r[2], r[3]) for r in res])
print(f"  DP(gols) entre as 6 partidas nosso-bot   = {res[:,0].std(ddof=1):.2f}")
print(f"  DP(xG)   entre as 6 partidas nosso-bot   = {res[:,1].std(ddof=1):.2f}")
print(f"  DP(gols-xG) = ruido de conversao         = {res[:,2].std(ddof=1):.2f}")
print(f"  correlacao xG x gols (6 partidas)        = {np.corrcoef(res[:,0],res[:,1])[0,1]:.3f}")
v3g = np.array([value(CACHE[c], "gols") for c in V3])
v3x = np.array([value(CACHE[c], "xG_soma") for c in V3])
print(f"  so v3: gols={v3g} DP={v3g.std(ddof=1):.2f}")
print(f"  so v3: xG  ={np.round(v3x,2)} DP={v3x.std(ddof=1):.2f}")

print()
print("=" * 122)
print("RANKING FINAL (menos partidas = melhor), pelo estimador B (bootstrap de blocos)")
print("=" * 122)
for k in sorted(KEYS, key=lambda k: tab[k]["nB"]):
    t = tab[k]
    print(f"  {k:20s} n_partidas={t['nB']:7.1f}   (vs 32 dos gols) "
          f"ganho={32/max(t['nB'],1e-9):6.1f}x   sinal/ruido={t['DB']:.2f}")
