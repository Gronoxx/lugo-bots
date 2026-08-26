# Lugo Bots — projeto de competição

Objetivo: vencer o **4º Campeonato Aberto de Lugo Bots**.
**Prazo de inscrição: 16 de agosto de 2026.**

Calendário oficial (lugobots.ai/tournaments):

| Fase | Data |
|---|---|
| Fim das inscrições | 16/ago/2026 |
| Partidas de classificação | 17/ago/2026 |
| Quartas de final | 27–28/ago/2026 |
| Semifinais | 25/set/2026 |
| Final e 3º lugar | 09/out/2026 |

---

## 1. Regras e números que importam

Valores extraídos do código oficial (`lugo4py/specs.py`) e confirmados em
replays do servidor.

| Parâmetro | Valor |
|---|---|
| Campo | 20000 × 10000 (x: 0–20000, y: 0–10000) |
| Gol | largura 3000 → y de 3500 a 6500 |
| Zona do gol | raio 1400 (adversário não entra) |
| Jogador | diâmetro 400, velocidade máx **100 d/turno** |
| Bola | diâmetro 200, velocidade máx **400 d/turno** |
| Desaceleração da bola | 10 d/turno², para quando ≤ 2 |
| Raio de contato bola-jogador | 300 |
| Goleiro | pulo 200 d/turno por **3 turnos, não interrompível** |
| Shot clock | 300 turnos |
| **Duração da partida** | **6000 turnos** |
| Janela de decisão | 50 ms por turno |
| Jogadores | 11 por time; abaixo de 6 conectados = W.O. |

> **Divergência da documentação:** o site indica 1200 turnos; o servidor real
> reporta `game_duration: 6000` no cabeçalho do replay. Vale o servidor.

### Regras de física com consequência tática

1. **O chute SOMA à velocidade atual da bola** (não substitui). Toques
   sucessivos mantendo contato aceleram a bola progressivamente — até ~240
   d/turno antes de ela escapar do raio de contato.
2. **Força do chute cai com o ângulo**: `0.5 + 0.5·((180−ang)/180)`. Chutar na
   direção do próprio movimento rende 100%; chutar para trás, 50%.
3. **A bola nunca sai**: quica nas bordas com a mesma velocidade. Passes de
   parede são legítimos e previsíveis.
4. **Integração trapezoidal** (descoberto medindo replays, não está na
   documentação): o avanço da bola em um turno é `v − BALL_DECEL/2`, não `v`.
   Aplicando isso, o erro de previsão da posição da bola cai de 5,0d para
   **0,38d por turno** — praticamente exato. Como toda decisão de
   interceptação, passe e defesa depende de prever onde a bola estará, esta
   correção melhora tudo de uma vez. Reproduzir com `sim/validate.py`.

---

## 2. Descobertas da análise física

Rodar `python3 analysis/report.py` reproduz tudo isto.

**Alcance do chute.** Um chute máximo percorre **8200d em 40 turnos** — apenas
41% do comprimento do campo. Do meio-campo ao gol são 10000d: **não alcança**.
Para a bola chegar ao gol com velocidade ≥200 d/turno, é preciso estar a no
máximo **6100d**. Isto define a zona de finalização real.

**Passar vence correr.** A bola é 4× mais rápida que o jogador em velocidade
de pico. Cobrir 5000d: ~31 turnos de bola contra 50 correndo. Quanto maior a
distância, maior a vantagem do passe.

**O goleiro é MENOS vulnerável do que parecia** (correção de uma afirmação
anterior deste documento). `GOALKEEPER_SIZE = PLAYER_SIZE * 2.3 = 920`, não 400:
o goleiro é 2,3× maior que um jogador de linha, e a meia-extensão efetiva contra
a bola é (920+200)/2 = **560**, não os 300 do `TOUCH_RADIUS`. Em `lugo4py` essa
constante tem uma vírgula final que a torna uma *tupla* — sinal de que ninguém no
ecossistema Python jamais a usou, nós inclusive.

Além disso, medido em replay: o servidor **acelera o goleiro até 200 d/turno
perto de bola rápida mesmo sem ordem de pulo** (144 ocorrências em uma partida),
e o mantém **preso à linha do gol** (x ∈ {0, 20000} em 12.058 snapshots) — pedir
posição com x deslocado só desperdiça o orçamento de velocidade em y.

