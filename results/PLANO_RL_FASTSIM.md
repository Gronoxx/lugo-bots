# Plano: transformar o fastsim num treinador de RL (JAX/GPU, fundação primeiro)

## Contexto

O bot heurístico v9 é forte mas está num platô: a evolução e os A/B mostram que *saldo-vs-level-1* é uma régua fraca/ruidosa demais para premiar melhorias de decisão, e o gargalo real é a **avaliação** (docker ~53s/partida). Já existe um simulador em processo (`sim/fastsim.py`, ~43× mais rápido que o docker, física da bola validada a 0,4d), mas ele: (a) roda `policies` simples, não o `my_bot` real; (b) só teve a física de voo-livre validada; (c) é escalar; (d) não tem interface de RL nem está ligado à evolução.

Objetivo: evoluir esse fastsim para um **treinador de RL vetorizado em JAX/GPU**, mas **construindo a fundação primeiro** — a ponte `my_bot→sim` + gate de fidelidade tem valor independente do RL (destrava avaliação heurística ~43× mais rápida, o gargalo declarado). O RL fica condicionado ao gate de fidelidade passar. Payoff do RL vs v9 é incerto; por isso o valor é front-loaded.

**Decisões do usuário:** framework = **JAX + GPU vetorizado**; prioridade = **fundação primeiro, RL depois**.

**Restrição arquitetural central:** o `my_bot` (Python, usa `lugo4py.GameSnapshotInspector`) **não pode rodar dentro de um batch JAX `vmap`ado**. Consequência: o **sim escalar numpy** (`sim/fastsim.py`) permanece a ferramenta de *ponte, validação e eval* (rodar o my_bot como oponente/referência e como backend rápido da evolução); o **sim JAX** é o *loop de treino* de alta vazão, cujos oponentes são redes neurais ou políticas JAX-nativas. Isso cria **dois gates de fidelidade**: escalar↔docker (Etapa 1) e JAX↔escalar (Etapa 2).

## Ambiente (Etapa 0)

Criar um venv dedicado **Python 3.11/3.12** (o `.venv` atual é 3.14, sem wheels de JAX) com: `jax[cuda12]` (a GTX 1660 SUPER é cc7.5, suportada), `flax`, `optax`, `numpy`, e o `lugo4py` do repo (a ponte precisa dele). Manter o `.venv` 3.14 do torneio intocado. Verificar `jax.devices()` vê a GPU e que `sim/fastsim.py`+`import lugo4py` importam no venv novo.
- Verificação: `play(dummy_policy, dummy_policy)` roda no venv novo; `jax.devices()` lista a GPU.

## Etapa 1 — Fundação: ponte escalar + gate de fidelidade (valor autônomo; PORTÃO)

Rodar o **my_bot exato** dentro do fastsim escalar via o inspector REAL (não fake), validar a partida inteira contra o docker, e corrigir as simplificações. Recompensa imediata: backend ~43× mais rápido para os A/B de genes.

- **Conversores** (`rl/bridge/snapshot.py`, `rl/bridge/orders.py`), templados em `bench/latency.py:28-64`:
  - `State→GameSnapshot`: por turno, montar um `server_pb2.GameSnapshot` (`state=LISTENING`, `turn`), preenchendo `position`/`velocity`/`init_position` de `s.pos/s.vel` (velocity = `direction` normalizada a magnitude 100 + `speed=|vel|`, **com fallback de vetor-unitário e speed=0 quando a velocidade é zero** — o caso que quebra `geo.normalize`), `ball.position/velocity`, `ball.holder` (ausente/number 0 = bola livre), e `shot_clock`. Mapear `number = idx+1`.
  - `Order→dict`: por `WhichOneof("action")`, `move/kick/jump`→`(dir.x/100*speed, dir.y/100*speed)`, `catch`→`{"catch":True}`; juntar as 1-2 ordens de um jogador num dict; espalhar no slot `idx=number-1`.
