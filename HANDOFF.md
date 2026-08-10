# Continuidade — projeto Lugo Bots (migração para Linux)

> Cole este arquivo no início da sessão do Claude na máquina Linux.
> Ele carrega o estado, as lições que custaram caro, e o que fazer a seguir.

## DIVISÃO DE TRABALHO ENTRE AS DUAS MÁQUINAS

**Linux (i5-10400F, 12 threads, 15,5 GB, Docker nativo) = a FÁBRICA.**
Gera partidas em volume. Medido lá: `wait` leva 5m43s por partida — igual ao Mac.
O ganho não é velocidade por partida, é **paralelismo**: 2-3 partidas simultâneas
em portas distintas. É onde rodam evolução, varreduras e séries longas.

**Mac = o LABORATÓRIO.**
Análise de replays, pesquisa, mudanças de código, download e análise dos vídeos
oficiais, intel sobre adversários. Decide o que testar; o Linux testa.

Fluxo: Mac propõe mudança → Linux mede → Mac analisa o replay e decide a próxima.

---

## Objetivo

Vencer o **4º Campeonato Aberto de Lugo Bots** (futebol de bots multi-agente,
plataforma brasileira). Calendário: inscrição até **16/ago/2026**,
classificatórias 17/ago, quartas 27-28/ago, semis 25/set, **final 9/out**.
Há bastante tempo de melhoria DEPOIS da inscrição.

## Estado: `mybot:v9` é a melhor versão verificada

**20 vitórias em 20 partidas** contra o painel completo, 1 gol sofrido no total:

| adversário | gols pró | contra |
|---|---|---|
| rival_p3 | 17,2 | 0,0 |
| rival_p2 | 14,0 | 0,0 |
| rival_p4 | 12,8 | 0,0 |
| rival_p1 | 8,5 | 0,8 |
| baseline oficial (the-dummies) | 7,5 | 0,2 |

Ganho conclusivo sobre a v3: **+2,73 gols** (5,06 × 2,33; erro padrão 0,76).

---

## A LIÇÃO MAIS IMPORTANTE: medir antes de acreditar

Três versões seguidas falharam porque troquei um modelo por outro **sem medir o
efeito no comportamento**. Não repita:

| versão | mudança | resultado |
|---|---|---|
| v6 | modelo de goleiro "correto" (física) | inconclusivo — o teste tinha só **17% de poder** |
| v8 | + busca de ângulo lateral | **0,69 gols** contra 3,31 da v3 — conclusivamente PIOR |
| v9 | portão de chute **empírico** (dados, não física) | **5,06 gols** — conclusivamente melhor |

A causa comum de v6 e v8: meu portão de finalização usava um modelo de física
pessimista (goleiro sempre pulando a 200 d/turno). Ele fechava em ~99% dos
turnos na área e o bot **parava de finalizar**. A v9 trocou isso pela regra
medida em 135 chutes reais.

**Regras que vieram dessa dor:**

1. **Uma mudança por vez.** A v8 empacotou duas e não deu para saber qual estragou.
2. **Poder estatístico antes de concluir.** O desvio entre partidas idênticas é
   **~2,0 gols** sobre média ~4. Com 8 partidas por versão o teste enxerga só
   diferenças acima de ~2,7 gols. `compare.sh` já imprime esse limite — leia-o
   antes de dizer "não funcionou".
3. **Regra empírica > modelo teórico.** Sempre que houver dados rotulados,
   calibre neles.
