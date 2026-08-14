#!/usr/bin/env python3
"""Extrai um replay do servidor Lugo para JSON compacto (1 estado por turno),
para o viewer HTML. Cada frame e um array (len 51):
  [t, bx, by, hside, hnum, sh, sa, HX(11), HY(11), AX(11), AY(11)]
hside: 0=home, 1=away, -1=bola solta. Slots 0..10 -> meta.home_nums/away_nums.
Uso: replay_to_json.py recordings/x.json out.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "analysis"))
import replay as R  # noqa: E402


def main():
    src, out = sys.argv[1], sys.argv[2]
    cfg, events = R.load(src)
    by_turn = {}
    for gs in R.snapshots(events):
        t = gs.get("turn", 0)
        if gs.get("state") == "LISTENING" or t not in by_turn:
            by_turn[t] = gs
    turns = sorted(by_turn)

    def nums(side):
        for t in turns:
            ns = sorted(p.get("number", 0) for p in R.players(by_turn[t], side))
            if len(ns) == 11:
                return ns
        return list(range(1, 12))

    hn, an = nums("home"), nums("away")
    hidx = {n: i for i, n in enumerate(hn)}
    aidx = {n: i for i, n in enumerate(an)}

    frames = []
    for t in turns:
        gs = by_turn[t]
        bx, by = R.ball_pos(gs)
        hold = R.holder(gs)
        hs, hnum = -1, 0
        if hold:
            hs, hnum = (1 if hold[0] == "AWAY" else 0), hold[1]
        HX = [-1] * 11; HY = [-1] * 11; AX = [-1] * 11; AY = [-1] * 11
        for p in R.players(gs, "home"):
            i = hidx.get(p.get("number", 0))
            if i is not None:
                x, y = R.pt(p.get("position")); HX[i] = int(x); HY[i] = int(y)
        for p in R.players(gs, "away"):
            i = aidx.get(p.get("number", 0))
            if i is not None:
                x, y = R.pt(p.get("position")); AX[i] = int(x); AY[i] = int(y)
        frames.append([t, int(bx), int(by), hs, hnum,
                       R.score(gs, "home"), R.score(gs, "away")]
                      + HX + HY + AX + AY)

    data = {"meta": {"src": os.path.basename(src), "turns": len(frames),
                     "field": [20000, 10000], "goalY": [3500, 6500],
                     "home_nums": hn, "away_nums": an,
                     "duration": cfg.get("game_duration")},
            "frames": frames}
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"frames={len(frames)} out={out} size={os.path.getsize(out)}")


if __name__ == "__main__":
    main()