- **my_bot como política do sim** (`rl/bridge/heuristic_policy.py`): reusar o dispatch de `sim/test_remote.py:45-62` (holder→estado→callback: `on_holding/on_supporting/on_defending/on_disputing/as_goalkeeper`), 1 `GameSnapshotInspector` por jogador sobre o snapshot compartilhado + `lugo4py.Mapper` real. Entrega `policy(state, side)→11 dicts`, drop-in para `fastsim.play`.
- **Validação full-match** (`rl/fidelity/validate_match.py`): rodar my_bot-vs-dummy e my_bot-vs-my_bot no fastsim e comparar **distribuições** (não turno-a-turno — o docker tem não-determinismo de ordem de chegada) contra `bench/recordings/` via `analysis/metrics_lab.all_metrics` + `bench/proxy_metric` (placar, posse%, território%, avanço/posse, chutes ao gol, best-slack). Reconciliar aqui a dúvida do integrador (voo-livre trapezoidal `v−5` já está em `sim/validate.py`/`geometry.ball_step` e foi confirmado a 0,4d — corrigir qualquer doc/menção a "deslocamento=velocidade").
- **Corrigir simplificações** em `sim/fastsim.py` guiadas por inferência de ordens dos replays: (i) roubo/`catch` quando `holder≠None` e disputa por ordem de chegada real, não HOME-antes-de-AWAY (`step` `:132-146`, `_try_catch` `:249`); (ii) alcance efetivo do goleiro (300 vs ~560 que o bot assume, `proxy_metric.GK_HALF`); (iii) o empurrão do círculo de 1400 no gol adversário (`_advance_player:239-246`) — checar contra a área real; (iv) drible (`:149-152`). Re-rodar a validação após cada correção.
- **Payoff autônomo:** adicionar `step_inplace` ao `sim/fastsim.py` (rollouts não precisam do `copy()` funcional) e um backend `evaluate()` em `bench/evolve.py` que usa o fastsim → A/B de genes ~43× mais rápido.
- **PORTÃO (obrigatório p/ seguir):** em ≥30 partidas, métricas agregadas fastsim vs docker dentro da tolerância (posse/território a poucos %, placar dentro da variância entre partidas); bônus: o backend fastsim reproduz o *ranking* docker de alguns genomas conhecidos.

## Etapa 2 — Sim vetorizado em JAX + paridade de fidelidade

Reescrever a física como função pura JAX para milhares de partidas em paralelo na GPU.
- `rl/jax/step.py`: `State` como pytree de arrays; `step` sem branches (condicionais por máscara: catch, gol, reset, shot-clock, goal-zone, bounce), `jit`+`vmap` sobre o batch B, `scan` sobre os turnos. Constantes idênticas às de `sim/fastsim.py:24-45`.
- **Gate JAX↔escalar:** alimentar sequências de ordens idênticas nos dois sims e exigir divergência ínfima (a física JAX herda a fidelidade validada do escalar). É uma 2ª implementação — precisa re-passar o gate.
- Verificação: erro JAX-vs-escalar por turno ~nível de arredondamento; throughput medido na GPU (turnos/s) com B grande dentro dos 6GB.

## Etapa 3 — Env multiagente + obs/ação/reward (JAX-nativo)

`rl/envs/` sobre o sim JAX: `reset→obs`, `step(actions)→(obs, reward, done, info)`, batched.
- **Observação** (`obs.py`): vetor egocêntrico por agente, **canonizado p/ "sempre ataca +x"** (espelha AWAY) p/ uma rede compartilhada servir os dois lados. Inclui: self (pos/vel/is_holder/jump), bola (rel pos/vel + one-hot do dono), companheiros (rel, ordenados por número + embedding de papel), k oponentes mais próximos + slot do goleiro adversário, contexto (shot_clock, diff de placar, fração do turno). **CTDE:** crítico central lê o estado completo (grátis, é o `State`); atores decem. leem só o egocêntrico.
- **Ação** (`actions.py`): **MultiDiscrete fatorada com masking** — move (8-16 direções + parar, a max speed), kick (direção×2-3 potências, mascarado exceto p/ o holder), catch (binário, compõe com move), jump (só goleiro). Máscara kick⇔holder e jump⇔GK é essencial.
- **Reward** (`rewards.py`): esparso primário = ±1 por gol (delta de `state.score`); **shaping potential-based** `F=γΦ(s')−Φ(s)` (invariante à política, permite anelar) com Φ = avanço rumo ao gol + posse + **slack do goleiro na zona** (`bench/proxy_metric`, AUC 0,868, o sinal mais forte) + `finishing.xg` nos chutes − `opp_danger`. Split por papel (goleiro←defesa/slack; atacante←xg/avanço). Schedule denso→esparso.
- **Portão de sanidade:** um PPO mínimo aprende algo trivial (um agente aprende a perseguir/segurar a bola; um time bate `dummy_policy` no reward moldado).

## Etapa 4 — Self-play MAPPO em JAX (núcleo especulativo)

`rl/train/` estilo PureJaxRL (tudo compilado): ator outfield **compartilhado** (10 jogadores, obs egocêntrica + embedding de papel) + ator do **goleiro** separado + crítico central compartilhado.
- **Self-play** (`opponent_pool.py`): fictitious/prioritized — snapshot periódico da política, amostra oponentes do pool p/ controlar a não-estacionariedade. Pool semeado com baselines **JAX-nativas** (reimplementar `dummy`/shaped em JAX) — o **my_bot NÃO entra no loop JAX** (só serve de eval no sim escalar / docker).
- **Currículo** de tamanho de time (3v3→5v5→11v11) p/ domar a atribuição de crédito.
- Redes = MLPs pequenas (cabem em 6GB). Checkpoint/CSV como `bench/evolve.py`.
- **Portão:** win-rate claramente > `dummy` e > shaped; alvo esticado ≥ paridade com my_bot (eval no escalar). Elo-vs-pool subindo, sem colapso.

