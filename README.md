# Lugo Bots — `killua-zoldyck`

Bot de futebol de robôs para o **4º Campeonato Aberto de Lugo Bots** (ago–out/2026),
escrito em Python sobre `lugo4py`. Este repositório guarda o bot, a bancada de
medição, os simuladores, a análise dos adversários e — principalmente — **o registro
honesto do que funcionou, do que não funcionou e por quê**.

Não passamos da fase de classificação. O documento explica exatamente onde o projeto
falhou, e o diagnóstico é mais interessante que o placar: **o bot não perdeu por falta
de engenharia, perdeu por medir a coisa errada durante duas semanas.**

> O README original, escrito no início do projeto (10/08), está preservado em
> `results/README_INICIAL_2026-08-10.md`.

---

## Índice

1. [Resultado final](#1-resultado-final)
2. [O jogo: regras e física que decidem tudo](#2-o-jogo-regras-e-física-que-decidem-tudo)
3. [Arquitetura: o bot como genoma](#3-arquitetura-o-bot-como-genoma)
4. [A bancada: como medimos](#4-a-bancada-como-medimos)
5. [A trajetória, fase a fase](#5-a-trajetória-fase-a-fase)
6. [As leis do projeto](#6-as-leis-do-projeto)
7. [Estratégia competitiva](#7-estratégia-competitiva)
8. [Análise dos adversários (a fase do metamorfo)](#8-análise-dos-adversários-a-fase-do-metamorfo)
9. [Armadilhas do servidor e do laboratório](#9-armadilhas-do-servidor-e-do-laboratório)
10. [Estrutura do repositório e como rodar](#10-estrutura-do-repositório-e-como-rodar)
11. [O que eu faria diferente](#11-o-que-eu-faria-diferente)

---

## 1. Resultado final

### Fase de classificação (os jogos que valeram)

| Adversário | Placar | Pontos | Observação |
|---|---|---|---|
| level-1 | **1 × 0** | 5 | 218 passes certos, **2 finalizações** — posse estéril |
| level-2 | **3 × 2** | 7 | 6 finalizações para 3 gols (50%!), mas eles chutaram **46 vezes** |
| level-3 | **0 × 0** | 3 | **o jogo da eliminação** — 6 finalizações contra 15, 76% do tempo no nosso campo |

**15 pontos e saldo 0 contra o level-3** — e o desempate do seeding é, na ordem:
saldo vs L3 → gols vs L3 → saldo vs L2. Zero gols no critério nº 1 é o que nos tirou.

### Depois da eliminação (desafios, com a versão que chegou tarde)

| Adversário | Placar | Finalizações | Leitura |
|---|---|---|---|
| level-3 | **1 × 0** | 5 × 34 | vitória sob cerco pesado |
| **BotAdversario7** (fora) | **4 × 2** | **26 × 8** | o mesmo bot tinha feito **8 × 0** no BotAdversario5 |

O 4 × 2 fora de casa contra o BotAdversario7 é a validação que não deu tempo de usar: **26
finalizações**, contra as 8 que a versão do torneio produzia. O desenho estava certo;
ele ficou pronto depois do jogo que importava, e as duas versões finais ficaram
presas em "On tests" na plataforma durante as horas decisivas.

### O erro central, em uma frase

Otimizamos o ataque contra o **level-1**, cujo goleiro **espalma** o chute de longe —
então o chute de longe virava rebote e gol, e o laboratório premiava volume de longe.
O goleiro do **level-3 segura**. Contra ele, o mesmo chute é uma doação limpa: zero
gol *e* zero rebote. A régua não estava errada por descuido; estava errada porque
media o adversário disponível, não o adversário que decidia a classificação.

---

## 2. O jogo: regras e física que decidem tudo

Valores extraídos do código oficial (`lugo4py/specs.py`) e **confirmados em replays
do servidor real** — em vários pontos a documentação diverge do servidor, e vale o
servidor.

| Parâmetro | Valor |
|---|---|
| Campo | 20000 × 10000 |
| Gol | largura 3000 (y de 3500 a 6500) |
| Zona do gol | raio 1400 — jogador de linha **não entra** (vale nos DOIS gols) |
| Jogador | diâmetro 400, velocidade máx **100 d/turno** |
| Bola | diâmetro 200, velocidade máx **400 d/turno** |
| Desaceleração da bola | 10 d/turno², para quando ≤ 2 |
| Raio de contato bola-jogador | 300 |
| Goleiro | tamanho **920** (2,3× um jogador), pulo 200 d/turno por 3 turnos não-interrompíveis |
| Duração | **6000 turnos** (o site diz 1200; o servidor manda) |
| Janela de decisão | 50 ms por turno |
| Regra de misericórdia | partida encerra com saldo **+10** |

### As cinco consequências físicas que moldaram o bot

1. **A integração é trapezoidal.** O avanço da bola num turno é `v − 5`, não `v`.
   Descoberto medindo replays, não está na documentação. Aplicando a correção, o erro
   de previsão da posição da bola cai de **5,0 d para 0,38 d por turno**. Como
   interceptação, passe e defesa dependem de prever a bola, essa linha melhora tudo
   de uma vez. Reproduz com `sim/validate.py`.

2. **O chute SOMA à velocidade atual da bola** (não substitui), e a força cai com o
   ângulo: `0.5 + 0.5·((180−ang)/180)`. Chutar na direção do próprio movimento rende
   100%; para trás, 50%. Toques sucessivos aceleram a bola progressivamente.

3. **O alcance máximo do chute é 8200 d em 40 turnos** — 41% do campo. Do meio-campo
   ao gol são 10000: **não alcança**. Para a bola chegar com velocidade ≥ 200, é
   preciso estar a no máximo ~6100. Isso define a zona de finalização real e é a
   razão de existir o parâmetro `dangerous_shot_range`.

4. **O goleiro é maior do que parece.** `GOALKEEPER_SIZE = PLAYER_SIZE * 2.3 = 920`,
   e a meia-extensão efetiva contra a bola é `(920+200)/2 = 560`. Em `lugo4py` essa
   constante tem uma vírgula final que a torna uma *tupla* — sinal de que ninguém no
   ecossistema Python jamais a usou. Além disso, medido em replay: o servidor
   **acelera o goleiro até 200 d/turno perto de bola rápida mesmo sem ordem de pulo**
   (144 ocorrências numa partida) e o mantém **preso à linha** (x ∈ {0, 20000} em
   12.058 snapshots).

5. **O campo é esparso.** 22 jogadores em 200 M d² → raio livre médio de ~1700 d por
   jogador, contra 300 d de raio de contato. Há muito espaço: manter formação abre
   linhas de passe que o adversário não cobre. É por isso que o baseline oficial
   (`the-dummies`, que manda os 11 atrás da bola) empata 0 × 0 consigo mesmo com a
   bola 75% do tempo no meio-campo — e por isso a primeira versão do nosso bot, que
   só manda os 2 mais próximos, já ganhava de 6 × 0.

### Uma descoberta de regra que valeu genes inteiros

**O kickoff é uma CORRIDA.** A bola fica solta no centro, os 22 jogadores são
teleportados para suas `init_position` e o primeiro toque acontece no turno reset+13.
Ganha quem tem posição inicial mais perto do centro — respeitando as duas restrições
(própria metade; fora do círculo neutro de raio 1000). Com `init_variant="race"`
(#10 a d=1500 do centro) passamos a **ganhar a posse em todo reinício**: contra um bot
da nossa classe, a taxa de vitória na corrida foi de 43% para **100%**.

---

## 3. Arquitetura: o bot como genoma

### As cinco decisões

O `lugo4py` chama um callback por estado. Todo o bot vive em cinco funções
(`bot/src/my_bot.py`, ~2000 linhas):

| Callback | Quando | O que faz |
|---|---|---|
| `on_holding` | temos a bola | finalizar → cruzar → passar → conduzir |
| `on_supporting` | companheiro com a bola | oferecer linha, correr ao rebote, acampar |
| `on_defending` | adversário com a bola | perseguir (2), marcar, cobrir, formar |
| `on_disputing` | bola solta | perseguir, emboscar a segunda bola |
| `as_goalkeeper` | goleiro | posicionar na linha, sair, distribuir |

Módulos de apoio: `geometry.py` (física, interceptação, `kick_to`), `tactics.py`
(formação dinâmica e papéis), `setplays.py` (reinícios), `planner.py` (planejador de
passe não-guloso), `carry.py`, `finish_play.py`.

### O genoma: todo comportamento novo nasce desligado

A decisão de projeto mais importante do repositório: **nenhuma mudança de
comportamento é escrita direto no código**. Toda ideia vira um parâmetro em
`bot/src/params.py`, com valor default que reproduz **exatamente** a versão anterior:

```python
DEFAULTS = {"dangerous_shot_range": 6000.0, "dc_floor": 0.52, ...}        # contínuos
STRUCTURE_DEFAULTS = {"shot_gate": "threshold", "def_camp": "off", ...}   # estruturais
BOUNDS = {"dangerous_shot_range": (2000.0, 8000.0), ...}                  # faixas legais
STRUCTURE_OPTIONS = {"shot_gate": ["threshold", "xg", "slack", "hybrid"], ...}
```

O genoma entra por `BOT_PARAMS` (JSON em variável de ambiente) ou por
`BOT_PARAMS_FILE` (usado na imagem de submissão). Consequências práticas:

- **A/B sem rebuild**: dois genomas na mesma imagem, só trocando a variável.
- **Rollback grátis**: desligar o gene devolve a versão anterior byte a byte.
- **Uma versão por adversário**: o regulamento permite trocar o *main release* entre
  jogos, e o mesmo binário vira um bot diferente por configuração.
- **Busca automática**: o GA em `bench/evolve.py` evolui os genes diretamente.

Ao final do projeto havia **~90 genes**. A versão publicada mais agressiva usa 36.

### A tríade de validação (obrigatória por commit)

Cada commit que adiciona um gene roda três portões:

1. **`bench/test_edge_cases.py`** — 140 combinações de estado-limite; nenhuma callback
   pode lançar exceção. Motivo: o template do `lugo4py` envolve tudo em `try/except`,
   então uma exceção não derruba o bot — ela o deixa **parado e silencioso**.
2. **`bench/decide_dump.py`** — reconstrói o inspector de cada snapshot de um replay e
   chama a função de decisão real, sob o `PYTHONPATH` da base e do worktree, e faz
   `diff`. Com os genes desligados o diff tem que ser **vazio** (função pura, imune ao
   não-determinismo do servidor).
3. **`bench/latency.py`** — média por turno bem abaixo dos 50 ms. Com todos os genes
   ligados o pior caso medido foi **2,7 ms**.

Existe um quarto portão informal, aprendido na dor: **provar que o gene DISPARA**.
Dois genes (`press_shadow`/`press_hold_mark` e `high_camp`) foram medidos como
"neutros" quando na verdade nunca tinham sido carregados ou nunca chegavam ao alvo
final. Desde então todo gene novo tem um teste que mostra a decisão mudando.

---

## 4. A bancada: como medimos

Metade do repositório é instrumentação. Cada ferramenta nasceu de um erro de medição
específico.

| Ferramenta | O que responde |
|---|---|
| `bench/run_match.sh` + `gen_compose.py` | uma partida completa (23 containers) e o replay |
| `bench/escada.py` | teto ofensivo: N partidas, mediana/média de gols, knockout configurável |
| `bench/ab_transition.py` | A/B de dois braços contra o mesmo adversário, com painel defensivo |
| `bench/ab_selfplay.py` | **a régua forte**: nosso bot contra si mesmo, só os genes mudam |
| `bench/decide_dump.py` | portão de inércia no nível da decisão |
| `bench/shot_distance_curve.py` | conversão × distância do chute |
| `bench/chance_origin.py` | de onde nasce a chance curta (rebote? roubo alto? construção?) |
| `bench/shot_veto.py` | por que o bot **não** chutou (fora de alcance / linha bloqueada / folga do GK) |
| `bench/cerco_report.py` | painel com gols, sofridos e **chutes curtos** (métrica densa) |
| `bench/camp_check.py` | onde estão nossos corpos quando a bola está no nosso campo |
| `bench/siege_probe.py` | qual adversário local reproduz a geografia do adversário real |
| `sim/scene_extract.py` + `scene_runner.py` | reconstrói lances do **vídeo** da plataforma e re-simula |
| `sim/match_profile.py` | perfil macro de uma partida oficial por visão computacional |
| `analysis/scrape_profiles.py` | raspa placares e as 12 estatísticas por partida do site |

### Três lições de metodologia que valem mais que as ferramentas

**(a) `wait`, não `rush`.** Com configuração idêntica, `rush` deu placares 6 e 2
(desvio 2,83) e `wait` deu 4, 6, 5 (desvio 1,00). Em `rush` o servidor avança assim
que as ordens chegam; sob contenção de 22 processos, a ordem de chegada varia e
injeta ruído do *laboratório*, não do jogo. Detectar +1 gol de diferença custa ~8
partidas em `wait` contra ~62 em `rush` — `wait` demora mais por partida e sai **mais
barato no total**.

**(b) O `wait` não é determinístico.** A mesma imagem contra o mesmo adversário
diverge na trajetória da bola já no turno ~83. Isso **invalida** qualquer portão do
tipo "0 diferenças no replay". Daí o `decide_dump.py`: prova inércia no nível da
função pura, e o efeito do gene só se mede por estatística.

**(c) Métrica densa vence métrica esparsa.** Gol é raro e ruidoso (desvio ~1 gol por
partida). A mesma pergunta respondida por **chutes curtos por jogo** (dezenas por
partida) precisa de muito menos partidas para o mesmo poder estatístico. Todas as
decisões finais do projeto foram tomadas em cima de métricas densas, com o placar
apenas confirmando.

---

## 5. A trajetória, fase a fase

### Fase 0 — Física e baseline (v1 → v9)

Reimplementar a física a partir das specs, medir contra replays reais, e explorar a
fraqueza estrutural do baseline (todos atrás da bola). Resultado imediato: 3 vitórias
em 3 contra `the-dummies`, 13 gols a 0, dominando território dos dois lados.

Aqui nasce também o `geometry.kick_to`: a `make_order_kick` da `lugo4py` **mira
torto** — ela compensa a velocidade da bola subtraindo um vetor normalizado para
magnitude 100 enquanto a bola anda até 400. Medido em 300 cenários: erro mediano de
**19,2°** (p90 60,6°). Nossa versão resolve a física ao contrário e busca o melhor
chute *alcançável*: mediana **1,3°**, em 0,28 ms. Como o defeito está na biblioteca,
**todo bot Python da competição o tem**.

### Fase 1 — Evolução automática: o primeiro "não"

GA elitista (μ+λ) sobre 10 genes ofensivos, fitness = saldo vs level-1. **47 genomas,
~400 partidas, 5 horas.** Veredito: **nenhuma melhora sobre a v9.**

O líder da busca (saldo 1,42 em `rush`) regrediu para **+0,38** quando validado em
`wait`, contra **+0,88** da própria v9 — **winner's curse** puro, capturado pela
validação. A triagem estrutural mostrou que até a ordem de decisão da v9
(`shoot_pass_carry`) era conclusivamente melhor que a alternativa.

Lição registrada na época e confirmada depois: *ganho futuro exige lógica nova, não
ajuste do que já existe*. E o gargalo real não era a busca — era a **avaliação**:
com desvio de ~0,9 gol por partida e placares comprimidos, distinguir ganhos menores
que 0,6 gol exige dezenas de partidas por genoma.

### Fase 2 — Heurísticas dirigidas

Plano de itens numerados, cada um implementado como gene e medido. O placar honesto:
condução por toque **ganhou**; passe de troca **piorou**; chasers adaptativos, neutro;
gate de chute por folga temporal, neutro; modelo de xG treinado sobre os próprios
chutes **não superou a heurística** e ficou desligado.

### Fase 3 — "Quando passar" e a régua de self-play

A pergunta era boa: quando o portador deve passar em vez de conduzir? Três
componentes foram implementados — status por jogador, um planejador não-guloso de
passe (MPC de uma perna) e tática por estado de jogo.

O problema era medir. Contra oponente fraco tudo era ruído. A solução foi a régua que
mudou o projeto: **self-play**. Nosso próprio bot é o adversário forte que não
existia localmente; os dois lados usam a mesma imagem e só os genes mudam. Disputa
competitiva ⇒ baixa variância ⇒ sinal limpo.

O veredito foi brutal e útil:

| variante | saldo/jogo (self-play) | veredito |
|---|---|---|
| controle base × base | −0,15 ± 0,17 | régua válida, sem viés de lado |
| **status sozinho** | **+0,40 ± 0,18 (z = 2,18)** | **ganha** ✓ |
| planejador sozinho | **−2,65 ± 0,32 (z = −8,32)** | perde muito ✗ |
| combo | −2,58 ± 0,33 | perde |

O planejador — a peça mais sofisticada da fase — **piorava o bot**. Para um bot que
dribla bem, passar mais cria perdas de posse e abre mão do tempo de condução que
vence. Ficou no repositório, desligado, com o motivo documentado.

### Fase 4 — Fastsim e RL em JAX: a aposta que foi engavetada

A hipótese: se a avaliação é o gargalo, um simulador rápido destrava tudo — GA denso
e, depois, aprendizado por reforço.

O que foi construído e **funciona**:

- `sim/fastsim.py` — servidor reimplementado em Python. Física de voo livre da bola
  com erro **mediano de 0,4 d** contra replays reais.
- `rl/bridge/` — ponte que roda o `my_bot.py` **exato** dentro do fastsim, via um
  `GameSnapshotInspector` real, sem Docker nem gRPC.
- `rl/jax/step.py` — o mesmo simulador **vetorizado em JAX**: **45 M env-steps/s
  (~7500 partidas/s)** numa GTX 1660S, com física idêntica ao escalar (0,00 d de
  diferença).
- `rl/envs/` — ambiente multiagente CTDE (observação egocêntrica canonizada de 109
  dims + global de 96, ação MultiDiscrete).
- `rl/train/` — MAPPO com ator compartilhado e crítico central, BC, self-play, eval.

E o RL **aprendeu futebol de verdade** — depois de três bugs sequenciais que
mascaravam um ao outro, todos com o mesmo sintoma (posse 0%, nenhum gol):

1. **Reward 100% PBRS** (`γΦ' − Φ`) é invariante à política → vantagem ≈ 0. Sem
   gradiente útil.
2. **A exploração destrói a posse.** A cabeça de chute tem 17 opções; sob exploração
   uniforme o portador chuta em ~94% dos turnos e larga a bola no mesmo turno.
   "Segurar" é indescobrível por acaso. Fix: **prior de inicialização** no ator
   (viés para não-chutar e para pegar).
3. **Reward farmável por inação** — o pior. Com avanço-da-bola incondicional, a
   política ótima era empurrar a bola para frente **uma vez** e colher recompensa
   parada. Diagnóstico: posse 0,04%, jogador a 1550 d da bola, bola parada 80% do
   tempo. Fix: shaping baseado em **esforço do agente** e **não-farmável parado**.

Com o reward corrigido: posse **0% → 73%**, e o melhor agente batia todos os
baselines internos (40 × 0 vs estático, +6,45 vs o oponente "booting").

**Por que foi engavetado assim mesmo.** O teto era estrutural, provado nos dois
caminhos:

- O `my_bot` (v9) **não roda no loop JAX** — a heurística é um objeto Python, não uma
  função vetorizável. Então o RL só treina contra oponentes JAX-nativos.
- **Clonar o v9 por BC falhou** (distribution shift clássico: o clone tinha 0% de
  posse contra estático).
- Construí um oponente heurístico JAX **forte** para elevar o teto: ele bate o melhor
  RL por 6,4 × 0 — e **ele mesmo perde do v9 por 0 × 12 e 0 × 19**.

Logo: nenhum oponente disponível dentro do JAX chega perto do v9, e o RL platôa muito
abaixo dele, **por construção**. O melhor RL contra o v9 no fastsim: **0 × 8**.

A infraestrutura foi preservada em *mothball*, com **condições objetivas de
reabertura** escritas (`results/RL_MOTHBALL_CONDICOES.md`): portar os fixes de
fidelidade para o passo JAX **e** ter um oponente forte fiel no loop. Nada foi
apagado; nada roda.

> O que o RL entregou fora do treino: o diagnóstico de que o gargalo competitivo era
> **criação e finalização contra defesas fortes** (~75% dos chutes salvos) — que é
> exatamente o que a heurística confirmaria duas semanas depois — e a ponte escalar
> `my_bot ↔ fastsim`, reutilizada nas cenas simuladas.

### Fase 5 — O 0 × 3 do BotAdversario1 e o programa tático

A primeira derrota séria para um bot de participante. A forense do replay mostrou que
os três gols tinham a mesma assinatura: **rebote não-limpo, condução para dentro do
pressing, e passe de saída interceptado**. Nasce daí o "programa tático": ~30 genes
novos (todos desligados por default), a bancada de sparring que reproduz o padrão do
BotAdversario1 localmente, e a linha de versões v3 → v4 → v5 → v6.

**A v5 foi reprovada por um bug de contador.** Ela perdeu 0 × 1 do level-3 — a
primeira derrota histórica para um bot oficial. Causa: o contador de "nossos chutes"
somava passes longos, então 337 passes viraram "12 chutes" no primeiro minuto, o gate
travou e o bot deu **3 chutes na partida inteira** com 65% de posse. Disso nasceu a
**regra do exame**: nenhuma versão vira *main release* sem passar por um jogo de
plataforma antes.

**A v6 foi a melhor arma anti-goleiro do projeto.** O gene `shot_gate="hybrid"` usa
threshold perto (d ≤ 3200) e uma folga temporal calibrada no cap físico do goleiro
para longe — na retro-análise, negava 53 de 74 chutes longos estéreis. Resultado no
exame: **3 × 0 no level-3, conversão de 42,9% (3/7)** contra os 2,3% (1/44) da v4, e
a doação ao goleiro adversário caiu de 43 para 4.

### Fase 6 — O metamorfo: dissecar a elite

Dezesseis partidas de bots de elite analisadas quadro a quadro (vídeo + estatísticas
do site). A pergunta: **por que eles fazem 10 × 0 e nós fazemos 3 × 0?**

A resposta: existem **dois modelos opostos de goleada, e nós não executávamos
nenhum**.

- **BotAdversario2 = CERCO.** 8–9 jogadores permanentes no campo adversário formando um anel
  ("2-8"), 41–51 finalizações por jogo com conversão média (7–23%). A conversão vem
  da **insistência espacial**: cada defesa do goleiro cai num raio onde ele tem 2–3
  corpos. O 12º chute da sequência pega o goleiro fora de posição.
- **BotAdversario1 = PREDAÇÃO.** 3 zagueiros fixos no próprio fundo, 7 corpos altos, 9–12
  finalizações com conversão de **67–83%**. A fonte das chances é **predar o
  reinício**: gol → kickoff previsível do adversário → 6 jogadores em anel no círculo
  central → roubo em ~2 s → gol em ~5 s. Três a zero nos primeiros 23 segundos.

Diagnóstico nosso à época: 4–5 corpos no campo adversário, 7 finalizações, **1 corpo**
no rebote, e recuo no kickoff adversário. Éramos o modelo BotAdversario1 pela metade —
convertíamos bem e não fabricávamos situação.

Daí saiu a v7, com dez genes novos: `init_variant="race"`, `kickoff_blitz`,
`kickoff_race`, `swarm_rebound`, `outlet_press_detect`, `counter_press_window`,
`kickoff_shield`, `quina_entry`, `ot_press`.

### Fase 7 — Cenas simuladas: recriar os gols sofridos

Ideia do usuário, e a mais original do projeto. As partidas de plataforma **não têm
replay JSON** — só o vídeo MP4. Então:

1. `sim/scene_extract.py` reconstrói o estado (22 jogadores + bola, ~14 unidades por
   pixel) a partir do vídeo, com calibração do campo, identificação de time pela cor
   do anel e resolução da trajetória da bola por programação dinâmica;
2. `sim/scene_runner.py` recoloca os adversários como *ghosts* reproduzindo a
   trajetória real e roda o **nosso bot ao vivo** dentro do fastsim;
3. critério de aprovação: **não sofrer nenhum dos 13 gols reais.**

O pacote de genes derivado dessas cenas passou **130/130**.

### Fase 8 — A crise da margem

Jogo oficial contra o level-1: **1 × 0**, com 218 passes certos e **2 finalizações**.
No mesmo dia, o BotAdversario2 fez 10 × 0 e o BotAdversario11 5 × 0. Com só 8 vagas e desempate por
saldo, "vencer" não bastava.

A resposta foi subir a linha: `aggression_support`, `shift_x`, `pass_w_advance`,
`dangerous_shot_range` mais largo e portão de chute aberto. Efeito medido contra o
level-1: **1,44 → 3,58 gols por jogo, com 0,00 sofrido, 16 vitórias em 16**. Nasce a
v8 → v9 → **v10**, publicada com 38 genes.

Foi o melhor número do projeto até então. E foi a armadilha.

### Fase 9 — O 0 × 0 e a forense que explicou tudo

A v10 jogou contra o level-3 e fez **0 × 0** com 8 finalizações — enquanto a v6, com
metade dos genes, tinha feito 3 × 0 com 7. Aí o diagnóstico apareceu.

**A curva de conversão por distância** (217 chutes nossos, medidos):

| distância | chutes | gols | conversão |
|---|---|---|---|
| < 2000 | 36 | 19 | **52,8%** |
| 2000–2600 | 35 | 14 | 40,0% |
| 2600–3200 | 31 | 11 | 35,5% |
| 3200–3800 | 15 | 2 | 13,3% |
| 3800–4500 | 26 | 1 | 3,8% |
| **4500–6000** | **62** | 3 | **4,8%** |
| > 6000 | 12 | 1 | 8,3% |

**Cem dos 217 chutes da v10 saíam de mais de 3800 e valiam 5 gols.**

**A origem das chances** (`bench/chance_origin.py`):

| origem da posse | chances curtas/jogo | conversão |
|---|---|---|
| **rebote do goleiro deles** | **3,25** | 40,4% |
| roubo no terço deles | 0,56 | 44,4% |
| roubo no meio-campo | 0,31 | **80,0%** |
| construção do nosso campo | 0,19 | 66,7% |

**73% das nossas chances curtas nasciam de rebote do goleiro adversário.** E aí o
mecanismo fecha: contra o level-1, o chute de longe é *espalmado* → vira rebote →
vira gol. Contra o level-3, é *segurado* → não vira nada. O portão frouxo da v10 não
só desperdiçava o chute: **desligava a própria fábrica de chances**.

**A geografia** (visão computacional sobre o vídeo do 0 × 0, 946 amostras): 20,7% dos
nossos corpos no campo deles, 5,5% no terço final. O jogo inteiro no nosso campo — 66
roubadas nossas viravam 137 passes com **94,5% de acerto** dentro do nosso próprio
terço. Tínhamos o melhor acerto de passe da competição e o pior volume de finalização.
Causa no código: `_cover_position` mistura a formação com 30% do caminho bola → nosso
gol, e levava os atacantes de x ≈ 9200 para x ≈ 5300. **Não existia para quem sair.**

Daí os dois genes finais:

- **`def_camp`** — 1 a 8 jogadores com piso de avanço **independente da bola**, válido
  também defendendo. É o "2-8" do BotAdversario2 traduzido em parâmetro.
- **`outlet_risk`** — com o portador cercado no próprio campo e um receptor já
  adiantado, **dispensa os vetos de passe**. O BotAdversario1 goleia errando 31–41 passes por
  jogo: a bola longa perdida cai no campo deles, é o erro mais barato que existe.

Eles são **superaditivos**, o que confirma o mecanismo e não só o resultado:

| braço (n=12, vs level-1) | gols | sofridos | chances ≤3200 |
|---|---|---|---|
| v6 (base) | 1,33 | 0,00 | 3,2 |
| + `def_camp` | 2,08 | 0,25 | 6,0 |
| + `outlet_risk` | 1,33 | 0,08 | 3,7 |
| **os dois** | **2,83** | 0,33 | 6,0 |

O `outlet_risk` sozinho não vale nada — não há para quem passar. Com o acampado, vale
+0,75.

### Fase 10 — A escada de agressividade, e o relógio

Com o mecanismo entendido, a última sessão foi uma escada de risco crescente, medida
em 8 a 16 partidas por degrau:

| versão | mediana | média | sofridos | finalizações | chances ≤3200 |
|---|---|---|---|---|---|
| v6 | 1,0 | 1,33 | 0,00 | 4,2 | 3,2 |
| v11 (forma 4-6) | 5,0 | 5,38 | 0,44 | 14,6 | 12,8 |
| 2-8 + linha máxima | 5,5 | 6,00 | 0,50 | 15,9 | 14,4 |
| + fábrica de rebote | 7,0 | 6,30 | 0,90 | 19,3 | — |
| **+ cascata de reinício** | **7,0** | 6,50 | **0,12** | **20,5** | — |
| **v14** (+ arco apertado) | **7,0** | **7,10** | 0,25 | até 35 | — |

Dois achados dessa escada:

- **O extremo não é o ótimo.** O braço com *todos* os parâmetros no teto das faixas foi
  o pior de todos: mediana caiu para 4,5 e os sofridos dobraram.
- **A cascata de reinício melhora ataque e defesa juntos.** Ganhar a corrida de todo
  kickoff tirou do adversário a posse que ele teria de graça depois de cada gol nosso:
  sofridos caíram de 0,90 para **0,12** enquanto as finalizações subiam.

A v14 mediu **7,10 gols de média, mediana 7, nenhuma partida abaixo de 5** contra uma
régua mais dura que o level-3 — e depois ganhou de 4 × 2 fora de casa do BotAdversario7, com
26 finalizações. Ela ficou pronta no dia seguinte ao jogo que valia; as versões v11 e
v12 ficaram **2 h e 50 min presas em "On tests"** na plataforma durante a janela
decisiva. A imagem publicada foi testada localmente nesse intervalo: conectava 11 de
11 jogadores e ganhava de 9 × 0 como visitante — o travamento não era nosso.

---

## 6. As leis do projeto

Regras empíricas que o projeto descobriu e depois usou como filtro. Cada uma custou
partidas.

### A lei da passividade (6 confirmações)

**Toda mudança que tira um corpo do jogo ofensivo para melhorar a defesa acaba
custando mais gols do que economiza.** Apareceu em seis formas distintas:

1. Recuar a linha inteira em bola disputada.
2. Adicionar mais marcadores fixos.
3. Escalonar zagueiros (`cb_stagger`): os gols sofridos **dobraram**, porque o
   substituto chega depois do zagueiro trocado e a pressão efetiva fica mais lenta.
4. Fechar o corredor central no pós-reinício.
5. Vetos de passe mais conservadores.
6. **A composição** — a forma mais traiçoeira. Vinte e seis genes, **cada um aprovado
   sozinho**, quando ligados juntos drenaram o corpo ofensivo: gols de 1,81 para 0,94,
   finalizações de 4,88 para 2,38, e os sofridos "perfeitos" em 0,06. Inanição
   clássica: o bot ficou ótimo em não perder e incapaz de ganhar. Só uma bisseção em
   três blocos localizou os culpados.

Consequência prática: todo gene defensivo passou a ter **critério de morte
pré-declarado** — se os gols pró caírem, o gene é rejeitado por melhor que fique a
defesa.

### A régua errada (a lei mais cara)

**Um laboratório mede o adversário que ele tem, não o adversário que decide o
resultado.** Contra o level-1 o ganho de +148% em gols era real — e metade dele vinha
de um canal (chute de longe → rebote) que vale **zero** contra goleiro de elite.

O antídoto que faltou: sempre que a métrica de laboratório subir muito, **perguntar
por qual mecanismo**, decompor o ganho por canal, e checar se aquele canal existe
contra o adversário-alvo. Foi exatamente o que a `chance_origin.py` fez — tarde
demais.

### Winner's curse

O líder de qualquer busca com poucas repetições é o sortudo, não o melhor. O campeão
do GA (1,42 em `rush`) virou +0,38 quando validado. **Nunca acreditar num número da
busca sem revalidar com N adequado**, e desconfiar por princípio de qualquer braço com
n pequeno na liderança.

### Piso de ruído

Medindo o *mesmo* genoma cinco vezes com 16 partidas cada, os resultados foram 4,44 /
3,88 / 3,12 / 3,81 / 2,94 — desvio de ±0,75 gol. Durante um período inteiro do
projeto, todos os experimentos estavam **abaixo do piso de ruído**, e eu estava lendo
sinal em ruído.

### Gene que não dispara

Um gene medido como "neutro" pode simplesmente nunca ter rodado. Aconteceu duas vezes:
uma por chave ausente em `STRUCTURE_DEFAULTS` (o carregador ignora chaves
desconhecidas **em silêncio**), outra porque outro branch sobrescrevia o alvo depois.
Desde então, todo gene precisa provar que muda a decisão antes de ser medido.

### Binário não é diagnóstico

A regra mais importante veio de uma cobrança do usuário: *"no momento você está
testando e descartando sem analisar de fato o que aconteceu no replay; só temos o
binário: funcionou ou não. Precisamos da justificativa."* Dessa cobrança saíram a
autópsia do portão de chute, a curva conversão × distância e a origem das chances —
ou seja, todo o diagnóstico que acabou explicando o projeto inteiro. **Um experimento
que só devolve "não funcionou" desperdiçou a partida.**

---

## 7. Estratégia competitiva

### O que o regulamento premia

- **1ª fase (seeding)**: os inscritos são desafiados pelos bots oficiais.
  Pontos: level-3 V=8/E=3, level-2 V=7/E=3, level-1 V=5/E=1.
- **Desempate, nesta ordem**: saldo vs L3 → gols vs L3 → saldo vs L2 → gols vs L2 →
  saldo vs L1 → data de inscrição.
- **2ª fase**: mata-mata, jogo único, e o **melhor seed tem a vantagem do empate**.
- **A versão pode ser trocada a qualquer momento**, inclusive durante o torneio.

Três consequências que guiaram tudo:

1. **Vencer não basta — o critério é goleada.** Foi por isso que o 1 × 0 contra o
   level-1 disparou a fase da margem.
2. **Uma versão por adversário é legal e vantajosa.** O mesmo binário, genoma
   diferente: volume contra goleiro fraco (level-2), qualidade contra goleiro de elite
   (level-3), defesa e empate no mata-mata.
3. **Seedar acima do rival transforma o 0 × 0 em vitória prática**, o que dá valor a
   um gene de "proteger o empate" ligável antes de um jogo específico.

### A regra do exame

Depois da v5 ser reprovada em jogo oficial por um bug que o laboratório não pegava,
passou a valer: **nenhuma versão vira main release sem passar por um jogo de
plataforma antes**, e a main é revertida se o exame reprovar. A quota de 5 desafios
por 24 h virou um recurso escasso a ser orçado.

### O mapa dos adversários oficiais

Descoberto tarde, e é a informação mais acionável do projeto:

| adversário | defesa do goleiro dele | como se ganha |
|---|---|---|
| level-1 | ~83% | difícil de golear; espalma longe (gera rebote) |
| **level-2** | **35–47%** | **alvo mole** — volume resolve (o BotAdversario5 fez 9 × 0 e 8 × 1) |
| level-3 | segura limpo | **filtro de qualidade** — só chance curta entra |

O BotAdversario5, apontado por "ter subido muito a quantidade de gols", fez **9 × 0 e 8 × 1
no level-2**, 3 × 0 no level-1 — e **perdeu de 0 × 1 para o level-3**. Ele não
descobriu um truque: jogou contra o adversário fácil.

---

## 8. Análise dos adversários (a fase do metamorfo)

Relatórios completos em `results/METAMORFO_2026-08.md` e nos dois eixos.

| bot | modelo | números vs level-3 |
|---|---|---|
| **BotAdversario3** | muralha vertical que vive de devoluções | média **9,33** gols |
| **BotAdversario1** | predação de reinício, 3 fixos + 7 altos | média 6,67; **10 × 0 com 12 finalizações (83% de conversão)** |
| **BotAdversario2** | cerco 2-8, anel de rebote | 12 × 2 com **51 finalizações** |
| **BotAdversario4** | cerco com volume variável | 17 finalizações → 9 gols; 70 → 11 |
| **BotAdversario5** | verticalidade caótica (47–57% de acerto de passe) | **0 × 1** — o cerco não fura o L3 |
| **nós (v6)** | conversão alta, volume baixo | 3 × 0 com 7 finalizações (42,9%) |

Duas observações de scouting que mudaram decisões:

- **O BotAdversario2 evolui entre jogos.** Em dois dias passou de 0 × 0 para 5 × 0 contra o
  BotAdversario1, com a posse líquida subindo de 38,8% para 51,2%.
- **Contra a muralha, volume é doação.** Nosso 3 × 7 contra o BotAdversario3: 34 chutes, 32
  deles defendidos. O contra-modelo é **inanição** — posse paciente e chute seletivo —,
  e é o que o BotAdversario6 usou para segurar um 0 × 0.

---

## 9. Armadilhas do servidor e do laboratório

Cada item aqui custou tempo real. Estão documentados para não se repetirem.

### Servidor e biblioteca

1. **`starter.run(bot, on_join)`** exige o segundo argumento; sem ele o bot nem inicia.
2. **`inspector.is_ball_holder(player)`** exige o jogador. Sem ele, exceção a cada
   turno — e como o template envolve tudo em `try/except`, o bot fica **parado em
   silêncio**.
3. **Posição inicial inválida derruba o registro do jogador** (e com menos de 11 o time
   perde por W.O.). Duas causas: posição na metade adversária, ou dentro do círculo
   neutro central (raio 1000).
4. **O servidor faz panic** (nil pointer no `LocalFileWriter`) se o arquivo de
   `--record-path` já existir. Sempre apagar antes.
5. **`PYTHONUNBUFFERED=1`** no Dockerfile — sem isso nenhum erro do bot aparece.
6. **`depends_on` não espera o servidor aceitar conexões.** O cliente `lugo4py` tem
   timeout fixo de 5 s sem retry; sem espera ativa pela porta, parte do time não
   conecta e a partida é perdida.
7. **`make_order_kick` mira torto** (19,2° de erro mediano) — ver Fase 0.
8. **A porta 5000 é ocupada pelo AirPlay no macOS**, e o erro resultante é enganoso.

### Laboratório

9. **Imagens Docker não atravessam arquiteturas.** Números de arm64 (Mac) não
   transferem para amd64 (Linux): a mesma v9 dava 2,50 gols no Mac e 0,78 no Linux.
10. **`docker-compose` recusa nome de projeto com maiúscula.** Custou 64 partidas numa
    madrugada e mais 16 no último dia. Hoje o `escada.py` normaliza a tag sozinho.
11. **`docker network prune` em paralelo com partidas subindo mata as partidas** — o
    prune remove a rede recém-criada antes de o compose subir os containers.
12. **`pkill -f <padrão>` mata o próprio shell** quando o padrão aparece na linha de
    comando dele. Duas filas foram perdidas assim; a forma segura é `pkill -x python3`.
13. **`params.P` é global**, carregado uma vez no import. Dois genomas não jogam no
    mesmo processo — o que impediu o A/B genoma-vs-genoma dentro do fastsim.

---

## 10. Estrutura do repositório e como rodar

```
bot/                    o bot de competição
  src/my_bot.py           as cinco decisões (~2000 linhas)
  src/params.py           ~90 genes: DEFAULTS, STRUCTURE_DEFAULTS, BOUNDS
  src/geometry.py         física, interceptação, kick_to
  src/tactics.py          formação dinâmica, papéis, acampamento
  src/setplays.py         reinícios (corrida, blitz, anel)
  src/planner.py          planejador de passe não-guloso (desligado)
  genome_*.json           os genomas de cada versão publicada
  Dockerfile.submit       imagem de submissão (embute o genoma)

bench/                  a bancada de medição
  run_match.sh            uma partida (23 containers) → replay
  escada.py               teto ofensivo (mediana de gols em N partidas)
  ab_transition.py        A/B com painel defensivo
  ab_selfplay.py          a régua forte
  evolve.py               GA sobre os genes
  decide_dump.py          portão de inércia no nível da decisão
  test_edge_cases.py      140 combinações de estado-limite
  latency.py              orçamento de 50 ms por turno
  chance_origin.py        de onde nascem as chances curtas
  shot_distance_curve.py  conversão × distância
  shot_veto.py            por que o bot não chutou
  cerco_report.py         painel de gols/sofridos/chutes curtos
  push_version.sh         build + verificação do genoma DENTRO da imagem + push

sim/                    simuladores e visão computacional
  fastsim.py              servidor reimplementado (erro mediano 0,4 d)
  scene_extract.py        vídeo da plataforma → estado dos 22 + bola
  scene_runner.py         re-simula o lance com o nosso bot ao vivo
  match_profile.py        perfil macro de uma partida oficial

rl/                     aprendizado por reforço (mothball)
  jax/step.py             sim vetorizado, 45M steps/s
  envs/                   ambiente multiagente CTDE
  train/                  MAPPO + BC + self-play
  eval/                   duelos e adaptador de deploy

analysis/               física, parser de replays, raspagem do site
results/                todos os relatórios e dossiês
rivals/                 bots públicos de participantes
```

### Comandos

```bash
# uma partida contra o baseline
cd bench && ./run_match.sh mybot:qp lugobots/level-1:latest teste

# teto ofensivo de um genoma (16 partidas, modo da plataforma)
python3 bench/escada.py --genome bot/genome_v14_best.json --n 8 --mode wait

# A/B de um gene contra a régua forte
python3 bench/ab_selfplay.py --test '{"def_camp":"on"}' --reps 16

# a tríade obrigatória por commit
cd bench && python test_edge_cases.py && python latency.py
PYTHONPATH=bot/src:analysis python bench/decide_dump.py <replay.json>

# publicar uma versão (verifica o genoma dentro da imagem antes de empurrar)
bash bench/push_version.sh bot/genome_v14_best.json v14
```

### Documentos de referência

| Arquivo | Conteúdo |
|---|---|
| `results/REFERENCIA_LUGO.md` | referência verificada do ambiente (dados + física) |
| `results/PROGRAMA_TATICO_2026-08.md` | dossiê de versões, travas e vereditos |
| `results/METAMORFO_2026-08.md` (+ eixos A e B) | dissecação dos adversários de elite |
| `results/FORENSE_L3_2026-08-20.md` | a autópsia do 0 × 0 |
| `results/FORENSE_10x0.md` | geometria do chute de alta conversão |
| `results/PLANO_RL_FASTSIM.md` | o plano de RL; `RL_MOTHBALL_CONDICOES.md`, o encerramento |
| `results/HANDOFF_QUANDO_PASSAR.md` | a régua de self-play e o veredito do planejador |
| `results/README_INICIAL_2026-08-10.md` | o README original (física, baseline, concorrência) |

---

## 11. O que eu faria diferente

1. **Medir contra o adversário que decide, desde o primeiro dia.** O level-2 e o
   level-3 só existem na plataforma, com quota de 5 jogos por dia. Isso não é um
   impedimento — é um orçamento a ser gasto com disciplina desde o começo, e foi gasto
   tarde e mal. Um único desafio contra o level-3 por dia, desde a primeira semana,
   teria exposto a curva de conversão muito antes.

2. **Decompor todo ganho por mecanismo antes de comemorar.** O salto de 1,44 para 3,58
   gols parecia progresso e era metade artefato. A pergunta "**por qual canal?**"
   deveria ser obrigatória junto com "quanto?".

3. **Construir a `chance_origin.py` no início, não no fim.** Saber que 73% das chances
   vinham de rebote do goleiro adversário mudaria todas as decisões anteriores —
   inclusive teria antecipado que um goleiro que *segura* zera a fábrica inteira.

4. **Tratar a fila da plataforma como parte do prazo.** Publicar duas horas antes do
   jogo não é publicar a tempo. A janela de validação é um recurso do adversário.

5. **Ter engavetado o RL uma semana antes.** A decisão de parar foi correta e bem
   documentada, mas os sinais (o v9 não roda no loop JAX; BC falha) estavam
   disponíveis muito antes de o teto estrutural ser provado com um oponente forte.

6. **Manter uma versão de segurança sempre validada.** Quando as duas versões boas
   travaram nos testes, a main era uma versão comprovadamente ruim contra o level-3
   (0 × 0) enquanto uma comprovadamente boa (v6, 3 × 0) estava `Ready` e disponível.
   A troca existia como opção e não foi feita a tempo.

---

## Créditos

Projeto de Gustavo (@Gronoxx), desenvolvido em pareamento com Claude (Anthropic)
via Claude Code. As decisões estratégicas, o desenho dos experimentos e várias das
ideias centrais — a régua de self-play, as cenas simuladas reconstruídas de vídeo, a
exigência de justificativa forense em vez de resultado binário — vieram do usuário; a
implementação, a medição e os relatórios foram construídos em conjunto.
