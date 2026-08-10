"""
Extrai de cada replay uma serie temporal compacta (1 registro por turno) e
salva em .npz, para que as analises de metrica rodem em segundos.

Uso: python extract_series.py            # extrai todos os replays grandes
     python extract_series.py var_1      # so um
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay as R

REC = "./bench/recordings"
CACHE = "<cache local>"

FILES = [
    "dummies_vs_dummies", "t1", "eval_0_norm", "var_1", "var_2",
    "swap", "v6_check", "smoke_rival", "p_rival_p2_home_1",
]


def extract(name):
    path = os.path.join(REC, name + ".json")
    cfg, ev = R.load(path)
    snaps = [e["game_snapshot"] for e in ev if "game_snapshot" in e]
    # 1 registro por turno: usamos o snapshot LISTENING (estado que o bot ve).
    by_turn = {}
    score_by_turn = {}
    for s in snaps:
        t = s.get("turn", 0)
        st = s.get("state")
        h, a = R.score(s, "home"), R.score(s, "away")
        prev = score_by_turn.get(t, (0, 0))
        score_by_turn[t] = (max(prev[0], h), max(prev[1], a))
        if st == "LISTENING" or t not in by_turn:
            by_turn[t] = s
    turns = sorted(by_turn)
    n = len(turns)

    out = {
        "turn": np.zeros(n, np.int32),
        "bx": np.zeros(n, np.float32), "by": np.zeros(n, np.float32),
        "bspeed": np.zeros(n, np.float32),
        "bdx": np.zeros(n, np.float32), "bdy": np.zeros(n, np.float32),
        "hold_side": np.zeros(n, np.int8),   # -1 solta, 0 home, 1 away
        "hold_num": np.zeros(n, np.int8),
        "sc_home": np.zeros(n, np.int16), "sc_away": np.zeros(n, np.int16),
        "shot_rem": np.zeros(n, np.int16), "shot_side": np.zeros(n, np.int8),
        "hx": np.zeros((n, 11), np.float32), "hy": np.zeros((n, 11), np.float32),
        "ax": np.zeros((n, 11), np.float32), "ay": np.zeros((n, 11), np.float32),
        "hnum": np.zeros((n, 11), np.int8), "anum": np.zeros((n, 11), np.int8),
    }
    for i, t in enumerate(turns):
        s = by_turn[t]
        out["turn"][i] = t
        bx, by = R.ball_pos(s)
        out["bx"][i], out["by"][i] = bx, by
        vel = (R.ball(s).get("velocity") or {})
        out["bspeed"][i] = vel.get("speed", 0)
        d = vel.get("direction") or {}
        out["bdx"][i], out["bdy"][i] = d.get("x", 0), d.get("y", 0)
        hold = R.holder(s)
        if hold is None:
            out["hold_side"][i] = -1
        else:
            out["hold_side"][i] = 1 if hold[0] == "AWAY" else 0
            out["hold_num"][i] = hold[1]
        h, a = score_by_turn[t]
        out["sc_home"][i], out["sc_away"][i] = h, a
        sc = s.get("shot_clock") or {}
        out["shot_rem"][i] = sc.get("remaining_turns", 0)
        out["shot_side"][i] = 1 if sc.get("team_side") == "AWAY" else 0
        for side, kx, ky, kn in (("home", "hx", "hy", "hnum"),
                                 ("away", "ax", "ay", "anum")):
            for j, p in enumerate(R.players(s, side)[:11]):
                px, py = R.pt(p.get("position"))
                out[kx][i, j], out[ky][i, j] = px, py
                out[kn][i, j] = p.get("number", 0)
    os.makedirs(CACHE, exist_ok=True)
    np.savez_compressed(os.path.join(CACHE, name + ".npz"), **out)
    print(f"{name}: {n} turnos, placar {out['sc_home'][-1]}x{out['sc_away'][-1]}")


if __name__ == "__main__":
    names = sys.argv[1:] or FILES
    for nm in names:
        extract(nm)