## Etapa 5 — Adaptador de deploy + sim2real

`rl/eval/deploy_policy.py`: inverter a ponte — `policy(side, number, inspector)→list[Order]` que codifica a obs a partir de um inspector REAL (mesmo `obs.py`), roda a rede, e emite Orders (inverso de `orders.py`). Plugar em `sim/remote_match.DeterministicMatch` p/ eval determinístico no docker; p/ o torneio, embrulhar no cliente `lugo4py` como `bot/src/main.py`.
- Eval vs level-1 e vs v9 **só aqui** (level-1 é imagem docker, não entra no sim), reusando `bench/evolve.py`/`eval_genome.sh`.
- **Portão:** métricas in-sim vs docker concordam (sim2real aceitável); saldo da política RL vs level-1 reportado ao lado do da v9. Decisão: usar em torneio, ou manter v9 e tratar o RL como pesquisa.

## Arquivos

**Reusar:** `sim/fastsim.py` (+ `step_inplace`, correções de fidelidade), `sim/test_remote.py` (dispatch), `sim/remote_match.py` (deploy/eval docker), `bench/latency.py` (montar snapshot), `bot/src/my_bot.py` (+ `geometry.py`, `tactics.py`, `params.py`, `finishing.py`, `settings.py`), `lugo4py` (`GameSnapshotInspector`, `Mapper`), `bench/proxy_metric.py` (slack), `analysis/metrics_lab.py` (métricas), `analysis/replay.py`, `bench/recordings/*.json`, `bench/evolve.py` (backend rápido).

**Criar (novo dir `rl/`):**
```
rl/bridge/   snapshot.py  orders.py  heuristic_policy.py     # Etapa 1
rl/fidelity/ validate_match.py                               # Etapa 1
rl/jax/      step.py  env_core.py                            # Etapa 2
rl/envs/     lugo_env.py  obs.py  actions.py  rewards.py     # Etapa 3
rl/train/    ppo_selfplay.py  networks.py  opponent_pool.py  # Etapa 4
rl/eval/     deploy_policy.py  eval_in_sim.py                # Etapa 5
rl/configs/  *.yaml   rl/checkpoints/   rl/README.md
```

## Verificação (por etapa)
- **0:** sim roda no venv RL; `jax.devices()` vê a GPU.
- **1 (PORTÃO):** fastsim vs docker dentro da tolerância em ≥30 partidas; backend fastsim reproduz ranking docker de genomas conhecidos.
- **2 (PORTÃO):** erro JAX-vs-escalar ~arredondamento com ordens idênticas; throughput/s na GPU medido.
- **3:** PPO aprende objetivo trivial; time bate `dummy` no reward moldado.
- **4:** win-rate > baselines; Elo-vs-pool subindo; alvo ≥ my_bot no escalar.
- **5:** in-sim ≈ docker (sim2real); saldo vs level-1 e vs v9 no docker.

## Riscos (honesto)
- **sim2real (alto):** RL explora qualquer imprecisão do sim. Mitigações: gate de fidelidade da Etapa 1 antes de qualquer RL; shaping potential-based; check da Etapa 5; **domain-randomization** das constantes incertas (ordem de disputa, alcance do goleiro, integrador) p/ robustez.
- **JAX das regras discretas (médio):** reescrever catch/gol/reset sem branches é o custo extra vs o caminho CPU; mitiga com o gate JAX↔escalar.
- **my_bot fora do loop JAX (médio):** oponentes de treino têm de ser JAX-nativos/neurais; o my_bot só entra como eval no escalar/docker.
- **MARL 11v11 (alto):** crédito/coordenação/não-estacionariedade — a maior incerteza de cronograma. Mitiga: CTDE + param sharing + currículo + pool.
- **GPU modesta (baixo-médio):** 6GB sem tensor cores limita batch/rede; MLPs pequenas bastam.
- **Payoff incerto vs v9 (estratégico):** a v9 já é 20/20; o RL pode não superá-la a tempo. Por isso a Etapa 1 tem **valor garantido** independente do RL.
- **Etapas que de-riscam barato:** 0, **1 (ponte+fidelidade — barata, valor autônomo, valida toda a física)**, e o portão de sanidade da 3. O gasto especulativo caro é a 4 (self-play). Condicionar o investimento em RL ao portão da 1 + um resultado positivo da 3.
