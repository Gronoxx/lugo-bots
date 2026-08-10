#!/usr/bin/env python3
"""
Pré-teste: o goleiro adversário segue o y da bola, e com quanto de atraso?

A hipótese a validar (do diagnóstico): se deslocarmos a bola lateralmente antes
de finalizar, o goleiro leva tempo para reposicionar, e o chute sai na faixa de
folga grande (>1800d = 70% de conversão) em vez da faixa colada (<1200d = 0%).

Se o goleiro NÃO seguir o y da bola, ou seguir rápido demais, a hipótese morre
aqui — antes de custar código no bot.

  ../.venv/bin/python gk_response.py
"""
import math
import statistics
import sys

import replay

MAX_Y = 10000
GK_HALF = 560.0          # meia-extensão efetiva do goleiro (GOALKEEPER_SIZE 920)


def gk_of(gs, side):
    for p in replay.players(gs, side):
        if p.get("number") == 1:
            return replay.pt(p.get("position"))
    return None


def series(path, our="home"):
    """Extrai (turno, y_bola, y_goleiro_adversario) ao longo da partida."""
    cfg, ev = replay.load(path)
    opp = "away" if our == "home" else "home"
    out = []
    seen = set()
    for gs in replay.snapshots(ev):
        t = gs.get("turn", 0)
        if t in seen:
            continue
        seen.add(t)
        g = gk_of(gs, opp)
        if g is None:
            continue
        bx, by = replay.ball_pos(gs)
        out.append((t, by, g[1], bx))
    return out


def analyze(path, our="home"):
    s = series(path, our)
    if len(s) < 100:
        return None

    # 1) correlação com atraso: o goleiro copia o y da bola de quantos turnos atrás?
    best_lag, best_r = 0, -2.0
    for lag in range(0, 41, 2):
        pares = [(s[i][1], s[i + lag][2]) for i in range(len(s) - lag)]
        if len(pares) < 50:
            continue
        bs = [p[0] for p in pares]
        gs_ = [p[1] for p in pares]
        try:
            r = statistics.correlation(bs, gs_)
        except Exception:
            continue
        if r > best_r:
            best_r, best_lag = r, lag

    # 2) velocidade de reposicionamento do goleiro em y
    vels = [abs(s[i + 1][2] - s[i][2]) for i in range(len(s) - 1)]
    vels = [v for v in vels if v > 0]

    # 3) o teste que importa: após a bola mudar de y bruscamente, quantos turnos
    #    o goleiro leva para voltar a cobrir (folga < 560)?
    recuperacoes = []
    janelas = 0
    for i in range(len(s) - 40):
        dy = s[i + 5][1] - s[i][1]
        if abs(dy) < 1500:
            continue
        janelas += 1
        alvo_y = s[i + 5][1]
        gap0 = abs(s[i + 5][2] - alvo_y)
        if gap0 <= GK_HALF:
            continue
        for k in range(5, 40):
            if abs(s[i + k][2] - alvo_y) <= GK_HALF:
                recuperacoes.append(k - 5)
                break

    return {
        "n": len(s),
        "lag": best_lag,
        "r": best_r,
        "vel_mediana": statistics.median(vels) if vels else 0,
        "vel_p90": sorted(vels)[int(len(vels) * 0.9)] if vels else 0,
        "janelas": janelas,
        "recuperacoes": recuperacoes,
    }


if __name__ == "__main__":
    casos = [
        ("../bench/recordings/var_1.json", "home"),
        ("../bench/recordings/t1.json", "home"),
        ("../bench/recordings/v6_check.json", "home"),
        ("../bench/recordings/swap.json", "away"),
    ]
    print("Resposta do goleiro adversário ao y da bola\n")
    print(f"{'replay':<22}{'atraso':>8}{'corr':>7}{'vel med':>9}{'vel p90':>9}"
          f"{'desloc>1500':>13}{'turnos p/ cobrir':>18}")
    todos = []
    for path, side in casos:
        r = analyze(path, side)
        if not r:
            continue
        rec = r["recuperacoes"]
        todos += rec
        med = f"{statistics.median(rec):.0f}" if rec else "nunca"
        print(f"{path.split('/')[-1]:<22}{r['lag']:>8}{r['r']:>7.2f}"
              f"{r['vel_mediana']:>9.0f}{r['vel_p90']:>9.0f}"
              f"{r['janelas']:>13}{med:>18}")

    print()
    if todos:
        todos.sort()
        print(f"Após um deslocamento lateral da bola >1500d, o goleiro leva")
        print(f"  mediana {statistics.median(todos):.0f} turnos para voltar a cobrir "
              f"(p10={todos[len(todos)//10]}, p90={todos[int(len(todos)*0.9)]})")
        print()
        print("Referência: um chute de 3000d chega em ~9 turnos; de 2000d, em ~6.")
        janela = statistics.median(todos)
        if janela >= 6:
            print(f"=> HIPÓTESE SUSTENTADA: há ~{janela:.0f} turnos de janela, "
                  f"tempo suficiente para finalizar antes de ele cobrir.")
        else:
            print(f"=> HIPÓTESE FRACA: só ~{janela:.0f} turnos de janela — "
                  f"o goleiro recompõe antes da bola chegar.")
    else:
        print("Nenhum deslocamento lateral >1500d encontrado nos replays.")
        print("=> Não conseguimos nem produzir a situação hoje. O primeiro passo")
        print("   é criar o deslocamento, não explorá-lo.")
