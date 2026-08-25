# Resultados do treino de RL (MAPPO) — 2026-08-14

Sessão autônoma de treino de RL no simulador JAX (`rl/`). Resumo honesto do que
foi construído, do que funciona e de onde o RL está frente ao heurístico **v9**.

## TL;DR

- **A infra de RL está pronta e FUNCIONA.** O agente aprende futebol de verdade:
  persegue, ganha e mantém posse (~50-73%), avança, finaliza e defende.
- Contra baselines simples o RL é forte: **estático 40x0**, **empata o chase**
  (defesa-enxame), **bate o "booting" +6.5** (atacante forte).
- **MAS contra o v9 (heurístico maduro) o RL PERDE feio: 0x8** (fastsim, 800t).
  O v9 é muito superior. **Recomendação: manter o v9 no torneio.** O RL é
  pesquisa/infra, não está pronto para competir.

## O que foi construído

- **Sim JAX vetorizado** (`rl/jax/step.py`) — física idêntica ao fastsim escalar,
  ~45M passos/s na GPU (GTX 1660S 6GB).
- **Env multiagente** (`rl/envs/`) — obs egocêntrica canonizada (109), ação
  MultiDiscrete [17,17,2,2], reward por-agente ajustável por env-var.
- **Treinador MAPPO/CTDE** (`rl/train/ppo_selfplay.py`) — ator compartilhado +
  crítico central por-agente, GAE, PPO clip; currículo **drill→estático→self-play**;
  **pool de oponentes diverso** (chase+booting+self); LR-anneal, checkpoints,
  **warm-start** para encadear runs.
- **Avaliação** (`rl/train/evaluate.py`, `scratch/league.sh`), **diagnóstico**
  (`diag.py`), **deploy** (`rl/eval/deploy_policy.py`, amostra), e **eval vs v9
  real no fastsim** (`rl/eval/eval_vs_v9.py`).

## Como o aprendizado foi destravado (4 bugs sequenciais)

Cada bug tinha o MESMO sintoma (posse 0%, sem gols) e mascarava o próximo:

1. **Reward 100% PBRS** (γΦ'−Φ, invariante à política) → vantagem ≈0. Fix: shaping
   DIRETO.
2. **Exploração destrói a posse**: kick head uniforme chuta 94% → larga a bola.
   Fix: **prior de inicialização** no ator (segurar + pegar por default).
3. **Reward farmável parado**: avanço da bola pago passivamente → botar e abandonar.
   Fix: avanço **só com posse** + near-ball forte (perseguir) + catch-evento.
4. **Bug de medição no eval**: lia `final.score` após o auto-reset → sempre 0x0,
   escondendo que os policies SEMPRE marcaram. Fix: somar gols por evento.

## Recipe vencedor (vs baselines)

reward v5 + **W_DANGER** (penaliza bola rumo ao próprio gol → corta gols-contra) +
**pool diverso** (chase/booting/self) + **drill de finalização** (start-state com a
bola perto do gol). Melhora **monotônica** com self-play (posse 1%→73%; saldo vs
chase −1.7→−0.02 em 2000 updates).

## Resultados (eval corrigido, 128 jogos, 6000t)

| Policy | vs estático | vs chase | vs booting | H2H |
|---|---|---|---|---|
| v6 | 40x0 | −0.14 | +6.45 | — |
| v7 | 19x0 | **−0.02** | +3.83 | bate v6 |
| v8 | 13x0 | −0.56 | +6.12 | **bate v7 (+0.29)** |
| final (warm-start v8 +4000u) | 3x0 | −0.33 | +6.76 | empata v8 (−0.03) |

- **v8** é o melhor por confronto direto (controlador: posse ~54-64%, defesa quase
  impenetrável, marca o suficiente). A run "final" (mais 4000 updates de self-play a
  partir do v8) deu **dead draw** vs v8 → o recipe **PLATÔOU**; mais self-play do
  mesmo tipo não melhora.

## O teste que importa: RL vs v9

- Adaptador net→fastsim **validado** (RL faz 15x0 vs nulo, = ao JAX).
- **v8 vs v9 = 0x8** (fastsim, 800t): o v9 marca 3-5 gols, o RL marca 0.
- **BC do v9 FALHA** (clone com 0% posse, perde para tudo; o v8 bate o clone +0.6) —
  distribution shift clássico + o v9 é ajustado para o servidor real (catch por ordem
  de chegada), não para a mecânica do sim JAX (argmin).

## Por que o RL não alcança o v9 (limitação estrutural)

O **v9 (Python/lugo4py) não roda dentro do batch JAX vmapado** — então os oponentes
de treino têm de ser JAX-nativos. Os disponíveis (self/chase/booting) são fracos, e
o **BC falha em clonar o v9**. Logo o RL só treina contra oponentes fracos e
**platôa muito abaixo do v9**. Isso já era o risco #1 do plano ("payoff vs v9
incerto; v9 já é 20/20"). Fechar a lacuna exigiria: um clone-v9 forte (DAgger,
incerto), ou RL no sim escalar vs v9 (lento demais para RL), ou muito mais compute.

## O platô é REAL e ESTRUTURAL (testado à exaustão)

Três experimentos independentes confirmam o teto:
- **Run final** (warm-start v8 + 4000u self-play): dead draw vs v8 (−0.03).
- **Pass-run** (warm-start v8 + reward de recepção/interceptação): dead draw (+0.00).
- **Form-run** (warm-start v8 + **oponente FORTE** formation 40% no pool): melhorou
  MUITO vs o formation (−6.34 → **−2.05**) e passou a marcar um pouco vs o v9, mas
  vs v8 = dead draw (+0.05) e **vs v9 ainda −20.5** (3.75 x 24.25, 6000t).

**Por que nem um oponente forte resolve:** construí um oponente heurístico JAX
decente — `rl/envs/opponents.py:formation_action` (segura formação + pressiona com
os 2 mais próximos + goleiro acompanha a bola + holder dribla/chuta). Ele é FORTE
(bate meu v8 **6.38x0.03**, o booting 51x0). MAS **o próprio formation perde para o
v9: 0x12 e 0x19** (fastsim). Ou seja: **nenhum oponente JAX-nativo que dá para
construir alcança o v9**, e o RL só aprende de oponentes JAX-nativos (o v9 não roda
no batch JAX). Logo o RL está **estruturalmente teto-limitado abaixo do v9** — o
melhor professor JAX (formation) já é 0-15 vs v9.

## Levers de RL testados (todos exauridos)

reward shaping extenso, currículo, drill de finalização, pool diverso, self-play
longo, warm-start encadeado, e **oponente heurístico forte**. Nenhum fecha a lacuna
vs v9. A limitação é a #1 do plano ("v9 fora do loop JAX"), agora quantificada.

Único caminho teórico restante (arriscado, fora do escopo desta sessão): **DAgger**
para clonar o v9 num net JAX que TRANSFIRA (casando a mecânica de catch do sim JAX
com a do servidor real). Payoff incerto.

## Recomendação

- **Torneio: manter o v9.** É claramente superior (0x8) e já é 20/20 vs level-1.
- **O RL fica como infra de pesquisa pronta.** Melhores pesos:
  `scratch/policy_v8.pkl` (≈ v7 ≈ final ≈ pass, todos empatados), deploy via
  `rl/eval/deploy_policy.py` (amostra). Todo o pipeline (`rl/`) está funcional e
  parametrizado (env-vars de reward, `--drill-frac --p-chase --p-boot --init-pkl`).
- O esforço de RL foi levado ao teto deste framework; avançar exige o item (1) acima.
