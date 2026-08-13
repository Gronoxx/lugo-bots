<!-- Referência definitiva do ambiente Lugo. Gerada por workflow multiagente
     (mineração do lugo4py + medição contra 221 replays reais), ago/2026.
     SUPERSEDE results/DADOS_DA_PARTIDA.md (que tinha o deslocamento/turno errado). -->

# Referência Técnica — Ambiente Lugo Bots (futebol 2D multiagente)

Reunião editada dos quatro blocos de pesquisa numa referência única. Convenção de marcação preservada em cada item:
**[AUTORITATIVO: specs/protobuf]** = lido do código/descriptor instalado · **[MEDIDO: replay, N]** = confirmado em replays reais · **[INFERIDO]** = modelo derivado/validado pelo time · **[DESCONHECIDO]** = não presente nas fontes deste ambiente.

Fontes canônicas (todas absolutas):
- SDK: `<caminho local>` (`src/`, `protos/`, `mapper/`)
- Física do time: `<caminho local>`, `<caminho local>`, `bot/src/finishing.py`
- Parser + replays: `<caminho local>`, `<caminho local>` (221 arquivos)

**Fato transversal de serialização** (confirmado em replays): protobuf→JSON **omite campos com valor default** (`x=0`, `side=HOME=0`, `score=0`, `number=0`, `state=WAITING=0`, `turn=0`, `speed=0`). No runtime gRPC as sub-mensagens **nunca são `None`** — retornam a instância default. Logo `get_ball_holder()` nunca é `None`: sem dono retorna um `Player` com `number == 0` (é assim que o SDK detecta "bola livre"). Fonte: `analysis/replay.py:6-11`, `src/define_state.py:38`. **[AUTORITATIVO: código + MEDIDO]**

**Estrutura do replay** [MEDIDO]: há **2 snapshots por turno** (transições `LISTENING`/`PLAYING`), com estado físico **idêntico** — deduplica-se por `turn`. A velocidade vem como `direction` (vetor **escalado a magnitude 100**, não unitário-1) + `speed` (escalar); vetor real = `unit(direction)·speed`. Os replays **NÃO registram as ordens** (`kick`/`move`) — só eventos `game_snapshot`, `state_change`, `new_player`, `lost_player`, `goal`, `game_over`. Consequência estrutural: a velocidade de chute *pedida*, o fator de ângulo e a resolução do `catch` são **inobserváveis** nestes replays.

---

## 1. Sistema de coordenadas e orientação

**[AUTORITATIVO: specs]** Campo 20000×10000 d (`MAX_X_COORDINATE=20000`, `MAX_Y_COORDINATE=10000`; `FIELD_WIDTH=20001`/`FIELD_HEIGHT=10001` são as contagens de coordenadas 0..20000 / 0..10000). Coordenadas de posição são **inteiras** (`Point{int32 x, int32 y}`).

Convenção de eixos **crítica e não intuitiva**: **y cresce para o NORTE** (para cima). Confirmado em `mapper/src/orientation.py` (NORTH=(0,+1), SOUTH=(0,−1)) e em `goal.py` (o poste "top" tem o **maior** y). **[AUTORITATIVO: código]**

- **Gol HOME em x=0** — defendido pelo time **HOME**; **gol AWAY em x=20000** — defendido pelo time **AWAY** (`mapper/src/direction.py:28-49`).
- Boca do gol: y ∈ [`GOAL_MIN_Y`=3500, `GOAL_MAX_Y`=6500], centro y=5000, largura `GOAL_WIDTH`=3000.
- HOME ataca para +x (gol AWAY em x=20000); AWAY ataca para −x (gol HOME em x=0).

```
  y=10000 (NORTE) ────────────────────────────────────────────────
        │                          . (centro y=5000)             │
  6500 ═╪══ ┐ top pole (y MAIOR)          |                 ┌ ══╪═ 6500
        ║   │                             |                 │   ║
  GOL   ║   │ boca do gol (3000 d)   círculo central        │   ║  GOL
  HOME  ║   │                     (FIELD_NEUTRAL_CENTER      │   ║  AWAY
  (x=0) ║   │                        = raio 1000)            │   ║ (x=20000)
  3500 ═╪══ ┘ bottom pole (y MENOR)       |                 └ ══╪═ 3500
        │                                 |                     │
     y=0 (SUL) ──────────────────────────────────────────────────
       x=0                        x=10000                   x=20000
   HOME defende ←── HOME ataca ──→        ←── AWAY ataca ──→ AWAY defende
```

**Espelhamento AWAY:** o `Mapper` opera na perspectiva do próprio time. `mirror_coords_to_away((x,y)) = (MAX_X−x, MAX_Y−y)` é aplicado ao **centro** das regiões e a pontos consultados quando `side==AWAY`; os índices `col/row` permanecem na perspectiva do time. `mapper/src/mapper.py`. **[AUTORITATIVO: código]**

**Objeto `Goal`** (`src/goal.py`; instâncias `homeGoal`/`awayGoal` em `mapper/src/direction.py`) **[AUTORITATIVO: código+specs]**:

