"""
FRENTE 3 - qual metrica discrimina bots com pouco ruido.

Saida:
  1. modelos auxiliares (xG por chute, xThreat por turno) + calibracao
  2. tabela de metricas por partida
  3. RUIDO estimado de 3 formas independentes
  4. SINAL (baseline x nosso) e teste v3 x v6
  5. quantas partidas cada metrica exige para detectar "+1 gol"
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_lab as M
import frente3_metricas as F

MATCHES = [
    ("dummies_vs_dummies", "home", "base-A"),
    ("dummies_vs_dummies", "away", "base-B"),
    ("t1", "home", "v1"),
    ("eval_0_norm", "home", "v2"),
    ("var_1", "home", "v3_a"),
    ("var_2", "home", "v3_b"),
    ("swap", "away", "v3_c"),
    ("v6_check", "home", "v6"),
]
EXTRA = [("smoke_rival", "home", "v3xrival_p1"),
         ("p_rival_p2_home_1", "home", "v3xtabaj")]
BASE = ["base-A", "base-B"]
V3 = ["v3_a", "v3_b", "v3_c"]           # MESMO bot, 3 partidas -> ruido puro (2 gl)
OURS = ["v1", "v2", "v3_a", "v3_b", "v3_c", "v6"]


def auc(y, p):
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return np.nan
    return float((pos[:, None] > neg[None, :]).mean()
                 + 0.5 * (pos[:, None] == neg[None, :]).mean())


def fit_models():
    names = sorted(set(n for n, _, _ in MATCHES + EXTRA))
    # ---- xG por chute
    Xs, ys = [], []
    for nm in names:
        d = M.load(nm)
        for side in ("home", "away"):
            ev = F.enrich(d, side, F.kick_events(d, side))
            F.label_goals(d, side, ev)
            sh = [e for e in ev if e["on_goal"]]
            if sh:
                Xs.append(F.xg_feat(sh))
                ys.append(np.array([e["goal"] for e in sh], float))
    X, y = np.vstack(Xs), np.concatenate(ys)
    wg = M.fit_logistic(X, y, iters=20000, lr=0.03, l2=1e-4)
    p = M.xg_predict(wg, X)
    print(f"[xG chute]   n={len(y)} gols={int(y.sum())} soma_xG={p.sum():.1f} "
          f"AUC={auc(y, p):.3f}")

    # ---- xThreat por turno
    Xs, ys = [], []
    for nm in names:
        d = M.load(nm)
        for side in ("home", "away"):
            Xs.append(F.xt_features(d, side))
            ys.append(F.xt_labels(d, side))
    X, y = np.vstack(Xs), np.concatenate(ys)
    sub = np.arange(0, len(y), 3)          # subamostra: turnos vizinhos sao redundantes
    wt = M.fit_logistic(X[sub], y[sub], iters=20000, lr=0.05, l2=1e-4)
    pt = M.xg_predict(wt, X)
    print(f"[xThreat turno] n={len(y)} frac_positiva={y.mean():.3f} "
          f"AUC={auc(y, pt):.3f}  frac>{F.XT_THR}={np.mean(pt > F.XT_THR):.3f}")
    return wg, wt


def main():
    wg, wt = fit_models()
    val, se, meta = {}, {}, {}
    for nm, side, lab in MATCHES + EXTRA:
        st = F.block_stats(M.load(nm), side, xg_w=wg, xt_w=wt)
        meta[lab] = st.pop("_meta")
        val[lab] = {k: F.point(v) for k, v in st.items()}
        se[lab] = {k: F.boot_se(v) for k, v in st.items()}
    labs = [l for _, _, l in MATCHES]
    keys = [k for k in val["v3_a"] if all(k in val[l] for l in val)]

    print("\n" + "=" * 100)
    print("1. VALORES POR PARTIDA")
    print(f"{'metrica':22s}" + "".join(f"{l:>10s}" for l in labs)
          + "".join(f"{l:>11s}" for _, _, l in EXTRA))
    for k in keys:
        print(f"{k:22s}"
              + "".join(f"{val[l][k]:10.2f}" for l in labs)
              + "".join(f"{val[l][k]:11.2f}" for _, _, l in EXTRA))

    print("\n" + "=" * 100)
    print("2. RUIDO (desvio-padrao entre partidas do MESMO bot)")
    print("   sd_v3   : desvio das 3 partidas v3 (var_1, var_2, swap) - 2 graus de liberdade")
    print("   sd_par  : |var_1 - var_2|/sqrt(2)  - 1 grau de liberdade")
    print("   sd_boot : media do bootstrap de blocos DENTRO de cada partida v3")
    print(f"\n{'metrica':22s}{'media_v3':>11s}{'sd_v3':>10s}{'sd_par':>10s}{'sd_boot':>10s}"
          f"{'cv_v3_%':>9s}")
    noise = {}
    for k in keys:
        v = np.array([val[l][k] for l in V3])
        sd_v3 = float(v.std(ddof=1))
        sd_par = abs(val["v3_a"][k] - val["v3_b"][k]) / np.sqrt(2)
        sd_bt = float(np.mean([se[l][k] for l in V3]))
        noise[k] = (sd_v3, sd_par, sd_bt)
        cv = 100 * sd_v3 / abs(v.mean()) if v.mean() else np.nan
        print(f"{k:22s}{v.mean():11.2f}{sd_v3:10.3f}{sd_par:10.3f}{sd_bt:10.3f}{cv:9.1f}")

    print("\n" + "=" * 100)
    print("3. SINAL / RUIDO")
    print("   SNR_base = |media(base) - media(v3)| / sd_v3     (bots MUITO diferentes)")
    print("   z_v6     = |v6 - media(v3)| / sd_v3              (bots POUCO diferentes,")
    print("              diferenca real conhecida: mira 19,2 -> 1,3 graus)")
    print(f"\n{'metrica':22s}{'base':>10s}{'v3':>10s}{'v6':>10s}"
          f"{'SNR_base':>10s}{'z_v6':>8s}{'ganho_vs_gols':>15s}")
    snr_gols = None
    rows = []
    for k in keys:
        b = np.mean([val[l][k] for l in BASE])
        v3 = np.mean([val[l][k] for l in V3])
        sd = noise[k][0]
        snr = abs(v3 - b) / sd if sd else np.inf
        z6 = abs(val["v6"][k] - v3) / sd if sd else np.inf
        rows.append((k, b, v3, val["v6"][k], snr, z6))
    snr_gols = dict((r[0], r[4]) for r in rows)["gols"]
    rows.sort(key=lambda r: -r[4])
    for k, b, v3, v6, snr, z6 in rows:
        gain = (snr / snr_gols) ** 2 if snr_gols else np.nan
        print(f"{k:22s}{b:10.2f}{v3:10.2f}{v6:10.2f}{snr:10.2f}{z6:8.2f}"
              f"{gain:14.1f}x")

    print("\n" + "=" * 100)
    print("4. CUSTO EM PARTIDAS PARA DETECTAR '+1 GOL'")
    print("   Ancora: gols tem sd=2,0 (A/B de 8 partidas do usuario) e exige ~32 partidas/config.")
    print("   Duas conversoes independentes de 'quanto da metrica vale 1 gol':")
    print("     (a) escala-base : 1 gol = fracao (1/gap_gols) do gap baseline->v3")
    print("     (b) regressao por bloco: gols_bloco ~ a + b*metrica_bloco (todos os blocos")
    print("         das 6 partidas nosso-bot; delta = 1/b)")
    gap_gols = np.mean([val[l]["gols"] for l in V3]) - np.mean([val[l]["gols"] for l in BASE])

    # regressao por bloco
    blocks = {}
    for nm, side, lab in MATCHES:
        if lab in BASE:
            continue
        st = F.block_stats(M.load(nm), side, xg_w=wg, xt_w=wt)
        st.pop("_meta")
        for k, (num, den) in st.items():
            with np.errstate(invalid="ignore", divide="ignore"):
                r = np.where(den > 0, num / np.maximum(den, 1e-9), np.nan)
            blocks.setdefault(k, []).append(r)
    gblk = np.concatenate(blocks["gols"])

    print(f"\n{'metrica':22s}{'d_1gol(a)':>11s}{'d_1gol(b)':>11s}{'sd_v3':>9s}"
          f"{'n_esc_base':>12s}{'n_regr':>9s}{'corr_bloco':>11s}")
    out = []
    for k in keys:
        b = np.mean([val[l][k] for l in BASE])
        v3 = np.mean([val[l][k] for l in V3])
        gap = v3 - b
        d_a = abs(gap) / gap_gols if gap_gols else np.nan
        mblk = np.concatenate(blocks[k])
        ok = np.isfinite(mblk) & np.isfinite(gblk)
        if ok.sum() > 10 and np.std(mblk[ok]) > 1e-9:
            corr = float(np.corrcoef(mblk[ok], gblk[ok])[0, 1])
            slope = np.cov(mblk[ok], gblk[ok], ddof=1)[0, 1] / np.var(mblk[ok], ddof=1)
            d_b = abs(1.0 / slope) if abs(slope) > 1e-12 else np.inf
        else:
            corr, d_b = np.nan, np.inf
        sd = noise[k][0]
        n_a = 15.7 * sd ** 2 / d_a ** 2 if d_a else np.inf
        n_b = 15.7 * sd ** 2 / d_b ** 2 if np.isfinite(d_b) and d_b else np.inf
        out.append((k, d_a, d_b, sd, n_a, n_b, corr))
    out.sort(key=lambda r: r[4])
    for k, d_a, d_b, sd, n_a, n_b, corr in out:
        print(f"{k:22s}{d_a:11.3f}{d_b:11.3f}{sd:9.3f}{n_a:12.1f}{n_b:9.1f}{corr:11.2f}")

    print("\n" + "=" * 100)
    print("5. EVENTOS POR PARTIDA (tamanho amostral bruto de cada metrica)")
    for l in labs + [x[2] for x in EXTRA]:
        m = meta[l]
        print(f"   {l:10s} gols={m['n_goals']:2d} chutes_ao_alvo={m['n_shots']:3d} "
              f"chutadas_perto={m['n_near']:3d} kicks={m['n_kicks']:3d}")


if __name__ == "__main__":
    main()
