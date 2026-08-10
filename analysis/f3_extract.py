"""
FRENTE 3 - extracao: converte cada replay num npz com series por TURNO.

Um snapshot por turno (o ultimo visto para aquele numero de turno).
Tudo normalizado depois; aqui gravamos cru.
"""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import replay as R  # noqa: E402

REC = os.path.join(os.path.dirname(HERE), "bench", "recordings")
OUT = "<cache local>"

FILES = [
    "dummies_vs_dummies.json",
    "t1.json",
    "eval_0_norm.json",
    "var_1.json",
    "var_2.json",
    "swap.json",
    "v6_check.json",
    "smoke_rival.json",
    "p_rival_p2_home_1.json",
]


def vel(v):
    v = v or {}
    d = v.get("direction", {}) or {}
    dx, dy = d.get("x", 0.0), d.get("y", 0.0)
    n = (dx * dx + dy * dy) ** 0.5
    if n > 0:
        dx, dy = dx / n, dy / n
    return dx, dy, v.get("speed", 0.0)


def extract(path):
    cfg, events = R.load(path)
    rows = {}
    for gs in R.snapshots(events):
        t = gs.get("turn", 0)
        rows[t] = gs  # ultimo snapshot do turno
    turns = sorted(rows)
    n = len(turns)

    bx = np.zeros(n); by = np.zeros(n)
    bdx = np.zeros(n); bdy = np.zeros(n); bsp = np.zeros(n)
    hold_side = np.full(n, -1, np.int8)   # -1 solta, 0 home, 1 away
    hold_num = np.zeros(n, np.int8)
    sh = np.zeros(n, np.int16); sa = np.zeros(n, np.int16)
    px = np.zeros((n, 2, 11)); py = np.zeros((n, 2, 11))
    pnum = np.zeros((n, 2, 11), np.int8)
    sc_side = np.full(n, -1, np.int8); sc_rem = np.zeros(n, np.int16)

    for i, t in enumerate(turns):
        gs = rows[t]
        bx[i], by[i] = R.ball_pos(gs)
        bdx[i], bdy[i], bsp[i] = vel(R.ball(gs).get("velocity"))
        h = R.holder(gs)
        if h:
            hold_side[i] = 0 if h[0] == "HOME" else 1
            hold_num[i] = h[1]
        sh[i], sa[i] = R.score(gs, "home"), R.score(gs, "away")
        for s, side in enumerate(("home", "away")):
            for j, p in enumerate(R.players(gs, side)[:11]):
                px[i, s, j], py[i, s, j] = R.pt(p.get("position"))
                pnum[i, s, j] = p.get("number", 0)
        sc = gs.get("shot_clock") or {}
        if sc:
            sc_side[i] = 0 if sc.get("team_side", "HOME") == "HOME" else 1
            sc_rem[i] = sc.get("remaining_turns", 0)

    name = os.path.basename(path).replace(".json", "")
    np.savez_compressed(
        os.path.join(OUT, name + ".npz"),
        turn=np.array(turns), bx=bx, by=by, bdx=bdx, bdy=bdy, bsp=bsp,
        hold_side=hold_side, hold_num=hold_num, sh=sh, sa=sa,
        px=px, py=py, pnum=pnum, sc_side=sc_side, sc_rem=sc_rem,
    )
    print(f"{name:34s} turnos={n:5d} placar {sh[-1]}x{sa[-1]}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in FILES:
        extract(os.path.join(REC, f))