| Goal | `place` | center (x,y) | top_pole (x,y) | bottom_pole (x,y) | defende |
|---|---|---|---|---|---|
| `homeGoal` | HOME (0) | (0, 5000) | (0, 6500) | (0, 3500) | HOME |
| `awayGoal` | AWAY (1) | (20000, 5000) | (20000, 6500) | (20000, 3500) | AWAY |

API: `get_center()`, `get_place()→Team.Side`, `get_top_pole()`, `get_bottom_pole()`. `Mapper.get_attack_goal()` = `awayGoal` se HOME senão `homeGoal`; `get_defense_goal()` = o oposto.

---

## 2. Dados por turno: API do inspector + protobuf + enums

### 2.1 `GameSnapshotInspector` — o que o bot lê e produz

Objeto entregue a cada turno (construído em `src/client.py:130` a partir de um `server_pb2.GameSnapshot`). Fonte: `src/game_snapshot_inspector.py`. **[AUTORITATIVO: código]**

**Getters de estado:**

| Método | Retorna | Linha |
|---|---|---|
| `get_snapshot()` | `GameSnapshot` inteiro | 17 |
| `get_turn()` | `uint32` `snapshot.turn` | 20 |
| `get_me()` | `Player` (o próprio) | 23 |
| `get_ball()` | `Ball` | 26 |
| `get_player(side, number)` | `Player` ou `None` | 29 |
| `get_ball_holder()` | `Player` (number 0 se livre) | 32 |
| `is_ball_holder(player)` | `bool` | 35 |
| `get_team(side)` / `get_my_team()` / `get_opponent_team()` | `Team` | 38/41/44 |
| `get_my_team_side()` / `get_opponent_side()` | `Team.Side` | 47/50 |
| `get_my_team_players()` / `get_opponent_players()` | `list[Player]` (`[]` se vazio) | 53/57 |
| `get_my_team_goalkeeper()` / `get_opponent_goalkeeper()` | `Player` (nº 1) | 61/64 |

Atributos públicos: `my_side`, `my_number`, `snapshot`, `me`. **Não há getters diretos** para `state`, `shot_clock` nem `turns_ball_in_goal_zone` — leem-se via `get_snapshot().state` / `.shot_clock` / `.turns_ball_in_goal_zone`.

**Factory de ordens (→ `server_pb2.Order`):**

| Método | Produz | Observação | Linha |
|---|---|---|---|
| `make_order_move(target, speed)` | `Order{move}` | de `me.position` até `target`, direção normalizada | 69 |
| `make_order_move_max_speed(target)` | `Order{move}` | `speed = PLAYER_MAX_SPEED (100)` | 72 |
| `make_order_move_from_point(origin, target, speed)` | `Order{move}` | núcleo | 75 |
| `make_order_move_from_vector(direction, speed)` | `Order{move}` | | 84 |
| `make_order_move_by_direction(direction, speed=None)` | `Order{move}` | **QUEBRADO, ver bug** | 88 |
| `make_order_move_to_stop()` | `Order{move}` speed 0 | mantém direção da velocidade atual | 92 |
| `make_order_jump(target, speed)` | `Order{jump}` | goleiro | 96 |
| `make_order_kick(target, speed)` | `Order{kick}` | **subtrai a velocidade atual da bola** antes de normalizar | 105 |
| `make_order_kick_max_speed(target)` | `Order{kick}` | `speed = BALL_MAX_SPEED (400)` | 115 |
| `make_order_catch()` | `Order{catch}` | mensagem vazia (`catch.SetInParent()`) | 118 |

**BUG confirmado [AUTORITATIVO: código]:** `get_orientation_by_direction` (L123) está definido **sem `self`** mas é chamado como método `self.get_orientation_by_direction(direction)` (L89). Em runtime `self` cai no parâmetro `direction` e `direction` no `my_side` → `make_order_move_by_direction` está quebrado. Use `make_order_move_from_point`/`_max_speed`.

**Detalhe do kick (L105-113):** o SDK calcula `diff = (vetor até o alvo) − (velocidade atual da bola)` e normaliza. Como o motor **soma** o kick à velocidade corrente, essa subtração compensa a inércia para a bola ir ao alvo. **[AUTORITATIVO: código]**

### 2.2 Mensagens protobuf — todos os campos

`protos/physics_pb2.py` e `protos/server_pb2.py` (namespace `lugo`). Lista completa de mensagens (não há outras): `physics_pb2 = {Vector, Point, Velocity}`; `server_pb2 = {JoinRequest, GameSnapshot, Team, ShotClock, Player, Ball, OrderResponse, OrderSet, Order, Move, Catch, Kick, Jump}`. **[AUTORITATIVO: protobuf]**

**physics_pb2:**

| Mensagem | # | tipo | campo | nota |
|---|---|---|---|---|
| `Point` | 1/2 | `int32` | `x` / `y` | coordenadas inteiras |
| `Vector` | 1/2 | `double` | `x` / `y` | direção/deslocamento |
| `Velocity` | 1 | message | `direction` | `Vector` (magnitude 100) |
| | 2 | `double` | `speed` | d/turno |

**server_pb2 (dados de turno):**

