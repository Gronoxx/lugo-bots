"""
FRENTE 3 - estimativa de ruido com mais graus de liberdade.

Com so 3 partidas do mesmo bot, qualquer sd tem 2 gl (IC enorme). Aqui cada
partida das 6 do nosso bot vira DUAS meias-partidas de 3000 turnos. A diferenca
entre as duas metades da MESMA partida e ruido puro (mesmo bot, mesmo
adversario, mesma partida) -> 6 gl para o desvio dentro da partida.

Comparamos, para cada metrica, a variancia dentro da partida com a de gols.
A RAZAO e o que importa: ela diz quantas vezes menos partidas a metrica exige.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_lab as M
import frente3_metricas as F
from frente3_run import MATCHES, EXTRA, BASE, V3
from frente3_final import spearman, fit_all

HALF = 3000


def slice_match(d, a, b):
    out = {}
    for k, v in d.items():
        out[k] = v[a:b]
    return out


def main():
    wg, wgg, wt = fit_all()
    ours = [(nm, side, lab) for nm, side, lab in MATCHES if lab not in BASE]
    base = [(nm, side, lab) for nm, side, lab in MATCHES if lab in BASE]

    F.BLOCK = 250
    halves = {}
    fulls = {}
    for nm, side, lab in MATCHES + EXTRA:
        d = M.load(nm)
        st = F.block_stats(d, side, xg_w=wg, xt_w=wt, xgg_w=wgg)
        st.pop("_meta")
        fulls[lab] = {k: F.point(v) for k, v in st.items()}
        for h, (a, b) in enumerate([(0, HALF), (HALF, 2 * HALF)]):
            dd = slice_match(d, a, b)
            sh = F.block_stats(dd, side, xg_w=wg, xt_w=wt, xgg_w=wgg)
            sh.pop("_meta")
            halves[(lab, h)] = {k: F.point(v) for k, v in sh.items()}

    keys = [k for k in fulls["v3_a"] if all(k in fulls[l] for l in fulls)]
    labs_o = [l for _, _, l in ours]
    all_labs = [l for _, _, l in MATCHES + EXTRA]
    gols = np.array([fulls[l]["gols"] for l in all_labs])

    print("\n" + "=" * 104)
    print("RUIDO DENTRO DA PARTIDA (6 partidas nossas x 2 metades de 3000 turnos)")
    print("sd_meia = sqrt( media_m (x[m,1]-x[m,2])^2 / 2 )   -> 6 graus de liberdade")
    print("Para metricas de CONTAGEM a metade vale metade; comparamos na mesma escala")
    print("multiplicando o desvio por sqrt(2) (contagens) ou 1 (taxas).\n")
    COUNT = {"gols", "chutes_ao_gol", "chutadas_perto_gol", "kicks_total", "xG",
             "xG_amplo", "xG_geom", "chutes_bons_geom", "avanco_total",
             "n_posses", "entradas_chance_clara"}
    res = {}
    for k in keys:
        dif = np.array([halves[(l, 0)][k] - halves[(l, 1)][k] for l in labs_o])
        sd_half = np.sqrt(np.mean(dif ** 2) / 2)
        scale = np.sqrt(2) if k in COUNT else 1.0
        res[k] = sd_half * scale
    sdg = res["gols"]
    print(f"{'metrica':24s}{'sd_dentro':>11s}{'sd_3part':>11s}{'base':>10s}{'v3':>10s}"
          f"{'d_1gol':>10s}{'ruido_rel':>11s}{'n_part':>9s}{'valid':>7s}")
    rows = []
    gap_g = np.mean([fulls[l]["gols"] for l in V3]) - np.mean([fulls[l]["gols"] for l in BASE])
    for k in keys:
        b = np.mean([fulls[l][k] for l in BASE])
        v3 = np.mean([fulls[l][k] for l in V3])
        sd3 = float(np.std([fulls[l][k] for l in V3], ddof=1))
        d1 = abs(v3 - b) / gap_g
        rel = (res[k] / d1) / (sdg / 1.0) if d1 > 0 else np.inf   # ruido em "gols equivalentes"
        npart = 32.0 * rel ** 2
        rho = spearman(np.array([fulls[l][k] for l in all_labs]), gols)
        rows.append((k, res[k], sd3, b, v3, d1, rel, npart, rho))
    rows.sort(key=lambda r: r[7])
    for k, sdh, sd3, b, v3, d1, rel, npart, rho in rows:
        mark = "" if rho >= 0.6 else ("   [validade baixa]" if rho < 0.35 else "   [validade media]")
        print(f"{k:24s}{sdh:11.3f}{sd3:11.3f}{b:10.2f}{v3:10.2f}{d1:10.3f}"
              f"{rel:11.2f}{npart:9.1f}{rho:7.2f}{mark}")

    print("\n" + "=" * 104)
    print("CONSISTENCIA: sd estimado por 3 partidas x por 6 meias-partidas")
    for k in ["gols", "xG", "xG_geom", "chutes_ao_gol", "chutes_bons_geom",
              "posse_no_terco_atq_%", "territorio_%", "xThreat_medio", "posses_c_chute_%"]:
        if k not in res:
            continue
        sd3 = float(np.std([fulls[l][k] for l in V3], ddof=1))
        print(f"   {k:24s} sd_3partidas={sd3:8.3f}   sd_meias(6gl)={res[k]:8.3f}   "
              f"razao={res[k]/max(sd3,1e-9):5.2f}")


if __name__ == "__main__":
    main()
