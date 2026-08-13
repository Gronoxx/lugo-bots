"""
Smoke test da ponte: roda o my_bot EXATO dentro do fastsim (sem gRPC/Docker).
Suprime o stderr do bot (as callbacks fazem traceback.print_exc em erro).

  ../.venv/bin/python rl/bridge/smoke_test.py [turnos]
"""
import contextlib
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "sim"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fastsim as fs
import policies as pol
from heuristic_policy import make_heuristic_policy


def quiet_play(a, b, turns):
    with open(os.devnull, "w") as dn, \
            contextlib.redirect_stdout(dn), contextlib.redirect_stderr(dn):
        return fs.play(a, b, turns=turns)


if __name__ == "__main__":
    turns = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
    mybot = make_heuristic_policy()
    for name, ph, pa in (("my_bot(H) vs dummy(A)", mybot, pol.dummy_policy),
                         ("dummy(H) vs my_bot(A)", pol.dummy_policy, mybot),
                         ("my_bot vs my_bot", mybot, mybot)):
        t = time.time()
        s = quiet_play(ph, pa, turns)
        dt = time.time() - t
        print(f"{name:24} {turns}t -> {s.score}  ({dt:.2f}s, {turns/dt:.0f} turnos/s)")