| Mensagem | # | tipo | campo | ref/nota |
|---|---|---|---|---|
| `Player` | 1 | `uint32` | `number` | 1..11; goleiro=1 |
| | 2 | message | `position` | `Point` |
| | 3 | message | `velocity` | `Velocity` |
| | 4 | enum | `team_side` | `Team.Side` |
| | 5 | message | `init_position` | `Point` |
| `Ball` | 1 | message | `position` | `Point` |
| | 2 | message | `velocity` | `Velocity` |
| | 3 | message | `holder` | `Player` (number 0 ⇒ sem dono) |
| `Team` | 1 | repeated | `players` | `Player` |
| | 2 | `string` | `name` | |
| | 3 | `uint32` | `score` | |
| | 4 | enum | `side` | `Team.Side` |
| `GameSnapshot` | 1 | enum | `state` | `GameSnapshot.State` |
| | 2 | `uint32` | `turn` | 0..6000 |
| | 3 | message | `home_team` | `Team` |
| | 4 | message | `away_team` | `Team` |
| | 5 | message | `ball` | `Ball` |
| | 6 | `uint32` | `turns_ball_in_goal_zone` | limite 40 |
| | 7 | message | `shot_clock` | `ShotClock` |
| `ShotClock` | **6** | enum | `team_side` | time atacando |
| | **7** | `uint32` | `remaining_turns` | começa em 300 |
| `Order` | 1 | message | `move` → `Move` | `oneof action` |
| | 2 | message | `catch` → `Catch` | |
| | 3 | message | `kick` → `Kick` | |
| | 4 | message | `jump` → `Jump` | |
| `Move`/`Kick`/`Jump` | 1 | message | `velocity` | `Velocity` |
| `Catch` | — | — | — | **sem campos** (o ato é a presença) |
| `OrderSet` | 1 | `uint32` | `turn` | o bot devolve por turno |
| | 2 | repeated | `orders` → `Order` | |
| | 3 | `string` | `debug_message` | |
| `OrderResponse` | 1 | enum | `code` | `OrderResponse.StatusCode` |
| | 2 | `string` | `details` | |
| `JoinRequest` (handshake) | 1/2/3/4/5 | | `token`, `protocol_version`("1.0.0"), `team_side`, `number`, `init_position` | não é dado de turno |

> Atenção aos números de campo **6 e 7** do `ShotClock` (não 1/2). `src/lugo.py` define **wrappers Python homônimos** que **não** trafegam no turno — o inspector carrega os protobuf de `server_pb2`. Os únicos símbolos de `lugo.py` usados no laço são os IntEnums `State` e `TeamSide`.

### 2.3 Enums

**`GameSnapshot.State` ≡ `lugo.State`** (`src/lugo.py:235`) **[AUTORITATIVO]**:

| valor | nº | significado |
|---|---|---|
| `WAITING` | 0 | esperando conexões; expira → OVER |
| `GET_READY` | 1 | reposiciona jogadores (início / pós-gol) |
| `LISTENING` | 2 | **janela em que o bot manda ordens** |
| `PLAYING` | 3 | executa ordens na ordem recebida; se a bola é livre, a velocidade dela é processada 1º |
| `SHIFTING` | 4 | troca de posse ao esgotar o shot clock; bola vai ao goleiro da defesa |
| `OVER` | 99 | fim de jogo |

- **`Team.Side` ≡ `TeamSide`:** `HOME=0`, `AWAY=1`.
- **`OrderResponse.StatusCode` ≡ `StatusCode`:** `SUCCESS=0`, `UNKNOWN_PLAYER=1`, `NOT_LISTENING=2`, `WRONG_TURN=3`, `OTHER=99`.
- **`PlayerState`** — estado **derivado pelo SDK**, não é campo protobuf (`src/define_state.py`); segundo argumento de `Bot.as_goalkeeper(inspector, player_state)`: `SUPPORTING=0` (dono é companheiro), `HOLDING_THE_BALL=1` (eu tenho), `DEFENDING=2` (dono é adversário), `DISPUTING_THE_BALL=3` (`holder.number==0`).
- **`DIRECTION`** (`mapper/src/direction.py:8`): `FORWARD=0, BACKWARD=1, LEFT=2, RIGHT=3, BACKWARD_LEFT=4, BACKWARD_RIGHT=5, FORWARD_LEFT=6, FORWARD_RIGHT=7`.
- **`ORIENTATION`** (8 vetores unitários escalados a 100; **y cresce para NORTE**): `EAST=(1,0)`, `WEST=(−1,0)`, `NORTH=(0,1)`, `SOUTH=(0,−1)`, `NORTH_EAST=(1,1)`, `NORTH_WEST=(−1,1)`, `SOUTH_EAST=(1,−1)`, `SOUTH_WEST=(−1,−1)`. Mapeamento `DIRECTION`→`ORIENTATION` depende do lado; HOME: FORWARD→EAST, LEFT→NORTH, etc.; AWAY: espelhado.

### 2.4 Mapper / Region (utilitário do bot, não trafega)

