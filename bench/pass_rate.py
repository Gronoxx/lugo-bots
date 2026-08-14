#!/usr/bin/env python3
"""Taxa de acerto de passe do NOSSO bot a partir de replays.

Reusa a deteccao de passe de analysis/frente2c_gate.run (mesma definicao de
"chegou a um companheiro" x "foi para o adversario"), sem depender da lista
MATCHES hardcoded — aceita replays arbitrarios.

Uso:
  pass_rate.py HOME recordings/off_home_1.json recordings/off_home_2.json ...
  pass_rate.py AWAY recordings/off_away_*.json

Imprime, agregado sobre os replays dados:
  passes tentados, chegaram a companheiro (ok), foram ao adversario (adv),
  taxa ok/npass e taxa resolvida ok/(ok+adv).
"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "analysis"))
import frente2c_gate as G  # noqa: E402


def measure(side, paths):
    tot_np = tot_ok = tot_bad = 0
    per = []
    for p in paths:
        if not os.path.exists(p):
            print(f"  (faltando) {p}", file=sys.stderr)
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            r = G.run(p, side, os.path.basename(p))
        tot_np += r["npass"]
        tot_ok += r["okp"]
        tot_bad += r["badp"]
        per.append((os.path.basename(p), r["npass"], r["okp"], r["badp"]))
    return tot_np, tot_ok, tot_bad, per


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    side = sys.argv[1].upper()
    paths = sys.argv[2:]
    tot_np, tot_ok, tot_bad, per = measure(side, paths)
    for name, np_, ok, bad in per:
        print(f"  {name:<44} passes={np_:>4} ok={ok:>4} adv={bad:>4}")
    resolved = tot_ok + tot_bad
    print(f"TOTAL side={side}  replays={len(per)}  passes={tot_np}  "
          f"ok={tot_ok}  adv={tot_bad}")
    if tot_np:
        print(f"  chegou_a_companheiro = {100.0*tot_ok/tot_np:.1f}%  (ok/npass)")
    if resolved:
        print(f"  acerto_resolvido     = {100.0*tot_ok/resolved:.1f}%  (ok/(ok+adv))")


if __name__ == "__main__":
    main()
