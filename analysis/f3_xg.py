"""FRENTE 3 - modelo xG: logistica ajustada por IRLS sobre os chutes do corpus."""
import numpy as np
from f3_metrics import Match, travel, FX, GOAL_C, GOAL_LO, GOAL_HI


def logistic_fit(X, y, l2=1.0, iters=60):
    """IRLS com regularizacao L2 (nao penaliza o intercepto)."""
    X = np.asarray(X, float)
    n, p = X.shape
    A = np.hstack([np.ones((n, 1)), X])
    w = np.zeros(p + 1)
    P = np.eye(p + 1) * l2
    P[0, 0] = 0.0
    for _ in range(iters):
        z = A @ w
        mu = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        s = np.clip(mu * (1 - mu), 1e-6, None)
        g = A.T @ (y - mu) - P @ w
        H = A.T @ (A * s[:, None]) + P
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w = w + step
        if np.max(np.abs(step)) < 1e-9:
            break
    return w


def predict(w, X):
    A = np.hstack([np.ones((len(X), 1)), np.asarray(X, float)])
    return 1.0 / (1.0 + np.exp(-np.clip(A @ w, -30, 30)))


def shot_features(k):
    """Vetor de features de UM chute nosso.
    dist/1000, |y_cross-5000|/1000 saturado, folga do goleiro/1000,
    alcanca a linha?, velocidade/100."""
    dist = k["dist"] / 1000.0
    reach = 1.0 if travel(k["v"]) >= k["dist"] else 0.0
    yc = k["y_cross"]
    if np.isfinite(yc):
        # quanto a mira entra no gol: 1 no centro, 0 fora
        miss = max(0.0, abs(yc - GOAL_C) - (GOAL_HI - GOAL_C)) / 1000.0
        inside = max(0.0, (GOAL_HI - GOAL_C) - abs(yc - GOAL_C)) / 1000.0
    else:
        miss, inside = 10.0, 0.0
    gk = k["gk_gap"]
    gk = 0.0 if not np.isfinite(gk) else min(gk, 3000.0) / 1000.0
    tt = k["t_arrive"]
    tt = 60.0 if not np.isfinite(tt) else min(tt, 60.0)
    return [dist, min(miss, 5.0), inside, gk, reach, k["v"] / 100.0, tt / 10.0]


FEAT_NAMES = ["dist/1k", "erro_mira/1k", "dentro_gol/1k", "folga_gk/1k",
              "alcanca", "v/100", "t_chegada/10"]


def collect_shots(cases, only_attempts=True):
    """Todos os chutes 'nossos' de uma lista de (nome, lado)."""
    rows, meta = [], []
    for name, side in cases:
        m = Match(name, side)
        for k in m.kicks():
            if not k["mine"]:
                continue
            if only_attempts and not is_attempt(k):
                continue
            rows.append(shot_features(k))
            meta.append((name, side, k))
    return np.array(rows), meta


def is_attempt(k):
    """Chute com intencao de gol: sai a <=8000d, aponta para a frente e a
    reta cruza a linha de fundo a menos de 3000d do centro do gol."""
    if k["dist"] > 8000:
        return False
    if k["dx"] <= 0.05:
        return False
    yc = k["y_cross"]
    if not np.isfinite(yc):
        return False
    return abs(yc - GOAL_C) < 4000