Consequência tática: a janela de chute direto contra goleiro centrado é estreita,
e finalizar de longe é desperdício. Vale deslocar o goleiro antes de finalizar.

**O campo é esparso.** 22 jogadores em 200M d² → raio livre médio de ~1700d por
jogador, contra 300d de raio de contato. Há muito espaço: manter formação abre
linhas de passe que o adversário não consegue cobrir.

---

## 3. O baseline é fraco (e por quê)

Partida completa `the-dummies` × `the-dummies` no servidor real:

- **placar 0 × 0** em 6000 turnos
- bola **75% do tempo no meio-campo**
- bola solta em 94% dos turnos

Motivo: o bot de referência manda **todos os 11 jogadores atrás da bola**
(`make_order_move_max_speed(ball_position)` em todos os estados). O resultado é
um enxame no centro que ninguém consegue romper.

**Nossa contramedida:** só os 2 jogadores que chegam primeiro vão à bola; os
outros 9 mantêm uma formação que desliza com o jogo.

### Resultados no servidor real (partidas completas, 6000 turnos)

| Partida | Nosso lado | Placar |
|---|---|---|
| `the-dummies` × `the-dummies` | — | 0 × 0 |
| nosso bot × `the-dummies` | HOME | **6 × 0** |
| nosso bot × `the-dummies` | HOME | **4 × 0** |
| `the-dummies` × nosso bot | AWAY | **3 × 0** |

3 vitórias em 3, 13 gols a 0, ganhando dos dois lados do campo. A posição média
da bola fica no campo adversário (x≈13370 jogando como HOME, contra x≈10504 do
baseline consigo mesmo), ou seja: dominamos território, não só o placar.

---

## 4. Concorrência

Bots públicos de participantes analisados (`rivals/`):

| Repositório | Nível |
|---|---|
| `Participante1/lugo-bot` | mais avançado: distância ponto-segmento para linha de passe, cálculo de rebote, formações por fase (extreme defensive → normal) |
| `Participante2/BotParticipante2`, `Participante3/bot` | heurístico simples, derivado do template |
| `Participante5/<ferramenta de formações>` | ferramenta de formações (não é bot) — útil como referência |

**Conclusão: ninguém usa aprendizado.** O teto atual é heurística bem feita.
Um bot com física correta e otimização automatizada tem margem real.

---

## 5. Armadilhas do servidor (custaram horas — documentadas para não repetir)

1. **`starter.run(bot, on_join)`** exige o segundo argumento; sem ele o bot
   nem inicia.
2. **`inspector.is_ball_holder(player)`** exige o jogador como argumento. Sem
   ele, exceção a cada turno — e como o template envolve tudo em `try/except`,
   o bot fica silenciosamente parado.
3. **Posição inicial inválida** derruba o registro do jogador (e, com menos de
   11, o time perde por W.O.). Duas causas:
   - posição na metade adversária do campo (com 20 colunas: `Col <= 9`);
   - posição dentro do **círculo neutro central** (raio 1000 em torno de
     10000,5000) — por isso `Col 9 / Row 4` falha.
4. **O servidor faz panic** (nil pointer no `LocalFileWriter`) se o arquivo de
   `--record-path` já existir. Sempre apagar antes.
5. **`PYTHONUNBUFFERED=1`** no Dockerfile — sem isso os logs do bot não
   aparecem e qualquer erro fica invisível.
6. **`depends_on` não espera o servidor aceitar conexões.** O cliente lugo4py
   tem timeout fixo de 5s sem retry; sem uma espera ativa pela porta, parte do
   time não conecta.
7. **`make_order_kick` da lugo4py mira torto.** Ela compensa a velocidade da
   bola subtraindo `ball.velocity.direction`, mas `geo.normalize` escala para
   magnitude **100** enquanto a bola anda até 400 — e o vetor até o alvo tem
   magnitude igual à distância. Medido em 300 cenários: erro mediano de **19,2°**
   (p90 60,6°). Nosso `geometry.kick_to` resolve a física ao contrário e busca o
   melhor chute *alcançável*: mediana **1,3°**, a 0,28 ms. Como o defeito está na
   biblioteca, todo bot Python da competição o tem.
8. **A porta 5000 é ocupada pelo AirPlay Receiver no macOS.** Publicar o servidor
   em 5000 faz o cliente gRPC bater num servidor HTTP e falhar com erro confuso
   ("Expected SETTINGS frame... HTTP status 403"). Usar outra porta.

