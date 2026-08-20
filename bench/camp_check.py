#!/usr/bin/env python3
"""VERIFICA O ACAMPAMENTO: onde estão nossos corpos quando a bola está no
NOSSO campo? (portão anti-"gene que não dispara" — lição dos commits c10/c18).

Uso: python3 bench/camp_check.py <replay.json> <HOME|AWAY>
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, HERE)
import proxy_metric as PM   # noqa: E402


def report(path, our):
    d = PM.build_d(path)
    home = (our == "HOME")
    X = d["hx"] if home else d["ax"]
    NUM = d["hnum"] if home else d["anum"]
    bx = d["bx"].astype(float)
    prog_ball = bx if home else 20000.0 - bx
    sel = prog_ball < 10000.0            # bola no NOSSO campo
    n = int(sel.sum())
    out = {}
    for num in range(1, 12):
        col = np.argmax(NUM[0] == num) if (NUM[0] == num).any() else None
        if col is None:
            continue
        px = X[sel, col].astype(float)
        prog = px if home else 20000.0 - px
        out[num] = (float(prog.mean()), float(np.percentile(prog, 90)))
    return n, out


def main():
    for path, our in zip(sys.argv[1::2], sys.argv[2::2]):
        n, out = report(path, our)
        print(f"{os.path.basename(path)} ({our}) — {n} turnos com a bola no nosso campo")
        line = "  avanço médio por camisa: " + " ".join(
            f"#{k}={v[0]:5.0f}" for k, v in sorted(out.items()))
        print(line)
        fw = [out[k][0] for k in (9, 10, 11) if k in out]
        if fw:
            print(f"  ATACANTES (9/10/11): média {np.mean(fw):.0f} "
                  f"(0 = nosso gol, 20000 = gol deles)")


if __name__ == "__main__":
    main()
