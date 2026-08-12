# Fastsim — memo de viabilidade (fundação de trabalho futuro)

> Escrito durante o modo autônomo (ago/2026), enquanto rodava a confirmação de gols do
> pacote de heurísticas. Objetivo: decidir, **com dados**, se vale reimplementar o servidor
> Lugo em Python/numpy (e depois vetorizar em JAX/GPU) para destravar tuning rápido e RL.
> A pesquisa de RL (ver vault `lugo-rl-research`) concluiu: *RL funciona, mas depende de um
> simulador rápido; sem sim vetorizado a GPU fica ociosa.* Este memo é o pré-requisito disso.

## Tese

Não reimplementar o **bot** (isso reintroduz gap de fidelidade e joga fora a v9). Reimplementar
só o **servidor**: física + orquestração de turnos. Rodar o `my_bot.py` EXATO contra um
"inspector" in-process sobre um estado numpy, sem docker/gRPC. Ganho esperado: de ~53s/partida
(rush, docker) para milhares de partidas/s (vetorizado), destravando GA denso e self-play/RL.

## O que já existe e é reaproveitável

- `analysis/physics.py` (172 linhas): constantes oficiais + integração da bola (`ball_travel`,
  `ball_position_after`). Derivado das specs.
- `analysis/replay.py`: parser dos replays (base64+gzip+json), acessores tolerantes a campos
  omitidos (protobuf omite defaults).
- `bot/src/geometry.py`: `ball_step`, `turns_for_ball`, `turns_for_player` — a física que o bot
  já usa para decidir. Reusar como referência do passo de simulação.
- 149 replays reais em `bench/recordings/` — **conjunto de validação turno-a-turno**.

## Medição de fidelidade (feita agora, com dados)

Física de **voo livre** da bola, prevendo `pos_{t+1} = pos_t + speed_t · dir_t` contra o replay
real (`fin_001_away`, 5868 pares de turnos consecutivos com a bola em voo, speed≥50):

| métrica | erro (d) |
|---|---|
| mediana | **7,7** |
| média | 73,1 |
| p90 | 231 |
| máx | 947 |

**Conclusões factuais:**
1. O núcleo contínuo é essencialmente exato (mediana 7,7d num campo de 20000d ≈ 0,04%).
2. **Deslocamento por turno = velocidade ATUAL** (não `v − decel/2`); a desaceleração de
   10 d/turno² aparece limpa na sequência de speeds (250,3 → 240,3 → 230,3 …).
3. A partida tem **6000 turnos** e o replay grava **2 snapshots por turno** (par idêntico).
4. A cauda (p90 231, máx 947) NÃO é erro de física — são os **eventos discretos** que o
   modelo de uma-linha ignora: chute/toque no meio do voo, quique na parede, troca de posse.

## O que falta reimplementar (o trabalho de verdade = eventos discretos)

O contínuo está resolvido. O risco de fidelidade está TODO na orquestração:

1. **Posse e toque** — raio de contato `TOUCH_RADIUS=300`; quando um jogador está a ≤300 da
   bola, quem fica com a posse? Regra de prioridade em disputa simultânea (desconhecida — inferir
   dos replays comparando snapshots com jogadores sobrepostos à bola).
2. **Aplicação do chute/movimento** — ordem MOVE (≤100/turno) e KICK (soma à velocidade, ≤400).
   Confirmar se KICK *substitui* ou *soma* à velocidade atual da bola (o bot assume "soma";
   validar).
3. **Colisão jogador-jogador** — `PLAYER_SIZE=400`. Há repulsão/bloqueio? (inferir dos replays.)
4. **Goleiro** — `GOALKEEPER_JUMP_DURATION=3`, `JUMP_SPEED=200`. Mecânica de defesa/catch.
5. **Quique na parede** — reflexão em x∈{0,20000}, y∈{0,10000} (o `ball_trajectory` em
   geometry.py já reflete; portar).
6. **Gol e kickoff** — detecção (bola cruza x=0/20000 com y∈[3500,6500]) e reset ao centro.
7. **`state_change`** — o replay tem 12003 destes; decodificar pode revelar a máquina de estados
   oficial (DISPUTING/HOLDING/DEFENDING/SUPPORTING) e as transições — atalho para fidelidade.

## Estratégia de validação (de-risca tudo)

Os replays **não gravam `orders`** (só `game_snapshot` + `state_change`). Duas saídas:
- **(a) Inferir ordens** de snapshots consecutivos: Δpos do jogador = seu MOVE; Δvelocidade da
  bola = houve KICK. Reconstruir `orders_t`, aplicar o passo do sim a `snapshot_t`, comparar com
  `snapshot_t+1`. Erro por jogador/bola = mapa de quais regras faltam.
- **(b) Instrumentar** o servidor Go (ou o bot) para logar ordens numa run controlada — fidelidade
  perfeita, mais trabalho de setup.

Começar por (a): é grátis (temos 149 replays) e localiza exatamente as regras erradas.

## Esforço e recomendação

- **Passo 1 (0,5–1 dia):** decodificar `state_change`; validador de fidelidade turno-a-turno via
  ordens inferidas; quantificar erro por tipo de evento. **Portão de decisão.**
- **Passo 2 (1–2 dias):** servidor escalar em numpy que reproduz 1 partida fielmente (erro < ~50d
  acumulado por jogador). Rodar `my_bot.py` via inspector fake.
- **Passo 3 (2–4 dias):** vetorizar N partidas (numpy batched → JAX/`pgx`-style). Aí sim GA denso
  e self-play.
- **Passo 4 (RL):** CTDE sobre o sim vetorizado (ver `lugo-rl-research`).

**Recomendação:** o caminho é viável e o núcleo físico já é fiel. O gargalo é a orquestração
discreta, mensurável e localizável com os replays que já temos. Fazer o Passo 1 como portão:
se as ordens inferidas reproduzirem os replays com erro pequeno, seguir; senão, instrumentar (b).
NÃO iniciar antes de fechar o pacote de heurísticas (prioridade declarada = torneio via heurística).