`mapper/src/mapper.py`. Grade `cols × rows`; limites `MIN_COLS=4`, `MAX_COLS=200`, `MIN_ROWS=2`, `MAX_ROWS=100`; nº de regiões = `cols×rows` (escolhido pelo bot; default SDK `Mapper(10,6)`=60 regiões). `regionWidth=20000/cols`, `regionHeight=10000/rows`. `Region` expõe `col/row/side/center/positioner`, `front()`/`back()` (mexem na **coluna**/eixo x), `left()`/`right()` (mexem na **linha**/eixo y). **[AUTORITATIVO: código]**

---

## 3. Constantes do ambiente — tabela mestra

Fonte: `src/specs.py` (avaliado; **não existe** `specs.json` no pacote). **[AUTORITATIVO: specs]** salvo indicação.

| Constante | Valor | Unidade | Fonte | Marca |
|---|---|---|---|---|
| `BASE_UNIT` | 100 | d | specs.py:1 | AUTORITATIVO |
| `MAX_X_COORDINATE` | 20000 | d | specs.py:2,26 | AUTORITATIVO |
| `MAX_Y_COORDINATE` | 10000 | d | specs.py:3,31 | AUTORITATIVO |
| `FIELD_WIDTH` / `FIELD_HEIGHT` | 20001 / 10001 | coord | specs.py:38,44 | AUTORITATIVO |
| `FIELD_NEUTRAL_CENTER` | 1000 | d (raio) | specs.py:47 | AUTORITATIVO |
| `GOAL_WIDTH` | 3000 | d | specs.py:66 | AUTORITATIVO |
| `GOAL_MIN_Y` / `GOAL_MAX_Y` | 3500.0 / 6500.0 | d (y) | specs.py:69,72 | AUTORITATIVO |
| `GOAL_ZONE_RANGE` | 1400 | d | specs.py:75 | AUTORITATIVO |
| `PLAYER_SIZE` | 400 | d (diâmetro) | specs.py:8 | AUTORITATIVO |
| `PLAYER_MAX_SPEED` | 100.0 | d/turno | specs.py:21 | AUTORITATIVO |
| `BALL_SIZE` | 200 | d (diâmetro) | specs.py:50 | AUTORITATIVO |
| `BALL_MAX_SPEED` | 400.0 | d/turno | specs.py:56 | AUTORITATIVO |
| `BALL_MIN_SPEED` | 2 (int) | d/turno | specs.py:59 | AUTORITATIVO |
| `BALL_DECELERATION` | 10.0 | d/turno (queda do `speed`) | specs.py:53 | AUTORITATIVO |
| `BALL_TIME_IN_GOAL_ZONE` | 40 | turnos (=2 s @20fps) | specs.py:63 | AUTORITATIVO |
| `SHOT_CLOCK_TIME` | 300 | turnos (=15 s @20fps) | specs.py:98 | AUTORITATIVO |
| `GOALKEEPER_NUMBER` | 1 | — | specs.py:92 | AUTORITATIVO |
| `GOALKEEPER_JUMP_SPEED` | 200.0 | d/turno (=2×jogador) | specs.py:89 | AUTORITATIVO |
| `GOALKEEPER_JUMP_DURATION` | 3 | turnos (não interrompível) | specs.py:82 | AUTORITATIVO |
| `GOALKEEPER_SIZE` | **`(919.999…,)` — TUPLA (bug)** | d (largura) | specs.py:95 | AUTORITATIVO (defeito) |
| `MAX_PLAYERS` / `MIN_PLAYERS` | 11 / 6 (<6 ⇒ W.O.) | — | specs.py:15,18 | AUTORITATIVO |
| `PLAYER_RECONNECTION_WAIT_TIME` | 20 | turnos | specs.py:12 | AUTORITATIVO |
| `TOUCH_RADIUS` | 300 = (400+200)/2 | d | `physics.py:37`, `geometry.py:23` | **INFERIDO** (não é constante do SDK) |
| `GOALKEEPER_HALF_EXTENT` | 560 = (920+200)/2 | d | `geometry.py` | INFERIDO |
| **GAME_TURNS** | **6000** | turnos | config replay `game_duration` + MEDIDO | ver §3 nota 1 |
| **FPS** | 20 | quadros/s | comentário specs.py:63; `physics.py` | INFERIDO (não é constante do SDK) |
| Duração real | 6000/20 = 300 s = 5 min | — | derivado | INFERIDO |
| `listening_duration` | 50 ms | orçamento/turno | config replay | MEDIDO (config) |
| `listening_mode` | "RUSH" | — | config replay | MEDIDO (config) |

**Defeitos e divergências resolvidos:**

1. **GAME_TURNS: `physics.py` está ERRADO por 5×.** Define `GAME_TURNS=1200`, mas a config real de todas as partidas traz `game_duration=6000` e o **maior `turn` observado = 6000** (25 arquivos). Valor autoritativo = **6000** (5 min @20fps). *Corrigir `physics.py`.*
2. **`GOALKEEPER_SIZE` é uma TUPLA**, não número: `specs.py:95` termina com vírgula (`PLAYER_SIZE*2.3,`) → `(919.999…,)`. Valor pretendido = **920.0**. Qualquer aritmética direta quebra; `geometry.py` hard-codeia 920. Sinal de que nenhum bot Python do ecossistema a usa.
3. `BALL_MIN_SPEED`: `int 2` (specs) vs `float 2.0` (physics) — sem efeito prático.
4. `FPS` e nº de turnos **não existem como constante** no `lugo4py` — FPS só em comentário; turnos vêm da config/medição.

