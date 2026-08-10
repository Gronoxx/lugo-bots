"""
FRENTE 3 - checagens de robustez da metrica vencedora (xG_geom) e
decomposicao da variancia dos gols.

1. o modelo geometrico reajustado SEM a partida avaliada (leave-one-match-out)
2. erro-padrao por bootstrap de blocos vs desvio entre partidas
3. sensibilidade ao tamanho do bloco e ao limiar de deteccao de chute
4. de onde vem a variancia dos gols
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_lab as M
import frente3_metricas as F
from frente3_run import MATCHES, EXTRA, BASE, V3, auc

ALL = MATCHES + EXTRA


def shots_of(nm, side):
    d = M.load(nm)
    ev = F.enrich(d, side, F.kick_events(d, side))
    F.label_goals(d, side, ev)
    sh = [e for e in ev if e["on_goal"]]
    return d, sh


def collect():
    data = {}
    for nm, side, lab in ALL:
        d, sh = shots_of(nm, side)
        data[lab] = (nm, side, d, sh)
    return data


def fit(shots, geom=True):
    X = F.xg_feat_geom(shots) if geom else F.xg_feat(shots)
    y = np.array([e["goal"] for e in shots], float)
    return M.fit_logistic(X, y, iters=20000, lr=0.03, l2=1e-4)


def main():
    data = collect()
    labs = list(data)

    print("=" * 96)
    print("1. LEAVE-ONE-MATCH-OUT: xG_geom com o modelo ajustado sem a propria partida")
    lomo, insample = {}, {}
    allsh = [e for l in labs for e in data[l][3]]
    w_full = fit(allsh)
    for l in labs:
        tr = [e for k in labs if k != l for e in data[k][3]]
        w = fit(tr)
        sh = data[l][3]
        lomo[l] = float(M.xg_predict(w, F.xg_feat_geom(sh)).sum()) if sh else 0.0
        insample[l] = float(M.xg_predict(w_full, F.xg_feat_geom(sh)).sum()) if sh else 0.0
    print(f"{'partida':12s}{'gols':>7s}{'xGgeom_in':>11s}{'xGgeom_LOMO':>13s}{'n_chutes':>10s}")
    for l in [x[2] for x in ALL]:
        print(f"{l:12s}{len(M.goal_turns(data[l][2], data[l][1])):7d}"
              f"{insample[l]:11.2f}{lomo[l]:13.2f}{len(data[l][3]):10d}")
    for nome, dd in (("in-sample", insample), ("LOMO", lomo)):
        v = np.array([dd[l] for l in V3])
        b = np.mean([dd[l] for l in BASE])
        sd = v.std(ddof=1)
        print(f"   {nome:10s} base={b:.2f} v3={v.mean():.2f} sd_v3={sd:.3f} "
              f"SNR={(v.mean()-b)/sd:.2f}  v6={dd['v6']:.2f}")

    print("\n" + "=" * 96)
    print("2. RUIDO: bootstrap dentro da partida x desvio entre partidas (xG_geom)")
    wt = None
    for l in V3 + ["v6"]:
        nm, side, d, sh = data[l]
        st = F.block_stats(d, side, xg_w=None, xt_w=None, xgg_w=w_full)
        print(f"   {l:6s} xG_geom={F.point(st['xG_geom']):.2f}  "
              f"SE_bootstrap={F.boot_se(st['xG_geom']):.3f}")
    v = np.array([lomo[l] for l in V3])
    sd = v.std(ddof=1)
    lo = sd * np.sqrt(2 / 5.991)   # IC90% de sigma com 2 gl (qui2)
    hi = sd * np.sqrt(2 / 0.103)
    print(f"   sd entre as 3 partidas v3 = {sd:.3f}  (IC90% da sd verdadeira: "
          f"{lo:.2f} a {hi:.2f} - so 2 graus de liberdade!)")

    print("\n" + "=" * 96)
    print("3. SENSIBILIDADE (sd de xG_geom entre as 3 partidas v3)")
    base_thr = 30
    for thr in (20, 30, 50, 80):
        F.__dict__["_thr"] = thr
        vals = []
        for l in V3 + BASE + ["v6"]:
            nm, side, d, _ = data[l]
            sp = d["bspeed"].astype(float)
            hs = d["hold_side"]
            s = 0 if side == "home" else 1
            idx = np.where((np.diff(sp) > thr) & (hs[:-1] == s))[0]
            ev = F.kick_events(d, side)
            ev = [e for e in ev if (sp[e["i"]] - sp[e["i"] - 1]) > thr]
            F.enrich(d, side, ev)
            F.label_goals(d, side, ev)
            sh = [e for e in ev if e["on_goal"]]
            vals.append(float(M.xg_predict(w_full, F.xg_feat_geom(sh)).sum()) if sh else 0.0)
        v3v = np.array(vals[:3]); bv = np.mean(vals[3:5])
        print(f"   limiar de chute >{thr:3d} d/turno: v3={v3v.mean():.2f} "
              f"sd={v3v.std(ddof=1):.3f} base={bv:.2f} SNR={(v3v.mean()-bv)/v3v.std(ddof=1):.2f}")
    for blk in (150, 250, 500, 1000):
        F.BLOCK = blk
        ses = []
        for l in V3:
            nm, side, d, _ = data[l]
            st = F.block_stats(d, side, xgg_w=w_full)
            ses.append(F.boot_se(st["xG_geom"]))
        print(f"   bloco={blk:4d} turnos: SE_bootstrap medio de xG_geom = {np.mean(ses):.3f}")
    F.BLOCK = 250

    print("\n" + "=" * 96)
    print("4. DE ONDE VEM A VARIANCIA DOS GOLS (3 partidas v3)")
    w_gk = fit(allsh, geom=False)
    tab = []
    for l in V3:
        nm, side, d, sh = data[l]
        g = len(M.goal_turns(d, side))
        xgg = float(M.xg_predict(w_full, F.xg_feat_geom(sh)).sum())
        xg = float(M.xg_predict(w_gk, F.xg_feat(sh)).sum())
        tab.append((l, len(sh), xgg, xg, g))
    for l, n, a, b, g in tab:
        print(f"   {l:6s} chutes={n:3d}  xG_geom={a:6.2f}  xG_com_goleiro={b:6.2f}  gols={g:2d}")
    arr = np.array([[a, b, g] for _, _, a, b, g in tab])
    v_geom = arr[:, 0].var(ddof=1)
    v_xg = arr[:, 1].var(ddof=1)
    v_g = arr[:, 2].var(ddof=1)
    print(f"\n   Var(xG_geom)      = {v_geom:6.2f}   -> {100*v_geom/v_g:5.1f}% da variancia dos gols")
    print(f"   Var(xG c/ goleiro)= {v_xg:6.2f}   -> {100*v_xg/v_g:5.1f}%")
    print(f"   Var(gols)         = {v_g:6.2f}   -> 100%")
    print("   leitura: o que o bot CRIA (geometria dos chutes) responde por pouco;")
    print("   a posicao do goleiro no instante do chute e o sorteio final respondem pelo resto.")

    print("\n" + "=" * 96)
    print("5. DISTRIBUICAO DO xG_geom POR CHUTE (para ver se nao e so contagem de chutes)")
    for l in V3 + ["v6"]:
        sh = data[l][3]
        p = M.xg_predict(w_full, F.xg_feat_geom(sh))
        print(f"   {l:6s} n={len(p):3d} media={p.mean():.3f} "
              f"p10={np.percentile(p,10):.3f} mediana={np.median(p):.3f} "
              f"p90={np.percentile(p,90):.3f} soma={p.sum():.2f}")


if __name__ == "__main__":
    main()
