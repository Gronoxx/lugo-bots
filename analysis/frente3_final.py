"""
FRENTE 3 - conclusao: ruido x sinal x VALIDADE.

Uma metrica so serve de fitness se, alem de ter pouco ruido, for MONOTONA na
forca do bot. Aqui cada candidata leva tres notas:

  ruido   : sd entre as 3 partidas do MESMO bot v3 (var_1, var_2, swap)
  sinal   : gap baseline -> v3 (bots comprovadamente diferentes)
  validade: correlacao de postos com os gols marcados em 10 lados-de-partida
            do corpus (0 a 46 gols) - metrica boa tem que subir com o placar

n_partidas para detectar "+1 gol" e reportado na MESMA convencao do usuario
(gols: sd=2,0 -> ~32 partidas por configuracao).
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_lab as M
import frente3_metricas as F
from frente3_run import MATCHES, EXTRA, BASE, V3, OURS, auc

N_GOLS_REF = 32.0     # partidas/config que gols exigem (A/B de 8 partidas do usuario)


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def fit_all():
    names = sorted(set(n for n, _, _ in MATCHES + EXTRA))
    Xs, Xg, ys = [], [], []
    for nm in names:
        d = M.load(nm)
        for side in ("home", "away"):
            ev = F.enrich(d, side, F.kick_events(d, side))
            F.label_goals(d, side, ev)
            sh = [e for e in ev if e["on_goal"]]
            if sh:
                Xs.append(F.xg_feat(sh))
                Xg.append(F.xg_feat_geom(sh))
                ys.append(np.array([e["goal"] for e in sh], float))
    X, Xg, y = np.vstack(Xs), np.vstack(Xg), np.concatenate(ys)
    wg = M.fit_logistic(X, y, iters=20000, lr=0.03, l2=1e-4)
    wgg = M.fit_logistic(Xg, y, iters=20000, lr=0.03, l2=1e-4)
    print(f"[xG completo   ] AUC={auc(y, M.xg_predict(wg, X)):.3f}  "
          f"soma={M.xg_predict(wg, X).sum():.1f} (gols reais {int(y.sum())})")
    print(f"[xG so geometria] AUC={auc(y, M.xg_predict(wgg, Xg)):.3f}  "
          f"soma={M.xg_predict(wgg, Xg).sum():.1f}")
    print("   -> se o xG completo e muito melhor que o geometrico, o que decide")
    print("      o gol e a POSICAO DO GOLEIRO, nao a qualidade da chegada.")

    Xt, yt = [], []
    for nm in names:
        d = M.load(nm)
        for side in ("home", "away"):
            Xt.append(F.xt_features(d, side))
            yt.append(F.xt_labels(d, side))
    Xt, yt = np.vstack(Xt), np.concatenate(yt)
    sub = np.arange(0, len(yt), 3)
    wt = M.fit_logistic(Xt[sub], yt[sub], iters=20000, lr=0.05, l2=1e-4)
    return wg, wgg, wt


def main():
    wg, wgg, wt = fit_all()
    val, se = {}, {}
    for nm, side, lab in MATCHES + EXTRA:
        st = F.block_stats(M.load(nm), side, xg_w=wg, xt_w=wt, xgg_w=wgg)
        st.pop("_meta")
        val[lab] = {k: F.point(v) for k, v in st.items()}
        se[lab] = {k: F.boot_se(v) for k, v in st.items()}
    all_labs = [l for _, _, l in MATCHES + EXTRA]
    keys = [k for k in val["v3_a"] if all(k in val[l] for l in all_labs)]
    gols = np.array([val[l]["gols"] for l in all_labs])

    print("\n" + "=" * 108)
    print("DECOMPOSICAO DA VARIANCIA DE GOLS (3 partidas do MESMO bot v3)")
    for l in V3:
        s, g = val[l]["chutes_ao_gol"], val[l]["gols"]
        print(f"   {l}: chutes_ao_alvo={s:.0f}  gols={g:.0f}  conversao={100*g/max(s,1):.1f}%"
              f"  xG={val[l]['xG']:.2f}  xG_geom={val[l]['xG_geom']:.2f}")
    sc = np.array([val[l]["chutes_ao_gol"] for l in V3])
    gc = np.array([val[l]["gols"] for l in V3])
    print(f"   cv(chutes)={100*sc.std(ddof=1)/sc.mean():.0f}%   "
          f"cv(conversao)={100*(gc/sc).std(ddof=1)/(gc/sc).mean():.0f}%   "
          f"cv(gols)={100*gc.std(ddof=1)/gc.mean():.0f}%")

    print("\n" + "=" * 108)
    print("TABELA FINAL")
    print(f"{'metrica':24s}{'base':>9s}{'v3':>9s}{'v6':>9s}{'sd_v3':>9s}"
          f"{'SNR':>7s}{'z_v6':>7s}{'valid':>7s}{'n_part':>8s}{'ganho':>7s}")
    snr = {}
    rows = []
    for k in keys:
        b = np.mean([val[l][k] for l in BASE])
        v3 = np.mean([val[l][k] for l in V3])
        v6 = val["v6"][k]
        sd = float(np.std([val[l][k] for l in V3], ddof=1))
        s = abs(v3 - b) / sd if sd > 0 else np.inf
        z6 = abs(v6 - v3) / sd if sd > 0 else np.inf
        rho = spearman(np.array([val[l][k] for l in all_labs]), gols)
        snr[k] = s
        rows.append([k, b, v3, v6, sd, s, z6, rho])
    sg = snr["gols"]
    for r in rows:
        r.append(N_GOLS_REF * (sg / r[5]) ** 2 if r[5] > 0 else np.inf)  # n_partidas
        r.append((r[5] / sg) ** 2)                                       # ganho
    rows.sort(key=lambda r: r[8])
    for k, b, v3, v6, sd, s, z6, rho, npart, gain in rows:
        flag = "" if rho >= 0.6 else ("  <-- validade baixa" if rho < 0.35 else "  <-- validade media")
        print(f"{k:24s}{b:9.2f}{v3:9.2f}{v6:9.2f}{sd:9.3f}{s:7.2f}{z6:7.2f}"
              f"{rho:7.2f}{npart:8.1f}{gain:6.1f}x{flag}")

    print("\n" + "=" * 108)
    print("FRONTEIRA: so as metricas com validade (rho >= 0.6) ordenadas por custo")
    ok = [r for r in rows if r[7] >= 0.6]
    ok.sort(key=lambda r: r[8])
    for k, b, v3, v6, sd, s, z6, rho, npart, gain in ok:
        print(f"   {k:24s} n_partidas={npart:6.1f}  ({gain:.1f}x mais barata que gols) "
              f" rho={rho:.2f}  z_v6={z6:.2f}")

    print("\n" + "=" * 108)
    print("COMPOSITO: regressao de gols sobre metricas validas, por BLOCO de 250 turnos")
    print("(leave-one-match-out para nao superestimar)")
    cand = [k for k in ["chutes_ao_gol", "xG", "xG_geom", "chutadas_perto_gol",
                        "chutes_bons_geom", "posses_c_chute_%", "t_dist<4000_%",
                        "posse_no_terco_atq_%", "xThreat_medio"] if k in keys]
    blocks = {}
    for nm, side, lab in MATCHES:
        st = F.block_stats(M.load(nm), side, xg_w=wg, xt_w=wt, xgg_w=wgg)
        st.pop("_meta")
        blocks[lab] = {k: (lambda nd: np.where(nd[1] > 0, nd[0] / np.maximum(nd[1], 1e-9), 0.0))(st[k])
                       for k in st}
    labs_fit = [l for _, _, l in MATCHES]
    comp = {}
    for held in labs_fit:
        Xtr = np.vstack([np.column_stack([blocks[l][k] for k in cand])
                         for l in labs_fit if l != held])
        ytr = np.concatenate([blocks[l]["gols"] for l in labs_fit if l != held])
        A = np.column_stack([np.ones(len(Xtr)), Xtr])
        w = np.linalg.lstsq(A, ytr, rcond=None)[0]
        Xh = np.column_stack([blocks[held][k] for k in cand])
        comp[held] = float((np.column_stack([np.ones(len(Xh)), Xh]) @ w).sum())
    b = np.mean([comp[l] for l in BASE])
    v3 = np.mean([comp[l] for l in V3])
    sd = float(np.std([comp[l] for l in V3], ddof=1))
    s = abs(v3 - b) / sd
    print("   gols previstos por partida:", {l: round(comp[l], 2) for l in labs_fit})
    print(f"   base={b:.2f}  v3={v3:.2f}  v6={comp['v6']:.2f}  sd_v3={sd:.3f}  "
          f"SNR={s:.2f}  n_partidas={N_GOLS_REF*(sg/s)**2:.1f}  "
          f"({(s/sg)**2:.1f}x vs gols)")


if __name__ == "__main__":
    main()