---

## 4. Física da bola (movimento livre, deceleração, bounce)

Medições: `analysis/replay.py` sobre `bench/recordings/`. Subconjuntos de 30–60 arquivos.

### 4.1 Deceleração — exata

**[MEDIDO: replay, N=56.503]** pares de turnos consecutivos com bola solta, direção constante (dot>0,9995): a bola perde **exatamente 10,0 d/turno** no `speed` reportado — mediana 10,0000, média 10,0000, mín=máx=10,000, **σ=0,0000**. Confirma `BALL_DECELERATION=10`. Corroborado em varredura de 35.095 transições (mediana 10,0). Bola **para** quando `speed ≤ BALL_MIN_SPEED=2`.

### 4.2 Deslocamento por turno — ⚠️ CORREÇÃO do fato de calibração

**[MEDIDO: replay, N=56.503]** Dois modelos do deslocamento `D_t` (de `pos_t` a `pos_{t+1}`) vs a velocidade reportada `S_t`:

| Modelo | Fórmula | Erro mediano | p90 | p99 |
|---|---|---|---|---|
| A — "velocidade atual" | `D = S_t` | 5,000 | 5,392 | 5,571 |
| **B — trapezoidal** | **`D = S_t − 5`** | **0,229** | 0,463 | 0,603 |

**Achado adversarial:** o fato de calibração *"deslocamento por turno = velocidade atual (erro 7,7)"* está **sistematicamente errado por +5 d/turno** (= metade da deceleração). O modelo correto é o **trapezoidal** `D = S_t − BALL_DECELERATION/2`, com erro mediano ~0,23 d (nível do arredondamento a inteiro). Isto **confirma** `ball_step(v)=v−HALF_DECEL` (`geometry.py:55-60`) e **refuta** `results/DADOS_DA_PARTIDA.md:48`. O `geometry.py` já usa o modelo certo; o doc de calibração está desatualizado. Os "7,7" antigos provavelmente incluíam turnos próximos de chutes/quiques/bordas.

Exemplo bruto (`fin_002_home`, voo livre): turno 15 `S=220,59`@(9927,5201); turno 16 `S=210,59`@(9929,5417); deslocamento medido = **216,0**. Modelo A prevê 220,59 (erro 4,6); Modelo B prevê 215,59 (erro 0,4). **[MEDIDO]**

> **Convenção de reporte** (chave para reconciliar tudo): a `speed` reportada no turno t é a velocidade **após** a deceleração daquele turno. **Regra operacional para o planejador:** da posição/velocidade reportadas, **avance `S−5` por turno e subtraia 10 da velocidade**.

### 4.3 Bounce nas paredes — reflexão elástica

**[MEDIDO: replay, N=92 quiques em 30 arquivos]** A bola **reflete elasticamente** em `x∈{0,20000}` e `y∈{0,10000}`: a componente **perpendicular** à parede é **negada exatamente**, a **paralela é preservada**, e o `speed` cai só os 10 d/turno normais. Confirma `ball_trajectory` (`geometry.py:110-154`). Casos (`fin_001_away`):

| Caso | Turno | Parede | Antes (ux,uy,s) | Depois (ux,uy,s) |
|---|---|---|---|---|
| topo y≈10000 | 407 | y=10000 | (−0,624, **+0,782**, 210) | (−0,624, **−0,782**, 200) |
| fundo AWAY | 5585 | x=20000 | (**+0,617**, +0,787, 330) | (**−0,617**, +0,787, 320) |

(No caso x=20000 o y=6933–7189 está **fora** da boca do gol [3500,6500] — bate na linha de fundo, não entra.)

---

## 5. Chute e passe (soma à velocidade, cap, fator de ângulo, alcance/chegada)

### 5.1 Teto e comportamento de saída

**[MEDIDO: replay, N=28.117 liberações de chute em 60 arquivos]** velocidade de saída reportada: mediana 209,7; p90=p99=390; **máximo = 390**; liberações ≥395 = **0**. O teto **reportado** é **exatamente 390, nunca 400** — nem em 78.959 amostras de voo livre.

Isto **não contradiz** `BALL_MAX_SPEED=400`: é a **convenção de reporte** (§4.2) — o servidor aplica o cap interno 400 no instante do chute, a bola avança nesse turno, e o snapshot já reporta a velocidade decrementada de um passo: **390 = 400 − 10**. **[MEDIDO + INFERIDO da convenção]**

**Soma + cap:** a regra "o kick SOMA à velocidade atual e limita a 400" é **consistente** com o teto rígido observado (nunca >390 reportado, independentemente da velocidade de entrada), mas o **termo de soma não é isolável** do replay sem as ordens gravadas. **[INFERIDO: specs/geometry; não isolável em replay]**

### 5.2 Fator de ângulo — proveniência corrigida

