"""
Coleta dados de behavior cloning do v9: roda o my_bot no sim escalar (via ponte)
e grava, por turno, os campos do State + a AÇÃO discreta do v9 (no espaço de
ação do env, referencial canônico). Roda no .venv (3.14, tem a ponte).

  ../.venv/bin/python rl/train/collect_bc.py <n_matches> <out.npz>

Depois, rl/train/bc_train.py (no .venv-rl) carrega e treina o ator por imitação.
"""
import contextlib
import math
import os
import sys
from pathlib import Path

import numpy as np

_R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_R / "rl/bridge"))
sys.path.insert(0, str(_R / "sim"))

import fastsim as fs
from heuristic_policy import make_heuristic_policy

N_DIR = 16
_TWO_PI = 2 * math.pi


def _dir_bin(vec, mirror_x):
    if vec is None:
        return 0
    vx, vy = float(vec[0]), float(vec[1])
    if mirror_x:
        vx = -vx
    if math.hypot(vx, vy) < 1e-6:
        return 0
    ang = math.atan2(vy, vx) % _TWO_PI
    return int(round(ang / (_TWO_PI / N_DIR))) % N_DIR + 1


def _dict_to_action(d, side):
    if d is None:
        return (0, 0, 0, 0)
    mirror = (side == fs.AWAY)
    return (_dir_bin(d.get("move"), mirror), _dir_bin(d.get("kick"), mirror),
            1 if d.get("catch") else 0, 1 if d.get("jump") else 0)


def collect(n_matches, out, turns=6000):
    pol = make_heuristic_policy()
    S = {k: [] for k in ("pos", "vel", "ball_pos", "ball_vel", "holder_side",
                         "holder_idx", "score", "shot_clock_side", "shot_clock",
                         "jump_left", "goal_zone_turns", "action")}
    for m in range(n_matches):
        s = fs.initial_state()
        for t in range(turns):
            with open(os.devnull, "w") as dn, contextlib.redirect_stderr(dn), \
                    contextlib.redirect_stdout(dn):
                oh = pol(s, fs.HOME)
                oa = pol(s, fs.AWAY)
            act = np.zeros((2, 11, 4), np.int32)
            for i in range(11):
                act[fs.HOME, i] = _dict_to_action(oh[i], fs.HOME)
                act[fs.AWAY, i] = _dict_to_action(oa[i], fs.AWAY)
            hs, hi = (s.holder if s.holder is not None else (-1, 0))
            S["pos"].append(s.pos.copy()); S["vel"].append(s.vel.copy())
            S["ball_pos"].append(s.ball_pos.copy()); S["ball_vel"].append(s.ball_vel.copy())
            S["holder_side"].append(hs); S["holder_idx"].append(hi)
            S["score"].append(list(s.score)); S["shot_clock_side"].append(s.shot_clock_side)
            S["shot_clock"].append(s.shot_clock); S["jump_left"].append(s.jump_left.copy())
            S["goal_zone_turns"].append(s.turns_ball_in_goal_zone); S["action"].append(act)
            s = fs.step(s, oh, oa)
        print(f"  match {m+1}/{n_matches} coletado ({turns} turnos)", flush=True)
    arrs = {k: np.array(v) for k, v in S.items()}
    np.savez_compressed(out, **arrs)
    print(f"salvo {out}: {arrs['action'].shape[0]} turnos, "
          f"{arrs['action'].shape[0]*22} amostras/agente")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    out = sys.argv[2] if len(sys.argv) > 2 else str(_R / "rl/checkpoints/bc_data.npz")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    collect(n, out)
