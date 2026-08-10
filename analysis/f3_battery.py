"""
FRENTE 3 - bateria de metricas candidatas + razao sinal/ruido.

Regras:
  - xG dos chutes usa predicao OUT-OF-FOLD (modelo re-ajustado sem a partida
    avaliada), para nao contaminar a comparacao.
  - ruido = desvio entre partidas do MESMO bot (v3: var_1, var_2, swap)
  - sinal = diferenca entre bots que sabemos serem diferentes
    (dummies << nosso bot)
"""
import numpy as np
from f3_metrics import Match, FX, GOAL_C, travel
from f3_xg import (collect_shots, logistic_fit, predict, shot_features,
                   is_attempt)

SCR = "<cache local>"

# corpus onde o adversario e o mesmo (dummies). Fit do xG so aqui.
DUMMY_OPP = [("t1", 0), ("eval_0_norm", 0), ("var_1", 0), ("var_2", 0),
             ("swap", 1), ("v6_check", 0)]
BASELINE = [("dummies_vs_dummies", 0), ("dummies_vs_dummies", 1)]
# lado dummy das nossas partidas: baseline sofrendo pressao (contexto diferente)
DUMMY_SIDE = [("t1", 1), ("eval_0_norm", 1), ("var_1", 1), ("var_2", 1),
              ("swap", 0), ("v6_check", 1)]
EXTRA = [("smoke_rival", 0), ("p_rival_p2_home_1", 0)]

ALL = DUMMY_OPP + BASELINE + DUMMY_SIDE + EXTRA

# ------------------------------------------------------------------ xG model
Xf, metaf = collect_shots(DUMMY_OPP)
yf = np.array([1.0 if k["goal"] else 0.0 for _, _, k in metaf])
W_FULL = logistic_fit(Xf, yf, l2=2.0)
W_LOO = {}
for nm in sorted(set(n for n, _, _ in metaf)):
    te = np.array([n == nm for n, _, _ in metaf])
    W_LOO[nm] = logistic_fit(Xf[~te], yf[~te], l2=2.0)


def xg_weights(name):
    return W_LOO.get(name, W_FULL)


def xt_surface(x, y, w):
    """Ameaca posicional: xG de um chute hipotetico de forca maxima daqui,
    mirando o centro do gol, com o goleiro em posicao 'neutra' (folga 800)."""
    d = float(np.hypot(FX - x, GOAL_C - y))
    fake = dict(dist=d, v=400.0, y_cross=GOAL_C, gk_gap=800.0,
                t_arrive=min(d / 300.0, 60.0))
    f = np.array([shot_features(fake)])
    return float(predict(w, f)[0])


# grade de xT pre-calculada (independente do bot)
GX = np.linspace(0, FX, 81)
GY = np.linspace(0, 10000, 41)
XT = np.array([[xt_surface(x, y, W_FULL) for y in GY] for x in GX])


def xt_lookup(bx, by):
    ix = np.clip(np.searchsorted(GX, bx) - 1, 0, len(GX) - 1)
    iy = np.clip(np.searchsorted(GY, by) - 1, 0, len(GY) - 1)
    return XT[ix, iy]


# ------------------------------------------------------------------ metricas
def metrics(name, side):
    m = Match(name, side)
    n = m.n
    w = xg_weights(name)
    ks = [k for k in m.kicks() if k["mine"]]
    att = [k for k in ks if is_attempt(k)]
    Xs = np.array([shot_features(k) for k in att]) if att else np.zeros((0, 7))
    xg = predict(w, Xs) if len(att) else np.array([])

    live = ~m.reset
    bx, by = m.bx, m.by
    dgoal = np.hypot(FX - bx, GOAL_C - by)
    ours = m.hold == 1
    theirs = m.hold == 0
    posse = ours.sum() / max(1, (ours.sum() + theirs.sum()))

    poss = m.possessions()
    mine_p = [p for p in poss if p["side"] == 1]
    adv = [bx[p["end"]] - bx[p["start"]] for p in mine_p]
    # posse termina em chute? (chute nosso dentro da janela da posse +2 turnos)
    kick_turns = set(k["i"] for k in att)
    ended_shot = sum(1 for p in mine_p
                     if any(p["start"] <= t <= p["end"] + 2 for t in kick_turns))

    in3 = bx > FX * 2 / 3
    entries = int(np.sum(in3[1:] & ~in3[:-1]))
    xt = xt_lookup(bx, by)

    r = {}
    r["gols"] = float(m.us_score[-1])
    r["xG_soma"] = float(xg.sum())
    r["n_chutes"] = float(len(att))
    r["n_no_alvo"] = float(sum(1 for k in att if k["on_target"]))
    r["xG_por_chute"] = float(xg.mean()) if len(xg) else 0.0
    r["xG_top10"] = float(np.sort(xg)[-10:].sum()) if len(xg) else 0.0
    r["posse_pct"] = 100 * posse
    r["territorio_t3"] = 100 * float(np.mean(in3[live]))
    r["bola_x_medio"] = float(np.mean(bx[live]))
    r["dist_gol_media"] = float(np.mean(dgoal[live]))
    r["tempo_perigo"] = 100 * float(np.mean(ours[live] & (dgoal[live] < 6000)))
    r["tempo_area"] = 100 * float(np.mean((dgoal[live] < 3000)))
    r["n_posses"] = float(len(mine_p))
    r["posse_p_chute"] = 100 * ended_shot / max(1, len(mine_p))
    r["avanco_por_posse"] = float(np.mean(adv)) if adv else 0.0
    r["entradas_t3"] = float(entries)
    r["xT_medio"] = float(np.mean(xt[live]))
    r["xT_posse"] = float(np.sum(xt[live & ours])) / 1000.0
    r["n_toques"] = float(len(ks))
    r["xG_por_1000t"] = float(xg.sum()) / 6.0
    return r