`factor = 0.5 + 0.5·((180−ang)/180)` → 100% a 0°, 50% a 180° (`geometry.py:396 _apply_server_kick`; `physics.py:102-107`; `fastsim.py:272`).

| Verificação | Resultado |
|---|---|
| Está no protobuf? | **NÃO** — `Velocity={direction,speed}`, `Kick={velocity}`; nenhum campo `factor/angle`. [AUTORITATIVO: introspecção] |
| Está em `specs.py`? | **NÃO.** [AUTORITATIVO: specs] |
| Onde aparece? | Só em código/docs **do próprio time**. |
| Mensurável no replay? | **NÃO** — ordens de chute não são gravadas. |

**Veredito:** o fator de ângulo é **[INFERIDO]** (modelo do time), **não [AUTORITATIVO]**. O comentário em `geometry.py:375` ("Física real do servidor (server.proto, message Kick)") **atribui erroneamente a proveniência** — o `server.proto`/`Kick` só carrega `velocity`, não a lógica de redução. A fonte real seria o código Go do servidor (`github.com/lugobots/server`), **ausente neste ambiente**. Contra estes replays: **[DESCONHECIDO]** — inconfirmável. O mesmo vale para "pedido vs. saída".

### 5.3 Alcance e velocidade de chegada — formas fechadas validadas

A integração trapezoidal com deceleração constante é exata:

| Grandeza | Forma fechada | Código | Verificação |
|---|---|---|---|
| Alcance | `range(v0) = v0²/20` | `ball_range` geometry.py:63 | discreto ≡ fechado |
| Vel. de chegada | `arrival(v0,d) = √(v0² − 20·d)` | `finishing.arrival_speed:30` | **[MEDIDO: N=78.959]** erro mediano **0,017** d/turno, p90 0,078, p99 0,479 |
| Vel. p/ distância | `speed_for_distance(d) = √(20·d)` | geometry.py:74 | ≡ fechado |
| Turnos p/ distância | soma trapezoidal iterativa | `turns_for_ball` geometry.py:90 | — |

**Alcance por v0 (a partir do pé)** [INFERIDO: forma fechada validada]:

| v0 | Alcance | Turnos até parar |
|---|---|---|
| 100 | 500 | — |
| 200 | 2.000 | — |
| 300 | 4.500 | — |
| 350 | 6.125 | — |
| **390** (máx reportado) | **7.605** | 39 |
| **400** (cap interno) | **8.000** | 40 (=2,0 s) |

**Chegada e turnos a v0=400** [INFERIDO]:

| Distância | Vel. chegada | Turnos |
|---|---|---|
| 1.000 | 374,2 | 3 |
| 3.000 | 316,2 | 9 |
| 4.000 | 282,8 | 12 |
| 5.000 | 245,0 | 16 |
| 6.000 | 200,0 | 20 |
| 7.000 | 141,4 | 26 |
| 8.000 | 0,0 | 40 |

Notas: `DANGEROUS_SHOT_RANGE=6000` (geometry.py:37) ⇔ chegada de exatamente **200** d/turno; `MAX_KICK_RANGE=8000` ⇔ chegada 0.

**Menor v0 para parar em d** (`speed_for_distance=√(20d)`): 3.000→245,0; 6.000→346,4; 7.605→390,0; 8.000→400,0 (cap); >8.000 inalcançável em 1 chute.

**Subtileza 7.605 vs 8.000** (dois números corretos, perguntas diferentes): "até onde meu chute máximo leva a bola?" → **8.000 d do pé** (v0 interno 400, `MAX_KICK_RANGE`); "até onde uma bola que vejo AGORA a 390 ainda vai?" → **7.605 d** da posição reportada (`390²/20`). Os ~395 d de diferença = o primeiro avanço (400−5) já ocorrido no turno da liberação, antes do primeiro snapshot solto. **O planejador, que só vê ≤390 reportado, deve usar `v0_reportado²/20` para bola já em voo.**

---

## 6. Regras do servidor (posse/catch, goleiro, gol, shot clock, colisão)

Medições: `analysis/replay.py` sobre 221 replays; amostras indicadas por regra. Cada turno tem 2 snapshots idênticos → série `PLAYING` consecutiva.

### 6.1 Posse / catch

| Campo | Valor | Fonte |
|---|---|---|
| Dist. bola↔holder **em posse** | **200,0** (min 199,4 / max 200,7; n=4016) | [MEDIDO] — grudada no raio do jogador (`PLAYER_SIZE/2=200`), à frente |
| `TOUCH_RADIUS` teórico de contato | 300 = 200+100 | [AUTORITATIVO: derivado] |
| Dist. pré-captura (1 turno antes), todas as trocas | mediana 239 · p95 500 (n=127913) | [MEDIDO] |
| … roubo do adversário | mediana 224,5 · p5 83 · p95 392,9 (n=93517) | [MEDIDO] |
| … bola solta | mediana 351,7 · p95 609 (n=34396) | [MEDIDO] |
| … bola parada (speed<15) | mediana 379 · min 276 · max 462 (n=83) | [MEDIDO] |

