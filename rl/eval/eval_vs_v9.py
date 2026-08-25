"""
Joga a política RL CONTRA o my_bot (v9) no fastsim escalar (em processo) e reporta
o placar médio. Dois blocos: RL como HOME e como AWAY (elimina viés de lado).

  JAX_PLATFORMS=cpu ../.venv-rl/bin/python rl/eval/eval_vs_v9.py <policy.pkl> [n] [turns]
"""
import sys
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in ("rl/eval", "rl/bridge", "sim", "bot/src", "rl/envs", "rl/jax", "rl/train"):
    p = str(_R / _p)
    if p not in sys.path:
        sys.path.insert(0, p)

import fastsim as fs
from fastsim_policy import make_net_fastsim_policy
from heuristic_policy import make_heuristic_policy

# --- workaround: o safe_move do GOLEIRO do my_bot faz geo.new_vector(p, p) (alvo ==
# posição) em estados incomuns -> "vector cannot have zero length". Só no processo de
# EVAL, guardamos o caso zero (nudge desprezível). NÃO altera o bot real. ---
from lugo4py.src import geo as _geo
from lugo4py.protos import physics_pb2 as _pb


def _safe_new_vector(from_point, to_point):
    v = _pb.Vector()
    v.x = to_point.x - from_point.x
    v.y = to_point.y - from_point.y
    if _geo.is_invalid_vector(v):
        v.x, v.y = 0.0, 1.0
    return v


_geo.new_vector = _safe_new_vector


def main(rl_path, n=6, turns=6000):
    rl = make_net_fastsim_policy(rl_path)
    v9 = make_heuristic_policy()
    import time
    gh = ga = 0.0
    for m in range(n):
        t = time.time()
        s = fs.play(rl, v9, turns=turns)
        gh += s.score[0]; ga += s.score[1]
        print(f"  [RL-home {m+1}/{n}] {s.score[0]}x{s.score[1]}  ({time.time()-t:.0f}s)", flush=True)
    print(f"RL(HOME) {gh/n:.2f} x {ga/n:.2f} v9(AWAY)", flush=True)
    gh2 = ga2 = 0.0
    for m in range(n):
        s = fs.play(v9, rl, turns=turns)
        gh2 += s.score[0]; ga2 += s.score[1]
        print(f"  [RL-away {m+1}/{n}] {s.score[0]}x{s.score[1]}", flush=True)
    print(f"v9(HOME) {gh2/n:.2f} x {ga2/n:.2f} RL(AWAY)", flush=True)
    rl_g = gh / n + ga2 / n
    v9_g = ga / n + gh2 / n
    print(f"=> RL {rl_g:.2f} x {v9_g:.2f} v9  | saldo RL {rl_g - v9_g:+.2f}  (n={n}x2, {turns}t)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6,
         int(sys.argv[3]) if len(sys.argv) > 3 else 6000)
