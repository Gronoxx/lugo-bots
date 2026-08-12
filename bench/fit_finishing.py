#!/usr/bin/env python3
"""Ajusta o modelo de finalizacao (xG) nos replays FRESCOS vs level-1 (amd64) e
SERIALIZA os coeficientes para o bot usar.

Por que refazer: o modelo antigo foi treinado vs the-dummies no Mac (arm64) e as
medicoes nao sao portaveis arm64<->amd64; o alvo agora e level-1. Os replays-fonte
antigos tambem sumiram. Entao regeneramos os chutes rotulados aqui (ver
gen_shot_data.sh) e refitamos.

Modelo: logistica de 4 features (metrics_lab.xg_features):
  [dist_line/1000, v_arr/100, min(gk,3000)/1000, |ycross-5000|/1000]
Deteccao de chute e rotulo de gol: metrics_lab.mark_shots (chute on-goal;
gol = ultimo chute <=80 turnos antes do placar subir).

Uso: python3 bench/fit_finishing.py            # le recordings/fin_*.json
Saida: bot/src/finishing_model.json (intercepto + 4 pesos) + AUC honesto.
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import replay as R          # noqa: E402
import metrics_lab as M     # noqa: E402


def build_d(path):
    """Replay -> dict de arrays por turno (copia da logica de extract_series,
    lendo direto do arquivo e devolvendo em memoria)."""
    cfg, ev = R.load(path)
    snaps = [e["game_snapshot"] for e in ev if "game_snapshot" in e]
    by_turn, score_by_turn = {}, {}
    for s in snaps:
        t = s.get("turn", 0)
        h, a = R.score(s, "home"), R.score(s, "away")
        prev = score_by_turn.get(t, (0, 0))
        score_by_turn[t] = (max(prev[0], h), max(prev[1], a))
        if s.get("state") == "LISTENING" or t not in by_turn:
            by_turn[t] = s
    turns = sorted(by_turn)
    n = len(turns)
    out = {
        "turn": np.zeros(n, np.int32),
        "bx": np.zeros(n, np.float32), "by": np.zeros(n, np.float32),
        "bspeed": np.zeros(n, np.float32),
        "bdx": np.zeros(n, np.float32), "bdy": np.zeros(n, np.float32),
        "hold_side": np.zeros(n, np.int8), "hold_num": np.zeros(n, np.int8),
        "sc_home": np.zeros(n, np.int16), "sc_away": np.zeros(n, np.int16),
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
        dirn = vel.get("direction") or {}
        out["bdx"][i], out["bdy"][i] = dirn.get("x", 0), dirn.get("y", 0)
        hold = R.holder(s)
        if hold is None:
            out["hold_side"][i] = -1
        else:
            out["hold_side"][i] = 1 if hold[0] == "AWAY" else 0
            out["hold_num"][i] = hold[1]
        h, a = score_by_turn[t]
        out["sc_home"][i], out["sc_away"][i] = h, a
        for side, kx, ky, kn in (("home", "hx", "hy", "hnum"),
                                 ("away", "ax", "ay", "anum")):
            for j, p in enumerate(R.players(s, side)[:11]):
                px, py = R.pt(p.get("position"))
                out[kx][i, j], out[ky][i, j] = px, py
                out[kn][i, j] = p.get("number", 0)
    return out


def auc(y, p):
    pos = p[y == 1]
    neg = p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    diff = pos[:, None] - neg[None, :]
    return float((np.sum(diff > 0) + 0.5 * np.sum(diff == 0)) / (len(pos) * len(neg)))


def main():
    files = sorted(glob.glob(os.path.join(HERE, "recordings", "fin_*.json")))
    if not files:
        print("NENHUM recordings/fin_*.json — rode gen_shot_data.sh primeiro.")
        return
    X_all, y_all, match_all = [], [], []
    n_shots = 0
    for mi, path in enumerate(files):
        name = os.path.basename(path)
        our_side = "away" if "_away" in name else "home"
        try:
            d = build_d(path)
        except Exception as e:
            print(f"  {name}: erro ao ler ({e})", file=sys.stderr)
            continue
        ev, gts = M.mark_shots(d, our_side)
        shots = [e for e in ev if e.get("on_goal")]
        if not shots:
            continue
        Xs = M.xg_features(shots)
        ys = np.array([e["goal"] for e in shots], float)
        X_all.append(Xs)
        y_all.append(ys)
        match_all.append(np.full(len(shots), mi))
        n_shots += len(shots)
    if not X_all:
        print("NENHUM chute detectado nos replays.")
        return
    X = np.vstack(X_all)
    y = np.concatenate(y_all)
    match = np.concatenate(match_all)
    print(f"{len(files)} replays, {n_shots} chutes ao gol, {int(y.sum())} gols "
          f"(taxa {y.mean():.1%})")

    # fit em tudo + AUC in-sample
    w = M.fit_logistic(X, y)
    p_in = M.xg_predict(w, X)
    auc_in = auc(y, p_in)

    # leave-one-match-out (honesto)
    p_loo = np.zeros(len(y))
    for mi in np.unique(match):
        tr = match != mi
        te = match == mi
        if tr.sum() < 5 or te.sum() == 0:
            p_loo[te] = y[tr].mean() if tr.sum() else 0.5
            continue
        w_tr = M.fit_logistic(X[tr], y[tr])
        p_loo[te] = M.xg_predict(w_tr, X[te])
    auc_loo = auc(y, p_loo)

    print(f"AUC in-sample = {auc_in:.3f}")
    print(f"AUC leave-one-match-out (HONESTO) = {auc_loo:.3f}")
    print("pesos [intercepto, dist/1k, v_arr/100, gk/1k, lat/1k] =",
          [round(float(x), 4) for x in w])

    out = {
        "features": ["dist_line/1000", "v_arr/100", "min(gk,3000)/1000",
                     "abs(ycross-5000)/1000"],
        "weights": [float(x) for x in w],  # [intercepto, ...4]
        "auc_in_sample": round(auc_in, 3),
        "auc_loo": round(auc_loo, 3),
        "n_shots": int(n_shots), "n_goals": int(y.sum()),
        "opp": "lugobots/level-1", "arch": "amd64",
    }
    dest = os.path.join(ROOT, "bot", "src", "finishing_model.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"modelo salvo em {dest}")


if __name__ == "__main__":
    main()
