"""
proto_reach.py — PROTOTIPO EMPIRICO.

Demonstra o ENCOLHIMENTO do conjunto alcancavel-SEGURO por drible ao crescer o
horizonte t, e o GAP entre a checagem de seguranca PIOR-CASO (disco do adversario
inflado 100*s por passo) e a REALIDADE (posicoes reais dos adversarios nos turnos
seguintes do replay).

Fisica (verificada): jogador 100 u/turno, sem inercia/colisao; roubo por
proximidade quando o corpo do adversario chega a <=300 (TOUCH_RADIUS) da bola.
Bola em posse anda grudada com o portador (~100 u/turno).

Rodar:
  PYTHONPATH=$HOME/lugo-quando-passar/bot/src:$HOME/lugo-quando-passar/analysis \
  $HOME/lugo-bots/.venv/bin/python $HOME/lugo-quando-passar/bench/proto_reach.py
"""

import math
import replay as R
from geometry import (
    ball_range, turns_for_ball, PLAYER_SPEED, TOUCH_RADIUS,
    GOALKEEPER_HALF_EXTENT, MAX_X, GOAL_MIN_Y, GOAL_MAX_Y, DANGEROUS_SHOT_RANGE,
)

REPLAY = "$HOME/lugo-bots/bench/recordings/fin_002_home.json"
HORIZONS = [1, 2, 3, 5, 10]
DIRS = list(range(0, 360, 5))          # 72 direcoes, 5 em 5 graus
NDIR = len(DIRS)
DTHETA = math.radians(5)
STEP = PLAYER_SPEED                     # 100 u por passo de drible
GOAL_X = MAX_X                          # HOME ataca x=20000
GOAL_YS = list(range(int(GOAL_MIN_Y), int(GOAL_MAX_Y) + 1, 100))


def load_turnmap(path):
    """turn -> ultimo snapshot daquele turno (uma posicao por turno inteiro)."""
    _, events = R.load(path)
    tm = {}
    for gs in R.snapshots(events):
        tm[gs.get("turn", 0)] = gs
    return tm


def opp_positions(gs):
    """Lista de (x,y) dos adversarios (AWAY) no snapshot."""
    return [R.pt(p.get("position")) for p in R.players(gs, "away")]


def keeper_pos(gs):
    """Goleiro AWAY: numero 1; fallback = jogador AWAY mais proximo da linha do gol."""
    aps = R.players(gs, "away")
    for p in aps:
        if p.get("number") == 1:
            return R.pt(p.get("position"))
    return max((R.pt(p.get("position")) for p in aps),
              key=lambda q: q[0], default=(GOAL_X, 5000))


# ---------------------------------------------------------------- seguranca
def safe_radius_worstcase(bx, by, dx, dy, t, opps):
    """Maior passo s<=t em que a bola dribla seguro na direcao (dx,dy).
    Seguro no passo s: para TODO adversario, dist(B(s),Q^0) > 100*s + 300.
    Retorna s_max (0..t). s_max==t => direcao segura ate o horizonte."""
    for s in range(1, t + 1):
        Bx, By = bx + dx * STEP * s, by + dy * STEP * s
        reach = STEP * s + TOUCH_RADIUS
        for (ox, oy) in opps:
            if math.hypot(Bx - ox, By - oy) <= reach:
                return s - 1
    return t


def safe_radius_real(bx, by, dx, dy, t, turnmap, turn0):
    """Igual, mas com posicoes REAIS dos adversarios em turn0+s.
    Seguro no passo s: para TODO adversario real, dist(B(s),Q_real) > 300."""
    for s in range(1, t + 1):
        gs = turnmap.get(turn0 + s)
        if gs is None:
            return s - 1          # sem dado real -> nao conta como seguro alem daqui
        Bx, By = bx + dx * STEP * s, by + dy * STEP * s
        for (ox, oy) in opp_positions(gs):
            if math.hypot(Bx - ox, By - oy) <= TOUCH_RADIUS:
                return s - 1
    return t


# ---------------------------------------------------------------- chute/goleiro
def in_shot_zone(px, py):
    gy = min(GOAL_MAX_Y, max(GOAL_MIN_Y, py))
    return math.hypot(GOAL_X - px, gy - py) <= DANGEROUS_SHOT_RANGE


def keeper_folga(px, py, gk):
    """Maior folga (turnos) sobre alvos na boca do gol: keeper_time - ball_time.
    >0 => existe mira que o goleiro nao alcanca a tempo."""
    _, gky = gk
    best = -math.inf
    for ty in GOAL_YS:
        d = math.hypot(GOAL_X - px, ty - py)
        if ball_range(400) < d:
            continue
        t_ball = turns_for_ball(400, d)
        if t_ball == math.inf:
            continue
        t_keeper = max(0.0, abs(ty - gky) - GOALKEEPER_HALF_EXTENT) / PLAYER_SPEED
        best = max(best, t_keeper - t_ball)
    return best