NAMES = None
res = {}
for name, side in ALL:
    r = metrics(name, side)
    res[(name, side)] = r
    if NAMES is None:
        NAMES = list(r)

LBL = {("t1", 0): "v1", ("eval_0_norm", 0): "v2", ("var_1", 0): "v3",
       ("var_2", 0): "v3", ("swap", 1): "v3(away)", ("v6_check", 0): "v6",
       ("dummies_vs_dummies", 0): "dummy", ("dummies_vs_dummies", 1): "dummy",
       ("smoke_rival", 0): "v3 vs rival_p1", ("p_rival_p2_home_1", 0): "v3 vs rival_p2"}

print("=" * 118)
print("TABELA BRUTA (perspectiva do lado analisado; campo espelhado p/ atacar em x=20000)")
print("=" * 118)
hdr = f"{'metrica':18s}" + "".join(f"{LBL[c][:9]:>10s}" for c in DUMMY_OPP) \
      + f"{'dumH':>8s}{'dumA':>8s}"
print(hdr)
print(f"{'partida':18s}" + "".join(f"{c[0][:9]:>10s}" for c in DUMMY_OPP) + f"{'d_v_d':>8s}{'d_v_d':>8s}")
print("-" * 118)
for k in NAMES:
    row = f"{k:18s}"
    for c in DUMMY_OPP:
        row += f"{res[c][k]:10.2f}"
    for c in BASELINE:
        row += f"{res[c][k]:8.2f}"
    print(row)

np.save(SCR + "/battery.npy", np.array([res], dtype=object), allow_pickle=True)

# ------------------------------------------------------- sinal / ruido
V3 = [("var_1", 0), ("var_2", 0), ("swap", 1)]
OURS_ALL = DUMMY_OPP


def sd(vals):
    v = np.array(vals, float)
    return float(v.std(ddof=1))


print()
print("=" * 118)
print("SINAL / RUIDO")
print(" ruido_v3 = DP entre var_1, var_2, swap (mesmo bot v3, mesmo adversario)")
print(" ruido_nos = DP entre as 6 partidas nosso-bot-vs-dummies (inclui diferenca real de versao: LIMITE SUPERIOR)")
print(" sinal = media(nosso bot) - media(dummy baseline)")
print("=" * 118)
print(f"{'metrica':18s}{'m_v3':>9s}{'ruido_v3':>9s}{'m_nos':>9s}{'ruido_nos':>10s}"
      f"{'m_dummy':>9s}{'sinal':>9s}{'D=sin/ru':>10s}{'n_part':>9s}{'vs_gols':>9s}")
print("-" * 118)

rows = []
gols_D = None
for k in NAMES:
    v3v = [res[c][k] for c in V3]
    ourv = [res[c][k] for c in OURS_ALL]
    dumv = [res[c][k] for c in BASELINE]
    s_v3, s_our = sd(v3v), sd(ourv)
    sig = np.mean(ourv) - np.mean(dumv)
    ru = max(s_v3, 1e-9)
    D = abs(sig) / ru
    rows.append((k, np.mean(v3v), s_v3, np.mean(ourv), s_our, np.mean(dumv), sig, D))

gols = [r for r in rows if r[0] == "gols"][0]
gols_D = gols[7]
# +1 gol = 1/sinal_gols da diferenca dummy->nos; n=32 para gols (dado)
N_GOLS = 32.0
for (k, mv3, s3, mo, so, md, sig, D) in rows:
    npart = N_GOLS * (gols_D / D) ** 2 if D > 0 else np.inf
    print(f"{k:18s}{mv3:9.2f}{s3:9.2f}{mo:9.2f}{so:10.2f}{md:9.2f}{sig:9.2f}"
          f"{D:10.2f}{npart:9.1f}{D/gols_D:9.2f}x")
