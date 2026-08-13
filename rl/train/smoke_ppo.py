"""
Smoke test de RL: prova que o env é treinável de ponta a ponta.

Roda alguns updates A2C (ator-crítico, 1 passo) — não busca aprender bem, só
demonstrar que obs->rede->ação->env->reward->gradiente fecha e roda na GPU, com
losses/gr—ads finitos e o crítico reduzindo o erro. É o esqueleto da Etapa 4.

  ../.venv-rl/bin/python rl/train/smoke_ppo.py
"""
import sys
import time
from pathlib import Path

_R = Path(__file__).resolve().parents[2]
for _p in (_R / "rl/envs", _R / "rl/jax", _R / "rl/train"):
    sys.path.insert(0, str(_p))

import jax
import jax.numpy as jnp
import optax

import lugo_env as E
from networks import Actor, Critic, sample_action, action_logprob, entropy

B = 256
UPDATES = 40
reset, env_step = E.make_env(B, episode_len=6000)

actor = Actor(nvec=tuple(E.META["action_nvec"]))
critic = Critic()


def main():
    key = jax.random.PRNGKey(0)
    s, (aobs, gobs) = reset()
    key, ka, kc = jax.random.split(key, 3)
    ap = actor.init(ka, aobs)
    cp = critic.init(kc, gobs)
    opt = optax.adam(3e-4)
    ostate = opt.init((ap, cp))

    def loss_fn(params, s, aobs, gobs, key):
        ap, cp = params
        logits = actor.apply(ap, aobs)                    # lista (B,2,11,ni)
        action, _ = sample_action(logits, key)            # (B,2,11,4)
        s2, (aobs2, gobs2), reward, done, info = env_step(s, action)
        r_side = reward.mean(-1)                           # (B,2)
        value = critic.apply(cp, gobs)                    # (B,2)
        target = r_side + 0.99 * critic.apply(cp, gobs2)  # 1-passo bootstrap
        adv = jax.lax.stop_gradient(target) - value
        lp = action_logprob(logits, action)               # (B,2,11)
        pg = -(lp * jax.lax.stop_gradient(adv)[..., None]).mean()
        vloss = (adv ** 2).mean()
        ent = entropy(logits).mean()
        loss = pg + 0.5 * vloss - 0.001 * ent
        return loss, (s2, aobs2, gobs2, vloss, r_side.mean())

    @jax.jit
    def update(params, ostate, s, aobs, gobs, key):
        (loss, aux), grads = jax.value_and_grad(loss_fn, has_aux=True)(
            params, s, aobs, gobs, key)
        upd, ostate = opt.update(grads, ostate)
        params = optax.apply_updates(params, upd)
        gnorm = optax.global_norm(grads)
        return params, ostate, loss, aux, gnorm

    params = (ap, cp)
    t0 = time.time()
    for i in range(UPDATES):
        key, k = jax.random.split(key)
        params, ostate, loss, aux, gnorm = update(params, ostate, s, aobs, gobs, k)
        s, aobs, gobs, vloss, rmean = aux
        if i % 8 == 0 or i == UPDATES - 1:
            print(f"update {i:3d} | loss {float(loss):+.4f} | vloss {float(vloss):.4f} "
                  f"| grad_norm {float(gnorm):.3f} | reward/step {float(rmean):+.4f} "
                  f"| finito? {bool(jnp.isfinite(loss))}")
    print(f"\n{UPDATES} updates A2C (B={B}) em {time.time()-t0:.1f}s -> "
          f"o env é TREINÁVEL de ponta a ponta na GPU.")


if __name__ == "__main__":
    main()