**Mecanismo (medido):** o holder muda por **proximidade** — ao entrar no raio de toque (~300 d centro-a-centro), o jogador vira `holder` e a bola é reposicionada a 200 d à sua frente. As distâncias pré-captura são medidas **1 turno antes**; como bola e jogador se aproximam no turno, a captura real é **≤** esses valores, consistente com `TOUCH_RADIUS=300`. **[INFERIDO]** raio efetivo ≈300 d (possivelmente um pouco menor); não isolável com precisão pela granularidade dos snapshots.

**Ordem `catch`:** mensagem vazia (`Catch` sem campos); o jogador tenta **agarrar** ativamente (uso típico do goleiro). **[DESCONHECIDO]** a resolução server-side do `catch` (prioridade vs. proximidade, se garante posse) — os replays não gravam eventos de `orders`. O mecanismo observável e dominante é a captura por proximidade.

### 6.2 Goleiro (jogador nº 1)

| Campo | Valor | Fonte |
|---|---|---|
| x preso à linha do gol | HOME x=0; AWAY x=20000 (min=med=max; n=438017/lado) | [MEDIDO] — travado |
| Deslocamento/turno (corrida, eixo y) | mediana 0 · p95 **100** · máx normal 100 | [MEDIDO, n=875888] = `PLAYER_MAX_SPEED` |
| Deslocamento/turno **no pulo** | **200** exatos (n=532 turnos limpos) | [MEDIDO] = `GOALKEEPER_JUMP_SPEED` |
| `velocity.speed` reportado | 100 (corrida) / 200 (pulo) | [MEDIDO, n=373633] |
| `GOALKEEPER_JUMP_DURATION` | 3 turnos (não interrompível) | [AUTORITATIVO] (não isolado sozinho no replay) |
| `GOALKEEPER_SIZE` | 920 pretendido (tupla — bug) | [AUTORITATIVO] |
| Alcance de pegada do goleiro | pré-captura mediana **525** · p95 **829** · máx **977** (n=252) | [MEDIDO] — >> jogador de linha (~300) |

**Interpretação:** o goleiro **não sai da linha** (x travado), move-se só em y a ≤100/turno; ao pular faz exatamente 200/turno por até 3 turnos (≈600 d de alcance vertical em rajada, [INFERIDO] de DURATION=3). Reach efetivo ≈ 920/2 + 100 ≈ **560 d** [INFERIDO da spec, corroborado pela medição]. **[DESCONHECIDO]** o gatilho de decisão do pulo — é do bot, não do servidor; nos replays vê-se só o efeito (rajadas de speed=200).

### 6.3 Gol

| Campo | Valor | Fonte |
|---|---|---|
| Condição de gol | bola atinge x∈{0,20000} **com** y∈[3500,6500] | [MEDIDO] |
| x da bola no gol (90 eventos) | exatamente 0 (38×) ou 20000 (52×) | [MEDIDO, n=90] |
| y da bola no gol | min 3518 · mediana 6240 · máx 6487 (∈[3500,6500]) | [MEDIDO, n=90] |
| Evento `goal` | `{"side": <time que MARCOU>}` (AWAY marca ⇒ x=0) | [MEDIDO] |
| Reset da bola pós-gol | **(10000, 5000)** exato | [MEDIDO] |
| Reset dos jogadores | teleporte para `init_position` | [MEDIDO] |
| Sequência de estados | mesmo turno: `PLAYING`→`GET_READY`→(reset)→`LISTENING`→`PLAYING` | [MEDIDO] |
| Placar | incrementa `team.score` do time que marcou | [MEDIDO] |

Exemplo (fin_001, turn 2348): bola cruza (0, 6330) → `goal side=AWAY`, placar 0×1; mesmo turn bola vai a (10000,5000), jogadores voltam via `GET_READY`.

### 6.4 Shot clock + zona de gol (dois temporizadores independentes)

**Shot clock** — tempo de ataque do time:

| Campo | Valor | Fonte |
|---|---|---|
| `SHOT_CLOCK_TIME` | 300 turnos (=15 s) | [AUTORITATIVO] |
| `shot_clock.remaining_turns` | conta regressiva 300→1 | [MEDIDO] |
| A quem pertence | time que possui/possuiu por último | [MEDIDO] |
| Bola solta pausa? | **Não** — segue contra o último atacante | [MEDIDO] |
| O que zera | posse mudar para o **outro** time ⇒ reset 300 | [MEDIDO] |
| Ao expirar | posse ao **goleiro adversário**, bola a x=200 à frente do GK, relógio→300 | [MEDIDO, 2 casos limpos] |
| Menor `remaining_turns` visto | 1 (posse quase sempre troca antes) | [MEDIDO, 221 arq.] |

Expiração (newg_005 turn 1743→1744; tcc_015 1919→1920): bola presa no canto defensivo do atacante, `rem→1`; turno seguinte `rem=300 side=<oponente>`, `holder=(<oponente>, 1)` (goleiro), bola em (200, ~5000). Turnover forçado anti-retenção.

**Zona de gol** — anti-camping, **independente** do shot clock:

