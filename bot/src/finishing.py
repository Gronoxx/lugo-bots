"""Modelo de finalizacao (xG): logistica de 4 features, treinada em replays
FRESCOS vs level-1 no amd64 (ver bench/fit_finishing.py; AUC leave-one-match-out
~0,81). Auto-contido para o Docker do bot (NAO importa de analysis/, que nao
esta na imagem). Se o JSON faltar, xg() devolve None e o bot cai no gate por
limiar (shot_gate=threshold).

Features (mesmas do treino, metrics_lab.xg_features):
  [dist_line/1000, v_arr/100, min(gk,3000)/1000, |ycross-5000|/1000]
"""
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_W = None  # [intercepto, w_dist, w_varr, w_gk, w_lat]

try:
    _m = json.load(open(os.path.join(_HERE, "finishing_model.json")))
    _W = _m.get("weights")
    if not _W or len(_W) != 5:
        _W = None
except Exception:
    _W = None


def available():
    return _W is not None


def arrival_speed(v, d):
    """Velocidade da bola ao percorrer a distancia d (0 se nao chega)."""
    s2 = v * v - 20.0 * d
    return math.sqrt(s2) if s2 > 0 else 0.0


def xg(dist_line, v_arr, gk, lat):
    """P(gol) do modelo. gk = folga perpendicular do goleiro a reta do chute."""
    if _W is None:
        return None
    if gk != gk:  # NaN
        gk = 600.0
    f = (dist_line / 1000.0, v_arr / 100.0, min(gk, 3000.0) / 1000.0, lat / 1000.0)
    z = _W[0] + _W[1] * f[0] + _W[2] * f[1] + _W[3] * f[2] + _W[4] * f[3]
    z = max(-60.0, min(60.0, z))
    return 1.0 / (1.0 + math.exp(-z))
