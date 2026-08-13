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
from flax import linen as nn


class Actor(nn.Module):
    nvec: tuple = (17, 17, 2, 2)
    hidden: int = 256

    @nn.compact
    def __call__(self, obs):
        x = nn.relu(nn.Dense(self.hidden)(obs))
        x = nn.relu(nn.Dense(self.hidden)(x))
        x = nn.relu(nn.Dense(self.hidden)(x))
        return [nn.Dense(n)(x) for n in self.nvec]   # lista de logits (...,n)


class Critic(nn.Module):
    hidden: int = 256

    @nn.compact
    def __call__(self, gobs):
        x = nn.relu(nn.Dense(self.hidden)(gobs))
        x = nn.relu(nn.Dense(self.hidden)(x))
        x = nn.relu(nn.Dense(self.hidden)(x))
        return nn.Dense(1)(x)[..., 0]                # valor (...)


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
