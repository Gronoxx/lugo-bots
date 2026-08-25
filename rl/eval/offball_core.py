"""
Extrator do MOVIMENTO sem-bola da política RL treinada, para plugar como o gene
`offball` sobre o v9. A rede decide TODA a movimentação; aqui usamos SÓ a cabeça
de movimento (move_dir) dos jogadores SEM a bola — o v9 mantém on-ball, goleiro,
defesa e finalização.

  movement_targets(params, state, key) -> (B, 2, 11, 2)  alvos ABSOLUTOS de mov.

O alvo é `pos_jogador + unit(move_dir) * MOVE_DIST` no referencial ABSOLUTO
(des-canonizado: o x do AWAY é espelhado). Núcleo puro-JAX/numpy, testável no
fastsim/JAX; o wrapper de servidor (inspector->J.State) reusa deploy_policy.
"""
import math
import sys
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in (_R / "rl/envs", _R / "rl/jax", _R / "rl/train"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp
import numpy as np

import step as J
from obs import get_obs
from networks import Actor, sample_action

_actor = Actor(nvec=(17, 17, 2, 2))
N_DIR = 16
_UNIT = jnp.array([[math.cos(2 * math.pi * k / N_DIR), math.sin(2 * math.pi * k / N_DIR)]
                   for k in range(N_DIR)])                       # (16,2)
MOVE_DIST = 800.0                                               # quão longe projetar o alvo
_SIGN = jnp.array([1.0, -1.0]).reshape(1, 2, 1)                 # des-canoniza x do AWAY


@jax.jit
def movement_targets(params, state, key):
    """(B,2,11,2) alvos absolutos de movimento (amostrados) para os 22 jogadores."""
    aobs, _ = get_obs(state)                                    # (B,2,11,109)
    B = aobs.shape[0]
    kH, kA = jax.random.split(key)
    aH, _ = sample_action(_actor.apply(params, aobs[:, J.HOME]), kH)   # (B,11,4)
    aA, _ = sample_action(_actor.apply(params, aobs[:, J.AWAY]), kA)
    md = jnp.stack([aH[..., 0], aA[..., 0]], axis=1)            # (B,2,11) move_dir 0..16
    unit = _UNIT[jnp.clip(md - 1, 0, N_DIR - 1)]               # (B,2,11,2) canônico
    ux = unit[..., 0] * _SIGN                                  # (B,2,11) espelha x do AWAY
    unit = jnp.stack([ux, unit[..., 1]], axis=-1)              # (B,2,11,2) absoluto
    moving = (md > 0)[..., None].astype(jnp.float32)
    tgt = state.pos + unit * MOVE_DIST * moving                 # (B,2,11,2); parado => própria pos
    tgt = jnp.stack([jnp.clip(tgt[..., 0], 0.0, J.MAX_X),
                     jnp.clip(tgt[..., 1], 0.0, J.MAX_Y)], -1)
    return tgt
