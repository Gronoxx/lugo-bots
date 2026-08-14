#!/usr/bin/env python3
"""Primitiva ATOMICA da logica de conducao/marcacao (spec do usuario): a
"marcacao" de um jogador NAO e' um raio, e' a AREA DE CONDUCAO SEGURA no instante
— todo lugar aonde ele pode conduzir a bola (100/turno) sem ser desarmado nos
proximos t turnos, ponderada por DIRECAO (rumo ao gol > lateral > tras).

Seguranca de um raio de conducao (direcao a, ate distancia 100*t): para todo
passo s=1..t e todo adversario k, a bola B(s)=ball+dir*100*s fica fora do disco
inflado do adversario: |B(s)-Q_k| > 100*s + 300 (mesma conta do leg_slack; o
front/back EMERGE dela — marcador atras nao intercepta a cunha frontal).

Saida: por direcao, ate onde da p/ conduzir seguro; agregado em cunhas
rumo-ao-gol / lateral / tras; e uma classificacao (livre / lateral-so / preso).
NAO altera o bot — e' primitiva + demonstracao (proto_reach formalizado).
"""
import math


def safe_dribble_reach(bx, by, opponents, attack_x, t_max=6, n_dirs=72,
                       reach=300.0, speed=100.0):
    """Para cada uma de n_dirs direcoes, a MAIOR distancia (ate speed*t_max) que a
    bola pode ser conduzida em linha reta mantendo-se fora do disco inflado de
    todo adversario. Devolve lista [(ang_rad, dx, dy, dist_segura)]."""
    out = []
    step = speed  # avanco por turno
    for i in range(n_dirs):
        a = 2 * math.pi * i / n_dirs
        dx, dy = math.cos(a), math.sin(a)
        safe = 0.0
        for s in range(1, t_max + 1):
            px, py = bx + dx * step * s, by + dy * step * s
            # fora do campo -> para
            if not (0 <= px <= 20000 and 0 <= py <= 10000):
                break
            ok = True
            for ox, oy in opponents:
                if math.hypot(px - ox, py - oy) <= step * s + reach:
                    ok = False
                    break
            if not ok:
                break
            safe = step * s
        out.append((a, dx, dy, safe))
    return out


def marking_metric(bx, by, opponents, attack_x, t_max=6, n_dirs=72):
    """Agrega a reach segura em cunhas por direcao (rumo ao gol / lateral / tras)
    e classifica. Rumo ao gol = componente x na direcao do gol atacado."""
    goal_dir = 1.0 if attack_x >= 10000 else -1.0   # +x se ataca x=20000
    reaches = safe_dribble_reach(bx, by, opponents, attack_x, t_max, n_dirs)
    maxd = 100.0 * t_max
    fwd = lat = back = 0.0
    nf = nl = nb = 0
    for a, dx, dy, safe in reaches:
        comp = dx * goal_dir                      # >0 rumo ao gol, <0 p/ tras
        frac = safe / maxd                        # 0..1
        if comp > 0.5:
            fwd += frac; nf += 1
        elif comp < -0.5:
            back += frac; nb += 1
        else:
            lat += frac; nl += 1
    fwd = fwd / nf if nf else 0.0
    lat = lat / nl if nl else 0.0
    back = back / nb if nb else 0.0
    total = sum(s for _, _, _, s in reaches) / (len(reaches) * maxd)
    # classificacao (spec do usuario): rumo ao gol vale mais; area total curta = preso
    if fwd > 0.5:
        cls = "livre-p/-gol"
    elif fwd > 0.2 or lat > 0.4:
        cls = "so-lateral/drible"
    elif total < 0.15:
        cls = "PRESO (precisa passar)"
    else:
        cls = "restrito"
    return dict(fwd=fwd, lat=lat, back=back, total=total, cls=cls)


if __name__ == "__main__":
    # DEMONSTRACAO: mesmo portador (10000,5000) atacando +x (gol em 20000).
    # Mostra que marcador ATRAS != marcador na FRENTE (assimetria emerge da conta).
    B = (10000, 5000)
    cenarios = {
        "livre (adversarios longe)":      [(3000, 2000), (16000, 8000)],
        "marcador ATRAS (x=9500)":        [(9500, 5000)],
        "marcador na FRENTE (x=10500)":   [(10500, 5000)],
        "frente+tras (sanduiche)":        [(9500, 5000), (10500, 5000)],
        "cercado (4 lados a ~450)":       [(10450, 5000), (9550, 5000), (10000, 5450), (10000, 4550)],
    }
    print(f"portador em {B} atacando +x (gol 20000). t_max=6 turnos.\n")
    print(f"{'cenario':<32}{'fwd':>6}{'lat':>6}{'back':>6}{'total':>7}  classificacao")
    for nome, opps in cenarios.items():
        m = marking_metric(B[0], B[1], opps, attack_x=20000)
        print(f"{nome:<32}{m['fwd']:6.2f}{m['lat']:6.2f}{m['back']:6.2f}"
              f"{m['total']:7.2f}  {m['cls']}")
    print("\nLeitura: 'fwd'=fracao da reach segura RUMO AO GOL; marcador ATRAS deixa fwd alto")
    print("(rota frontal aberta), marcador na FRENTE derruba fwd (rota fechada) — assimetria")
    print("emerge da reachability, sem heuristica de frente/tras. 'cercado' => PRESO => passar.")