---

## 6. Estrutura do projeto

```
analysis/     física do jogo e parser de replays
  physics.py    modelo de física derivado das specs
  report.py     consequências táticas (rodar para ver os números)
  dribble_sim.py comparação carregar vs. tocar a bola
  replay.py     parser dos replays (base64+gzip por linha) e estatísticas
bot/          o bot de competição
  src/geometry.py  predição de bola, interceptação, linhas de passe
  src/tactics.py   formação dinâmica e atribuição de papéis
  src/my_bot.py    as cinco decisões (posse, apoio, defesa, disputa, goleiro)
bench/        bancada de partidas
  gen_compose.py  gera o compose com os 22 jogadores
  run_match.sh    roda uma partida e devolve o replay
  evaluate.py     série de partidas com troca de lados
  latency.py      mede o tempo de decisão por turno
sim/          simulador rápido (sem Docker/gRPC)
upstream/     repositórios oficiais lugobots
rivals/       bots públicos de participantes
```

### Modo do temporizador: use `wait`, não `rush`

Medição com configuração idêntica (mesmo bot, mesmo adversário, mesmo lado):

| modo | placares | desvio |
|---|---|---|
| `rush` | 6, 2 | 2,83 |
| `wait` | 4, 6, 5 | 1,00 |

Em `rush` o servidor avança assim que as ordens chegam; com 22 processos
disputando 4 núcleos, a ordem de chegada varia e injeta ruído — que é do nosso
laboratório, não do jogo. `wait` dá 50 ms a todos e é o que os composes dos
rivais usam (provavelmente o torneio também).

Apesar de a partida em `wait` demorar mais (~5 min contra ~2), ela exige tão
menos repetições que sai **mais barato no total**: detectar +1 gol de diferença
custa ~8 partidas (40 min) em `wait`, contra ~62 partidas (124 min) em `rush`.
Por isso `bench/run_match.sh` usa `wait` por padrão.

### Como rodar

```bash
# uma partida contra o baseline
cd bench && ./run_match.sh mybot:v1 lugobots/the-dummies-go:latest teste

# série com troca de lados
python3 evaluate.py --home mybot:v1 -n 2

# orçamento de tempo por turno (limite: 50ms)
../.venv/bin/python latency.py
```

---

## 7. Dados de treino: por que replay > vídeo

Levantamento das fontes de partidas:

| Fonte | Situação |
|---|---|
| Replays do servidor local | **ilimitados** — `--record-path` grava, `replay` reproduz. Formato: uma linha por evento, `base64(gzip(json))`, com estado completo de todos os 22 jogadores e da bola a cada turno |
| Partidas oficiais em lugobots.ai | visíveis em `/matches/<uuid>/watch`, mas os dados são carregados por JS autenticado; o bucket S3 não permite listagem |
| YouTube (Liga Nacional) | transmissões das rodadas |

**Sobre treinar a partir de vídeo:** é possível, mas é a pior das três opções
disponíveis, por três motivos concretos:

1. O vídeo é uma *projeção com perda* de um estado que já temos exato. Extrair
   posições de vídeo exige visão computacional e introduz erro de dezenas de
   unidades — enquanto o replay dá a posição exata, e nossa própria física
   prevê a bola com erro de 0,4d.
2. Não há rótulos de ação. O vídeo mostra o que aconteceu, não qual ordem cada
   bot enviou. Sem isso, aprendizado por imitação precisa inferir a ação, o que
   reintroduz erro.
3. Aprender a imitar bots que empatam 0x0 ensina a empatar 0x0. O teto do
   aprendizado por imitação é o nível de quem gerou os dados.

**Caminho escolhido:** self-play em simulação, onde geramos partidas ilimitadas
com estado e ação exatos, e a qualidade do adversário cresce junto com a nossa.
Os replays oficiais continuam úteis — mas como *fonte de validação da física* e
*análise do estilo dos adversários*, não como material de treino supervisionado.

---

## 8. Orçamento computacional: há muita folga

Medição do bot atual: **0,5 ms de decisão por turno**, num orçamento de 50 ms.
Sobram ~100× de margem. Isso permite algoritmos muito mais caros por turno
(busca em profundidade, rollouts, redes neurais pequenas) sem risco de perder
o turno — uma vantagem que a maioria dos participantes não explora.
