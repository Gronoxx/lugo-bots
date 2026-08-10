"""
FRENTE 1 - extrator: converte cada replay num cache compacto (1 registro por turno).

Uso: python analysis/frente1_extract.py            (extrai todos)
Saída: <scratch>/f1_<nome>.pkl
"""
import math
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay  # noqa: E402

REC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "bench", "recordings")
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

# de que lado joga NOSSO bot em cada replay
OURS = {
    "dummies_vs_dummies.json": None,
    "t1.json": "home", "eval_0_norm.json": "home", "var_1.json": "home",
    "var_2.json": "home", "v6_check.json": "home",
    "swap.json": "away",
    "smoke_rival.json": "home", "p_rival_p2_home_1.json": "home",
}


def unit(d):
    x, y = d.get("x", 0.0), d.get("y", 0.0)
    m = math.hypot(x, y)
    return (x / m, y / m) if m > 1e-9 else (0.0, 0.0)


def extract(path):
    cfg, events = replay.load(path)
    rows = []
    seen = set()
    goal_turns = []
    for e in events:
        gs = e.get("game_snapshot")
        if not gs:
            continue
        t = gs.get("turn", 0)
        if "goal" in e:
            goal_turns.append(t)
        if t in seen:
            continue
        seen.add(t)
        b = replay.ball(gs)
        bd = unit((b.get("velocity", {}) or {}).get("direction", {}) or {})
        h = replay.holder(gs)
        row = {
            "turn": t,
            "ball": replay.ball_pos(gs),
            "bspeed": replay.ball_speed(gs),
            "bdir": bd,
            "holder": h,
            "home": {p.get("number", 0): replay.pt(p.get("position"))
                     for p in replay.players(gs, "home")},
            "away": {p.get("number", 0): replay.pt(p.get("position"))
                     for p in replay.players(gs, "away")},
            "sh": replay.score(gs, "home"),
            "sa": replay.score(gs, "away"),
        }
        rows.append(row)
    rows.sort(key=lambda r: r["turn"])
    return {"cfg": cfg, "rows": rows, "goal_turns": goal_turns}


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in FILES:
        p = os.path.join(REC, f)
        if not os.path.exists(p):
            print("MISSING", f)
            continue
        d = extract(p)
        d["file"] = f
        d["ours"] = OURS.get(f)
        with open(os.path.join(OUT, "f1_" + f.replace(".json", ".pkl")), "wb") as fh:
            pickle.dump(d, fh)
        r = d["rows"]
        print(f"{f:36s} turnos={len(r):5d} placar={r[-1]['sh']}x{r[-1]['sa']} "
              f"goal_events={len(d['goal_turns'])}")