| Campo | Valor | Fonte |
|---|---|---|
| `BALL_TIME_IN_GOAL_ZONE` | 40 turnos (=2 s) | [AUTORITATIVO] |
| `GOAL_ZONE_RANGE` | 1400 d da linha de gol, **qualquer y** | [AUTORITATIVO] + [MEDIDO] (contado com y fora da boca, ex. y=6548, y=2568) |
| Contador `turns_ball_in_goal_zone` | sobe 0..**39**; ao chegar a 40 dispara e zera | [MEDIDO, máx=39] |
| Ação ao expirar | bola **auto-chutada** ao centro | [MEDIDO, 25+ casos] |
| Velocidade do auto-chute | **≈390** (=cap 400 pós-1ª desaceleração) | [MEDIDO] |

Exemplo: bola parada em (760,3765) por 40 turnos → ejetada para (1152,3817) a 390/turno.

### 6.5 Colisão jogador-jogador — inexistente

| Campo | Valor | Fonte |
|---|---|---|
| Bloqueio/repulsão? | **Não detectado** | [MEDIDO] |
| Menor distância par-a-par por snapshot | mediana **200** · p5 37 · **min 0** (sobreposição total) (n=17544) | [MEDIDO] |
| Pares mais próximos que 400 (=PLAYER_SIZE) | 32154/4052664 = **0,79%** | [MEDIDO] |

**Conclusão [MEDIDO — definitivo]:** mediana do par mais próximo = 200 d (abaixo do diâmetro 400) e mínimo 0 → **sem corpo rígido nem repulsão**; jogadores se atravessam livremente.

---

## 7. O que NÃO temos, e implicações para decisão

**Não presente / não medível neste ambiente:**

1. **Ordens dos bots não são gravadas nos replays** — só snapshots + eventos de estado/gol. Consequências:
   - **[DESCONHECIDO]** velocidade de chute *pedida* vs. *saída*; o **fator de ângulo** (`0.5+0.5·(180−ang)/180`) é **modelo do time [INFERIDO]**, inverificável e sem proveniência autoritativa (o comentário em `geometry.py:375` atribui erroneamente ao `server.proto`).
   - **[DESCONHECIDO]** resolução server-side do `catch` — prioridade vs. proximidade, se garante posse.
   - **[DESCONHECIDO]** o **termo de soma** kick+velocidade não é isolável (só o cap rígido é observável).
2. **Intenção/decisão do adversário** — **[DESCONHECIDO]**. O snapshot dá posição/velocidade atuais, não a ordem que o oponente enviou nem seu alvo. O gatilho do pulo do goleiro também é do bot, não do servidor — invisível.
3. **Ruído do servidor** — as posições são inteiras (arredondadas); o erro residual do modelo trapezoidal (~0,23 d) é essencialmente esse arredondamento, **não** ruído estocástico do motor. A física medida é **determinística** (deceleração σ=0; reflexão exata; chegada validada a 0,017 d). **[MEDIDO]**
4. **Código Go do servidor** (`github.com/lugobots/server`) ausente — a lógica de redução de chute, prioridade de `catch` e detalhes de disputa vivem lá.

**Implicações para decisão do bot:**

- **Planeje a partir do estado reportado com o modelo trapezoidal:** avance `S−5` por turno, subtraia 10 de `S`. Não use "deslocamento = velocidade atual" (erro sistemático +5). Para bola em voo já observada (≤390), use alcance `S²/20`; para o próprio chute máximo do pé, use `MAX_KICK_RANGE=8000` (v0 interno 400).
- **Cap prático:** nunca conte com >390 reportado após um chute máximo; a chegada útil a 6.000 d é exatamente 200 d/turno (`DANGEROUS_SHOT_RANGE`).
- **Sem colisão corporal:** posicionamento pode sobrepor jogadores livremente; marcação é por interceptação da bola (raio ~300), não por bloqueio físico.
- **Dois relógios anti-retenção:** shot clock (300 turnos, por posse, turnover ao goleiro adversário) e goal-zone (40 turnos dentro de 1400 d de qualquer gol, auto-chute ao centro a ~390). Ambos devem ser monitorados via `get_snapshot().shot_clock.remaining_turns` e `.turns_ball_in_goal_zone`.
- **Goleiro:** reach efetivo ~560 d e pulo de 200/turno por 3 turnos — chutes a gol devem mirar fora desse alcance vertical (postes y=3500/6500) e evitar linhas retas ao GK.
- **Compense a inércia do kick** confiando em `make_order_kick` (que já subtrai a velocidade atual da bola). Evite `make_order_move_by_direction` (bug de `self`).

---

*Conflitos resolvidos nesta edição:* (a) deslocamento/turno — vence o **trapezoidal `v−5`** medido (geometry.py correto; doc de calibração e physics.py L48 desatualizados); (b) GAME_TURNS — vence **6000** medido/config (physics.py=1200 errado); (c) cap da bola — 400 interno (specs) reconciliado com 390 reportado (convenção pós-deceleração); (d) fator de ângulo — reclassificado de AUTORITATIVO para **INFERIDO** (ausente de protobuf/specs); (e) `GOALKEEPER_SIZE` — documentado como tupla-bug, valor pretendido 920.