# ---------------------------------------------------------------- por snapshot
def analyze_snapshot(gs, turnmap):
    turn0 = gs.get("turn", 0)
    bx, by = R.ball_pos(gs)
    opps = opp_positions(gs)
    d_near = nearest_opp(gs)
    gk = keeper_pos(gs)
    units = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in DIRS]

    rows = {}
    for t in HORIZONS:
        n_safe_wc = 0
        n_safe_real = 0
        area = 0.0
        reach_zone = False
        best_zone_folga = -math.inf
        for (dx, dy) in units:
            s_wc = safe_radius_worstcase(bx, by, dx, dy, t, opps)
            s_rl = safe_radius_real(bx, by, dx, dy, t, turnmap, turn0)
            if s_wc == t:
                n_safe_wc += 1
            if s_rl == t:
                n_safe_real += 1
            r = STEP * s_wc                          # raio seguro pior-caso
            area += 0.5 * DTHETA * r * r
            # endpoint seguro (pior-caso) mais distante nesta direcao
            ex, ey = bx + dx * r, by + dy * r
            if s_wc > 0 and in_shot_zone(ex, ey):
                reach_zone = True
                best_zone_folga = max(best_zone_folga, keeper_folga(ex, ey, gk))
        # area do disco ideal (irrestrito) = pi*(100t)^2; a fracao mostra o
        # encolhimento em AREA (1.0 = todo o disco alcancavel e' seguro).
        ideal = math.pi * (STEP * t) ** 2
        rows[t] = dict(
            frac_wc=n_safe_wc / NDIR,
            frac_real=n_safe_real / NDIR,
            area=area,
            area_frac=area / ideal if ideal else 0.0,
            reach_zone=reach_zone,
            folga=(None if best_zone_folga == -math.inf else best_zone_folga),
        )
    return turn0, (bx, by), d_near, rows


def nearest_opp(gs):
    bx, by = R.ball_pos(gs)
    return min((math.hypot(bx - ox, by - oy) for (ox, oy) in opp_positions(gs)),
              default=math.inf)


# Portador precisa de ESPACO para o encolhimento ser visivel: se um adversario ja
# esta colado (<=~500), TODAS as direcoes falham no passo 1 (100+300=400 de alcance)
# e o conjunto ja nasce vazio (pior-caso == real == 0). Filtramos esses e mantemos
# apenas snapshots com folga inicial, ainda bem espacados no jogo.
MIN_ROOM = 500


def pick_snapshots(turnmap, n=5, need_future=max(HORIZONS)):
    home_turns = sorted(
        tn for tn, gs in turnmap.items()
        if (R.holder(gs) or ("", 0))[0] == "HOME"
        and (tn + need_future) in turnmap
        and nearest_opp(gs) > MIN_ROOM
    )
    if len(home_turns) <= n:
        return home_turns
    # bem espacados no jogo: percentis 10,30,50,70,90 do tempo
    idxs = [int((i + 0.5) / n * len(home_turns)) for i in range(n)]
    return [home_turns[i] for i in idxs]


def main():
    turnmap = load_turnmap(REPLAY)
    turns = pick_snapshots(turnmap)
    print(f"Replay: {REPLAY}")
    print(f"Turnos escolhidos (holder=HOME): {turns}\n")

    results = []
    for tn in turns:
        results.append(analyze_snapshot(turnmap[tn], turnmap))

    # tabela
    hdr = (f"{'snap(turn)':>11} | {'ball(x,y)':>13} | {'opp+':>5} | {'t':>2} | "
           f"{'frac_seg_PIORCASO':>17} | {'frac_seg_REAL':>13} | "
           f"{'area%disco':>10} | {'chuta?':>16}")
    print(hdr)
    print("-" * len(hdr))
    for turn0, (bx, by), d_near, rows in results:
        for i, t in enumerate(HORIZONS):
            r = rows[t]
            if r["reach_zone"]:
                if r["folga"] is not None and r["folga"] > 0:
                    ch = f"SIM folga+{r['folga']:.1f}"
                elif r["folga"] is not None:
                    ch = f"zona folga{r['folga']:.1f}"
                else:
                    ch = "zona s/mira"
            else:
                ch = "nao"
            first = (f"{turn0:>11} | ({bx:>5.0f},{by:>5.0f}) | {d_near:>5.0f} "
                     if i == 0 else f"{'':>11} | {'':>13} | {'':>5} ")
            print(f"{first}| {t:>2} | {r['frac_wc']*100:>15.0f}% | "
                  f"{r['frac_real']*100:>11.0f}% | {r['area_frac']*100:>9.0f}% | {ch:>16}")
        print("-" * len(hdr))

    # resumo agregado por horizonte
    print("\nMEDIAS por horizonte (sobre os 5 snapshots):")
    print(f"{'t':>3} | {'frac_seg_PIORCASO':>17} | {'frac_seg_REAL':>13} | {'gap(real-pior)':>14}")
    for t in HORIZONS:
        wc = sum(r[3][t]["frac_wc"] for r in results) / len(results)
        rl = sum(r[3][t]["frac_real"] for r in results) / len(results)
        print(f"{t:>3} | {wc*100:>15.0f}% | {rl*100:>11.0f}% | {(rl-wc)*100:>12.0f}pp")


if __name__ == "__main__":
    main()