4. **Nunca confie numa métrica sem checar plausibilidade.** Duas ferramentas
   minhas de análise deram números errados por meses (uma reportava "bola solta
   107% dos turnos" — impossível, e passou batido).

---

## Física e regras que descobrimos (não estão na documentação)

- **Partida tem 6000 turnos**, não os 1200 que o site diz.
- **Integração trapezoidal**: a bola avança `v - desaceleração/2` por turno. Com
  isso o erro de previsão cai de 5,0d para **0,38d** (`sim/validate.py`).
- **`GOALKEEPER_SIZE = 920`** (2,3× um jogador), não 400. Meia-extensão efetiva
  contra a bola: 560. Em `lugo4py` a constante é uma *tupla* por causa de uma
  vírgula final — ninguém no ecossistema Python jamais a usou.
- **O goleiro é preso à linha** (x ∈ {0, 20000} em 12.058 snapshots) e o servidor
  **o acelera até 200 d/turno perto de bola rápida mesmo sem ordem de pulo**.
- **`make_order_kick` da lugo4py mira torto**: compensa a velocidade da bola com
  `normalize`, que escala para magnitude 100, enquanto a bola anda até 400. Erro
  mediano de **19,2°**. Nosso `geometry.kick_to` resolve a física ao contrário e
  busca o melhor chute alcançável: **1,3°**. Todo bot Python da competição tem
  esse defeito.
- **Conversão depende da folga lateral do goleiro** ao ponto de cruzamento
  (135 chutes medidos): `<1200 → 0%` · `1200-1800 → 29%` · `>1800 → 45%`.
  A distância ao gol é praticamente igual nos dois grupos — **o que separa é o
  ângulo, não a proximidade**.

## Armadilhas de infraestrutura

1. **O servidor não encerra o container ao fim da partida.** Detecte o fim pelo
   evento `game_over` no replay (`bench/match_done.py`), nunca por
   `docker inspect` — isso custava 20 min por partida em vez de 3.
2. **O servidor faz panic** se o arquivo de `--record-path` já existir. Apagar antes.
3. **Posição inicial inválida** derruba o registro (e com <11 jogadores o time
   perde por W.O.). Duas causas: metade adversária do campo (Col ≤ 9 com 20
   colunas) e o **círculo neutro central** (raio 1000) — por isso Col 9/Row 4 falha.
4. **`depends_on` não espera o servidor aceitar conexões.** O cliente lugo4py tem
   timeout fixo de 5s sem retry. `bot/src/main.py` já espera a porta ativamente.
5. **`make_order_move_to_stop()` está quebrado** na lugo4py 1.0.5 (chama
   `me.get_velocity()`, que não existe). Contornado em `safe_move`.
6. **`is_ball_holder()` exige o jogador como argumento.** Sem ele, exceção a cada
   turno — e como as callbacks têm `try/except`, o jogador fica parado **sem sinal**.
7. **No macOS a porta 5000 é do AirPlay.** No Linux isso não acontece.
8. **`LugoClient.stop()` chama `exit(0)`** — mata o processo. Feche o canal direto.

## Modos do temporizador

| modo | uso |
|---|---|
| `wait` | **padrão do servidor e o que o campeonato usa.** Validar aqui. |
| `remote` | "only in dev mode" — para treino determinístico. Proibido em partida oficial. |
| `rush` | **não usar.** Foi escolha nossa por velocidade; não é determinístico nem representa o torneio. |

Testado: nem `wait` nem `rush` são determinísticos (o ruído vem da **ordem de
chegada** das ordens dos 22 clientes concorrentes). `lugo.RLAssistant` resolveria
isso com uma única mensagem por turno, mas **não é exposto** por esta versão do
servidor (sondado por reflexão gRPC).

---

## Estrutura

```
bot/src/        my_bot.py (5 callbacks), geometry.py (física+kick_to),
                tactics.py (formação), params.py (30+ genes com faixas)
bench/          run_match.sh · compare.sh (A/B com poder) · sweep.sh (varredura
                de 1 parâmetro) · panel.sh (vs todos os rivais) ·
                match_done.py · test_edge_cases.py (140 casos) · latency.py
analysis/       replay.py (parser) · report.py · gk_response.py · compare_sides.py
sim/            fastsim.py (ENVIESADO, não usar para fitness) · validate.py
                (regressão da física) · remote_match.py (controlador
                determinístico, INCOMPLETO)
rivals/         4 bots públicos de participantes (construídos como imagens)
upstream/       repos oficiais lugobots
```

**Sistema de parâmetros:** uma imagem serve qualquer genoma via `BOT_PARAMS`
(JSON no ambiente). É o mecanismo que a evolução usa — não reconstrua imagem por
indivíduo. Genoma inválido cai nos padrões em vez de derrubar o bot.

---

## ⚠️ ACHADO QUE MUDA O ALVO (confirmar antes de agir)

Levantamento por agentes indicou que **a fase de classificação NÃO é contra
participantes — é contra os bots oficiais Level 1, 2 e 3**:

| adversário | vitória | empate |
|---|---|---|
| Level 3 | 8 pts | 3 |
| Level 2 | 7 pts | 3 |
| Level 1 | 5 pts | 1 |

Máximo 20 pts. Desempate nesta ordem: saldo vs L3 → gols vs L3 → saldo vs L2 →
gols vs L2 → saldo vs L1 → **data de inscrição**.

Também indicado: **regra de misericórdia a +10** (em 1.279 partidas de 2025-26,
nenhuma passou de 10 de diferença) — golear além disso não rende nada.

**Consequências:**
1. O painel atual (4 rivais do GitHub + `the-dummies`) **não representa o alvo**.
   Trocar para Level 1/2/3.
2. O fitness da evolução deve ser **saldo contra o Level 3**, não gols contra os
   dummies.
3. Inscrever cedo é critério de desempate.

**Status da verificação:** `lugobots/level-1:latest` existe e foi baixado no Mac.
`level-2` e `level-3` **não** vieram com esse nome — achar a variação correta é a
primeira tarefa. O regulamento em si veio de agente e **ainda não foi conferido
diretamente na página do torneio** — confirme antes de reorientar tudo.

## Resultado da varredura de `shot_min_gap` (Mac, 24 partidas)

| valor | n | gols |
|---|---|---|
| **900** | 6 | **6,00** |
| 1300 (atual) | 6 | 5,50 |
| 1700 | 5 | 2,40 |
| 2100 | 6 | 1,50 |

900 e 1300 são indistinguíveis (diferença 0,5, erro ~1,4); acima de 1300 despenca.

**Isso corrigiu uma leitura minha:** eu tratava chutes de folga pequena como
desperdício porque convertem 0%. Mas eles rendem mais gols que NÃO chutar —
provavelmente por rebote e manutenção de pressão, enquanto não chutar termina em
desarme (87-91% das perdas eram "condução tomada"). **Volume vale mais que
precisão por chute.** Vale varrer abaixo de 900 — a tendência não mostrou fundo.

## Próximos passos, em ordem

1. **Portar e validar no Linux** — rodar `bench/setup_linux.sh`, depois
   `./run_match.sh mybot:v9 lugobots/the-dummies-go:latest teste` e conferir que
   completa. **Meça o tempo por partida**: no Mac era ~5 min com 4 núcleos em VM;
   no Linux com 12 threads nativos deve cair bastante.
2. **Habilitar partidas paralelas.** Cada partida usa 23 containers leves; com
   15,5 GB e 12 threads devem caber 2-3 simultâneas em portas diferentes. É o
   maior multiplicador disponível.
3. **Evolução dos parâmetros.** Genes e faixas já estão em `params.py`. Desenho
   acordado: modelo de ilhas (frentes com ênfases diferentes), mutação
   estrutural a cada T épocas, **especiação** (proteger estruturas novas por K
   gerações, senão morrem antes de amadurecer), **hall of fame** contra
   pedra-papel-tesoura, e escolha do candidato por **maximin** (num mata-mata o
   que elimina é o confronto ruim, não a média).
4. **Modelo aprendido de finalização** substituindo o limiar fixo `shot_min_gap`.
   Já há dados rotulados (135 chutes) e uma logística sobre a folga do goleiro
   atinge AUC 0,98. Treina em segundos, sem GPU.
5. **Terminar `sim/remote_match.py`** se a evolução precisar de determinismo. Ele
   conecta os 22 em um processo e serializa o envio das ordens; falta ajustar o
   `OrderSet` (o servidor responde "did not return orders") e reiniciar o
   servidor entre partidas.

**Sobre RL completo:** mal-condicionado aqui (11 agentes, ação contínua,
recompensa esparsa, episódios de 6000 turnos) e o gargalo é gerar partidas, não
treinar rede — a GPU ficaria ociosa. Só depois de 1-4, e sem expectativa alta.

## Comandos

```bash
./bench/run_match.sh mybot:v9 lugobots/the-dummies-go:latest teste   # 1 partida
./bench/compare.sh mybot:v9 mybot:v10 8                             # A/B com poder
REPS=3 ./bench/sweep.sh mybot:v9 shot_min_gap 900 1300 1700 2100     # varredura
./bench/panel.sh mybot:v9 2 results/panel.csv                        # vs todos
.venv/bin/python bench/test_edge_cases.py                            # 140 casos-limite
.venv/bin/python sim/validate.py bench/recordings/<x>.json           # física (≈0,4d)
```

Rode séries longas **fora da sessão do Claude** (`nohup ... &`) — no Mac elas
morriam junto com a sessão.
