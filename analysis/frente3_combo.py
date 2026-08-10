"""
FRENTE 3 - resposta final.

1. converte cada metrica para UNIDADE DE GOL (divide pelo ganho por gol medido
   no eixo baseline -> v3), de modo que todas fiquem comparaveis
2. usa a estimativa de ruido CONSERVADORA = max(sd de 3 partidas, sd de 6 meias)
3. testa combinacoes de peso igual (media de estimadores) - se os ruidos nao
   forem perfeitamente correlacionados, a media tem menos ruido que cada um
4. imprime n de partidas por configuracao para detectar +1 gol
"""
import os
import sys
import itertools
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics_lab as M
import frente3_metricas as F
from frente3_run import MATCHES, EXTRA, BASE, V3
from frente3_final import spearman, fit_all
from frente3_meias import slice_match, HALF

SD_GOLS_REF = 2.0     # do A/B de 8 partidas do usuario (estimativa mais confiavel)
N_GOLS_REF = 32.0
COUNT = {"gols", "chutes_ao_gol", "chutadas_perto_gol", "kicks_total", "xG",
         "xG_amplo", "xG_geom", "chutes_bons_geom", "avanco_total",
         "n_posses", "entradas_chance_clara"}


def main():
    wg, wgg, wt = fit_all()
    fulls, halves = {}, {}
    for nm, side, lab in MATCHES + EXTRA:
        d = M.load(nm)
        st = F.block_stats(d, side, xg_w=wg, xt_w=wt, xgg_w=wgg)
        st.pop("_meta")
        fulls[lab] = {k: F.point(v) for k, v in st.items()}
        for h, (a, b) in enumerate([(0, HALF), (HALF, 2 * HALF)]):
            sh = F.block_stats(slice_match(d, a, b), side, xg_w=wg, xt_w=wt, xgg_w=wgg)
            sh.pop("_meta")
            halves[(lab, h)] = {k: F.point(v) for k, v in sh.items()}

    all_labs = [l for _, _, l in MATCHES + EXTRA]
    labs_o = [l for _, _, l in MATCHES if l not in BASE]
    keys = [k for k in fulls["v3_a"] if all(k in fulls[l] for l in fulls)]
    gols = np.array([fulls[l]["gols"] for l in all_labs])
    gap_g = np.mean([fulls[l]["gols"] for l in V3]) - np.mean([fulls[l]["gols"] for l in BASE])

    info = {}
    for k in keys:
        b = np.mean([fulls[l][k] for l in BASE])
        v3 = np.mean([fulls[l][k] for l in V3])
        d1 = (v3 - b) / gap_g                      # unidades da metrica por gol (com sinal)
        if abs(d1) < 1e-12:
            continue
        sd3 = float(np.std([fulls[l][k] for l in V3], ddof=1))
        dif = np.array([halves[(l, 0)][k] - halves[(l, 1)][k] for l in labs_o])
        sc = np.sqrt(2) if k in COUNT else 1.0
        sdh = np.sqrt(np.mean(dif ** 2) / 2) * sc
        rho = spearman(np.array([fulls[l][k] for l in all_labs]), gols)
        info[k] = dict(d1=d1, sd3=sd3, sdh=sdh, sd=max(sd3, sdh), rho=rho,
                       base=b, v3=v3, v6=fulls[k and "v6"][k])

    print("\n" + "=" * 100)
    print("METRICAS EM UNIDADE DE GOL (ruido conservador = max das duas estimativas)")
    print(f"{'metrica':24s}{'1gol=':>10s}{'sd_gol_eq':>11s}{'n_part':>9s}{'ganho':>8s}"
          f"{'valid':>7s}{'v6-v3(gols_eq)':>16s}")
    tab = []
    for k, v in info.items():
        sd_eq = v["sd"] / abs(v["d1"])
        n = N_GOLS_REF * (sd_eq / SD_GOLS_REF) ** 2
        d6 = (v["v6"] - v["v3"]) / v["d1"]
        tab.append((k, v["d1"], sd_eq, n, N_GOLS_REF / n, v["rho"], d6))
    tab.sort(key=lambda r: r[3])
    for k, d1, sd_eq, n, gain, rho, d6 in tab:
        mark = "" if rho >= 0.6 else ("  [INVALIDA]" if rho < 0.35 else "  [duvidosa]")
        print(f"{k:24s}{d1:10.3f}{sd_eq:11.3f}{n:9.1f}{gain:7.1f}x{rho:7.2f}"
              f"{d6:16.2f}{mark}")

    valid = [k for k, v in info.items() if v["rho"] >= 0.6 and k != "gols"]
    print(f"\nmetricas validas (rho>=0.60): {valid}")

    print("\n" + "=" * 100)
    print("CORRELACAO DO RUIDO entre as metricas validas (nas 6 diferencas de meia-partida)")
    D = {}
    for k in valid + ["gols"]:
        dif = np.array([halves[(l, 0)][k] - halves[(l, 1)][k] for l in labs_o])
        D[k] = dif / info[k]["d1"]
    ks = valid + ["gols"]
    print("        " + "".join(f"{k[:9]:>11s}" for k in ks))
    for a in ks:
        print(f"{a[:8]:8s}" + "".join(
            f"{np.corrcoef(D[a], D[b])[0,1]:11.2f}" for b in ks))

    print("\n" + "=" * 100)
    print("COMBINACOES DE PESO IGUAL (media das metricas ja convertidas em gols)")
    best = []
    for r in (1, 2, 3, 4):
        for combo in itertools.combinations(valid, r):
            gh = {l: np.mean([fulls[l][k] / info[k]["d1"] for k in combo])
                  for l in all_labs}
            dif = np.array([np.mean([(halves[(l, 0)][k] - halves[(l, 1)][k]) / info[k]["d1"]
                                     for k in combo]) for l in labs_o])
            sdh = np.sqrt(np.mean(dif ** 2) / 2) * np.sqrt(2)
            sd3 = float(np.std([gh[l] for l in V3], ddof=1))
            sd = max(sd3, sdh)
            b = np.mean([gh[l] for l in BASE])
            v3 = np.mean([gh[l] for l in V3])
            scale = (v3 - b) / gap_g
            sd_eq = sd / abs(scale) if scale else np.inf
            n = N_GOLS_REF * (sd_eq / SD_GOLS_REF) ** 2
            rho = spearman(np.array([gh[l] for l in all_labs]), gols)
            best.append((n, combo, sd_eq, rho, (gh["v6"] - v3) / scale, sd3, sdh))
    best.sort()
    print(f"{'n_part':>8s}{'ganho':>8s}{'sd_gol_eq':>11s}{'valid':>7s}{'v6-v3':>8s}  combinacao")
    for n, combo, sd_eq, rho, d6, sd3, sdh in best[:14]:
        print(f"{n:8.1f}{N_GOLS_REF/n:7.1f}x{sd_eq:11.3f}{rho:7.2f}{d6:8.2f}  "
              + " + ".join(combo))

    print("\n" + "=" * 100)
    print("VALORES DA MELHOR COMBINACAO POR PARTIDA (em gols equivalentes)")
    n, combo, sd_eq, rho, d6, sd3, sdh = best[0]
    gh = {l: np.mean([fulls[l][k] / info[k]["d1"] for k in combo]) for l in all_labs}
    for l in all_labs:
        print(f"   {l:12s} gols={fulls[l]['gols']:5.1f}   metrica={gh[l]:6.2f}")
    print(f"\n   sd(3 partidas v3)={sd3:.3f}  sd(6 meias)={sdh:.3f}  usado={max(sd3,sdh):.3f}")
    print(f"   n_partidas={n:.1f} vs 32 de gols  ->  {N_GOLS_REF/n:.1f}x mais barato")


if __name__ == "__main__":
    main()
