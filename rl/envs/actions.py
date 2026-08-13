"""
Espaço de ação (MultiDiscrete) e decodificação para as ordens de baixo nível que
o sim JAX (rl/jax/step.py) consome.

Ação por jogador = 4 inteiros: [move_dir, kick_dir, catch, jump]
  move_dir ∈ {0..16}  0 = parar; 1..16 = uma das 16 direções (a max speed)
  kick_dir ∈ {0..16}  0 = não chutar; 1..16 = direção do chute (a BALL_MAX_SPEED)
  catch    ∈ {0,1}
  jump     ∈ {0,1}    (só goleiro é honrado pelo sim)

As direções estão no referencial CANÔNICO de cada agente (sempre ataca +x). O
AWAY ataca -x no absoluto, então des-espelhamos a componente x das ordens dele.
"""
import jax.numpy as jnp

N_DIR = 16
NVEC = (N_DIR + 1, N_DIR + 1, 2, 2)   # MultiDiscrete por jogador

_ANG = jnp.arange(N_DIR) * (2 * jnp.pi / N_DIR)
_UNIT = jnp.stack([jnp.cos(_ANG), jnp.sin(_ANG)], axis=-1)   # (16,2)


def _dir_vec(idx, speed):
    """idx: (...,) int em {0..16}; 0 -> vetor nulo. Retorna (...,2)."""
    u = _UNIT[jnp.clip(idx - 1, 0, N_DIR - 1)]                # (...,2)
    return jnp.where((idx > 0)[..., None], u * speed, 0.0)


def decode(action):
    """action: (B,2,11,4) int -> (move, kick, do_catch, do_jump) para o sim.
    move,kick: (B,2,11,2) absolutos; do_catch,do_jump: (B,2,11) bool."""
    from step import PLAYER_MAX_SPEED, BALL_MAX_SPEED, HOME
    move = _dir_vec(action[..., 0], PLAYER_MAX_SPEED)         # (B,2,11,2) canônico
    kick = _dir_vec(action[..., 1], BALL_MAX_SPEED)
    do_catch = action[..., 2] > 0
    do_jump = action[..., 3] > 0
    # des-espelha o x do AWAY (side 1): canônico +x -> absoluto -x
    sign = jnp.array([1.0, -1.0]).reshape(1, 2, 1, 1)         # HOME +1, AWAY -1
    move = move * jnp.concatenate([sign, jnp.ones_like(sign)], axis=-1)
    kick = kick * jnp.concatenate([sign, jnp.ones_like(sign)], axis=-1)
    return move, kick, do_catch, do_jump


def action_dims():
    """Para a rede: lista de tamanhos das cabeças MultiDiscrete por jogador."""
    return list(NVEC)
