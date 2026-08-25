"""
Redes ator-crítico (flax) para o env do Lugo — CTDE com compartilhamento de
parâmetros.

- Actor: MLP compartilhado sobre a obs POR-AGENTE (109), com 4 cabeças
  categóricas MultiDiscrete [17,17,2,2]. O mesmo ator serve os 22 jogadores (a
  obs é canonizada p/ "sempre ataca +x"); um embedding de papel pode ser somado
  depois (goleiro vs linha).
- Critic: MLP sobre a obs GLOBAL (96) -> valor por lado (crítico central CTDE).
"""
import jax
import jax.numpy as jnp
import numpy as np
from flax import linen as nn


def _bias_at(n, idx, val):
    """Inicializador de bias: zeros exceto `val` no índice `idx` (prior de ação)."""
    def init(key, shape, dtype=jnp.float32):
        b = np.zeros(n, np.float32)
        b[idx] = val
        return jnp.asarray(b, dtype)
    return init


class Actor(nn.Module):
    """Ator compartilhado. As cabeças de kick/catch recebem um PRIOR de bias:
    kick -> favorece índice 0 (não chutar = SEGURAR); catch -> favorece índice 1
    (pegar). Sem esse prior, a exploração uniforme faz o holder largar a bola em
    ~94% dos turnos (16/17 direções ≠ nokick) e a POSSE nunca emerge (o reward de
    is-holder fica inalcançável por acaso). Ver diagnóstico 2026-08-13."""
    nvec: tuple = (17, 17, 2, 2)
    hidden: int = 256
    kick_hold_bias: float = 3.0    # ~77% nokick no início (segura, mas explora chute)
    catch_bias: float = 3.0        # ~95% catch no início (tentar pegar/roubar)

    @nn.compact
    def __call__(self, obs):
        x = nn.relu(nn.Dense(self.hidden)(obs))
        x = nn.relu(nn.Dense(self.hidden)(x))
        x = nn.relu(nn.Dense(self.hidden)(x))
        # bias_init por cabeça: [move, kick, catch, jump]
        binit = [nn.initializers.zeros,
                 _bias_at(self.nvec[1], 0, self.kick_hold_bias),
                 _bias_at(self.nvec[2], 1, self.catch_bias),
                 nn.initializers.zeros]
        return [nn.Dense(n, bias_init=bi)(x)
                for n, bi in zip(self.nvec, binit)]   # lista de logits (...,n)


class Critic(nn.Module):
    """Crítico CENTRAL (MAPPO/CTDE): recebe a obs GLOBAL do time e emite um valor
    POR-AGENTE (n_out=11). Condicionar no estado completo dá vantagens de menor
    variância e melhor coordenação que um crítico ego-only (IPPO)."""
    n_out: int = 11
    hidden: int = 256

    @nn.compact
    def __call__(self, gobs):
        x = nn.relu(nn.Dense(self.hidden)(gobs))
        x = nn.relu(nn.Dense(self.hidden)(x))
        x = nn.relu(nn.Dense(self.hidden)(x))
        return nn.Dense(self.n_out)(x)              # (..., 11) valores por-agente


def sample_action(logits_list, key):
    """Amostra uma ação MultiDiscrete e devolve (action (...,4), logprob (...))."""
    keys = jax.random.split(key, len(logits_list))
    comps, lps = [], []
    for lg, k in zip(logits_list, keys):
        a = jax.random.categorical(k, lg, axis=-1)              # (...,)
        lp = jnp.take_along_axis(jax.nn.log_softmax(lg, -1),
                                 a[..., None], -1)[..., 0]
        comps.append(a); lps.append(lp)
    return jnp.stack(comps, -1), sum(lps)


def action_logprob(logits_list, action):
    """log-prob de uma ação dada (para o ratio do PPO)."""
    lp = 0.0
    for j, lg in enumerate(logits_list):
        lp = lp + jnp.take_along_axis(jax.nn.log_softmax(lg, -1),
                                      action[..., j][..., None], -1)[..., 0]
    return lp


def entropy(logits_list):
    ent = 0.0
    for lg in logits_list:
        p = jax.nn.softmax(lg, -1)
        ent = ent + -(p * jax.nn.log_softmax(lg, -1)).sum(-1)
    return ent
