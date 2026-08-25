# Triagem cética — o que deste projeto poderia virar issue/PR em terceiros

## Contexto

O projeto Lugo Bots esbarrou em ~13 comportamentos anotados como "armadilhas" no
README. A pergunta desta triagem não é "o que nos atrapalhou", é **"o que é defeito da
ferramenta e não uso incorreto nosso"**. Verifiquei cada candidato contra o código-fonte
atual dos repositórios de terceiros, o pacote publicado no PyPI, e as issues/PRs abertas
e fechadas. Onde a evidência era só impressão, descartei.

**Resultado honesto: dois candidatos sobreviveram ao teste técnico, e ambos falham no
seu critério de manutenção.** Os detalhes estão abaixo para você decidir; a recomendação
está no fim.

---

## O fato que contamina os dois candidatos

Ambos vivem em `github.com/lugobots/lugo4py`. Estado medido hoje:

| indicador | valor |
|---|---|
| último commit no `master` | **2024-09-09** (23 meses) |
| última atividade de qualquer tipo | PR #34, do próprio mantenedor, aberto **2025-06-24**, sem comentários |
| issue #33 (aberta pelo **mantenedor**, `rubens21`) | aberta 2024-09-25, **0 comentários em 23 meses** |
| versão no PyPI | 1.0.5, publicada 2024-08-30 |
| downloads | 232/mês (o pacote está em uso) |

Pela letra da sua regra — "projeto abandonado, sem commit há mais de um ano" — **os dois
candidatos são descartados aqui**. O contra-argumento é que a organização está viva
(`bot-starter` com push em 2026-03-29, torneio rodando em 2026) e o pacote tem uso real;
o repositório Python é que está dormente. Você decide se a regra vale como escrita.

---

## Candidato 1 — `GOALKEEPER_SIZE` é uma tupla, não um número

### 1. Ferramenta e versão
`lugo4py` 1.0.5 (PyPI, 2024-08-30) e `master` atual. Manutenção: ver quadro acima.

### 2. Classificação
**Defeito de comportamento.** Erro de digitação de um caractere que torna uma constante
pública inutilizável.

### 3. Reprodução mínima (fora do nosso projeto)
```python
pip install lugo4py==1.0.5

from lugo4py import specs
print(repr(specs.GOALKEEPER_SIZE))   # (919.9999999999999,)  <- tupla
print(repr(specs.PLAYER_SIZE))       # 400                   <- int, como esperado
specs.GOALKEEPER_SIZE / 2            # TypeError: unsupported operand type(s)
                                     #            for /: 'tuple' and 'int'
```

Causa, em `src/lugo4py/src/specs.py`:
```python
GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,     # <- vírgula final
```

### 4. Evidência
- Executado no pacote instalado: `type(GOALKEEPER_SIZE)` é `tuple`; qualquer aritmética
  levanta `TypeError`. Não é interpretação — é exceção.
- **Os clientes irmãos estão corretos**, o que prova que é engano e não intenção:
  - Go (`lugo4go/specs/specs.go`): `GoalkeeperSize = PlayerSize * 2.3` — sem vírgula
  - JS (`lugo4node/src/specs.ts`): `GOALKEEPER_SIZE: player_size * 2.3,` — a vírgula é
    separador de objeto e está correta ali
  A versão Python é uma transliteração do literal de objeto do JS; a vírgula, inofensiva
  em JS, virou tupla em Python.
- **Nada dentro do pacote usa a constante** (`grep` no pacote instalado: zero
  ocorrências fora do `specs.py`) — por isso passou despercebido.
- Foi introduzida no **último commit substantivo do repositório** (PR #31/#32, "adding
  missing constant with the goalkeeper size", 2024-08-30/09-09).

### 5. Onde está no nosso repositório
`bot/src/geometry.py:25-28` — comentário e contorno.

### 6. Como contornamos
Hardcode do valor, com a razão registrada no comentário:
```python
GOALKEEPER_HALF_EXTENT = (920 + BALL_SIZE) / 2   # 560
```
O contorno **é** o rascunho da correção: basta remover a vírgula.

### 7. Já foi reportado?
Não. Varri as 34 issues/PRs de `lugo4py` (abertas e fechadas) e as de `lugo4go`,
`lugo4node` e `protos`: nenhuma menciona `GOALKEEPER_SIZE`. A única issue Python aberta
é a #33, sobre outro assunto (`get_orientation_by_direction` sem `self`).

---

## Candidato 2 — `make_order_kick` mira de forma dimensionalmente inconsistente

### 1. Ferramenta e versão
`lugo4py` 1.0.5 / `master`. **Agravante:** o mesmo cálculo está em `lugo4go`
(`snapshot_inspector.go:140-155`), então é o desenho da biblioteca, não um deslize só do
Python. Isso enfraquece o candidato — ver item 7.

### 2. Classificação
**Defeito de comportamento** (fronteira com limitação de design). O helper subtrai um
vetor de *direção* de magnitude 100 de um vetor de *deslocamento* medido em unidades de
campo. As duas consequências são puramente client-side e não dependem da semântica do
servidor.

### 3. Reprodução mínima (fora do nosso projeto)
Usa só `lugo4py`, com a API real — sem código nosso:
```python
import math
from lugo4py.protos import server_pb2, physics_pb2
from lugo4py.src.game_snapshot_inspector import GameSnapshotInspector
import lugo4py

def kick_angle(dist, speed):
    s = server_pb2.GameSnapshot(); s.turn = 1
    s.ball.position.x, s.ball.position.y = 10000, 5000
    s.ball.velocity.direction.x, s.ball.velocity.direction.y = 100.0, 0.0
    s.ball.velocity.speed = speed
    p = s.home_team.players.add(); p.number = 10
    p.team_side = lugo4py.TeamSide.HOME
    p.position.x, p.position.y = 10000, 5000
    insp = GameSnapshotInspector(lugo4py.TeamSide.HOME, 10, s)
    u = 1 / math.sqrt(2)
    tgt = physics_pb2.Point(x=int(10000 + dist*u), y=int(5000 + dist*u))  # sempre 45°
    d = insp.make_order_kick(tgt, 400).kick.velocity.direction
    return math.degrees(math.atan2(d.y, d.x))
```

### 4. Evidência (medida agora, com a API real)

**(a) A direção depende da DISTÂNCIA do alvo.** O alvo está sempre sobre a mesma reta de
45°; só a distância muda:

| distância ao alvo | ângulo devolvido | desvio dos 45° |
|---|---|---|
| 400 | 57,16° | **+12,16°** |
| 800 | 50,55° | +5,55° |
| 1500 | 47,83° | +2,83° |
| 3000 | 46,38° | +1,38° |
| 12000 | 45,34° | +0,34° |

Um helper de "chute para este ponto" não pode devolver direções diferentes para pontos
sobre a mesma reta.

**(b) A direção ignora a VELOCIDADE da bola.** Mesma geometria (distância 3000),
variando `velocity.speed`:

| speed | 0 | 50 | 100 | 200 | 400 |
|---|---|---|---|---|---|
| ângulo | 46,38° | 46,38° | 46,38° | 46,38° | 46,38° |

Idêntico. Como o propósito da subtração é compensar o movimento da bola, e a velocidade
varia de 0 a 400, a compensação só pode estar certa para um valor de velocidade.

> **Ressalva de honestidade:** o número "erro mediano de 19,2° em 300 cenários" que
> circula no nosso README **não tem script de origem localizável** no repositório —
> aparece só como texto impresso em `analysis/frente3_run.py:120`. Descarto esse número
> como evidência; as duas tabelas acima o substituem com vantagem, por serem
> reproduzíveis sem o nosso código.

### 5. Onde está no nosso repositório
`bot/src/geometry.py:453` (`kick_to`) — a substituição, com o raciocínio no docstring.

### 6. Como contornamos
`kick_to` resolve a física ao contrário: procura, entre os chutes **alcançáveis** (o teto
de 400 nem sempre permite a velocidade desejada depois da soma), o que minimiza o erro
angular e só depois otimiza velocidade. ~288 avaliações triviais por turno, dentro do
orçamento de 50 ms.

### 7. Já foi reportado?
Não — nenhuma issue sobre mira/kick em `lugo4py`, `lugo4go`, `lugo4node` ou `protos`.

**Por que este candidato é mais fraco que o primeiro:**
- Está replicado em Go, ou seja, é o comportamento pretendido pela biblioteca; a resposta
  provável do mantenedor é "é uma aproximação, faça sua própria matemática".
- A correção "certa" depende da semântica do servidor (o chute **soma** à velocidade
  atual — medimos isso em replays, mas o servidor não tem repositório público, então não
  consigo citar fonte de terceiro).
- Desfecho realista: vira correção de **documentação** ("este helper não mira com
  precisão"), não correção de código. O README, aliás, já está desatualizado: documenta
  `reader.make_order_kick(ball, target, speed)` com três argumentos, enquanto o código
  tem dois.

---

## Ordenação por probabilidade de aceitação × esforço

| # | candidato | esforço | probabilidade | veredito |
|---|---|---|---|---|
| 1 | `GOALKEEPER_SIZE` tupla | ~10 min (PR de 1 caractere + issue com repro) | baixa **pelo abandono**, alta **pelo mérito** | **único que vale tentar** |
| 2 | mira do `make_order_kick` | ~2 h (issue com as duas tabelas; PR exigiria acordo sobre a semântica do servidor) | baixa | não fazer agora |

**Recomendação:** abrir **apenas o candidato 1**, como issue *com* PR anexado (uma issue
sozinha morreria como a #33 do próprio mantenedor). Se em algumas semanas houver
qualquer resposta, aí sim o candidato 2 passa a valer o esforço — a resposta seria a
evidência de que o repositório voltou a ser mantido. Se não houver, os dois ficam
documentados aqui e o assunto se encerra.

---

## Descartados

Onze candidatos foram descartados. Os principais, com o motivo:

| candidato | motivo do descarte |
|---|---|
| `starter.run(bot, on_join)` exigir 2 argumentos | **uso incorreto nosso** — a assinatura é `run(self, bot, on_join)`, ambos obrigatórios e tipados |
| `is_ball_holder(player)` exigir o jogador | **uso incorreto nosso** — assinatura correta e coerente |
| `docker-compose` recusar projeto com maiúscula | comportamento documentado do compose; **erro nosso** |
| timeout fixo de 5 s sem retry (`client.py:93`) | funciona como codificado; seria pedido de funcionalidade, e o contorno (esperar a porta) é trivial |
| servidor faz *panic* se o arquivo de replay já existe | **sem repositório público** — o servidor Lugo não está no GitHub da organização |
| posição inicial inválida derruba o registro em silêncio | idem — servidor, sem repositório |
| documentação diz 1200 turnos, servidor usa 6000 | está no site, **sem repositório de docs** onde abrir issue |
| `params.P` global impedir dois genomas no mesmo processo | **código nosso** |
| `docker network prune` matar partidas subindo | comportamento correto do Docker; corrida provocada por nós |
| `pkill -f` matar o próprio shell | comportamento correto do `pkill`; **erro nosso** |
| `get_orientation_by_direction` sem `self` | **já reportado** — issue #33, aberta pelo próprio mantenedor; não temos medição a acrescentar |

**Motivo predominante do descarte: uso incorreto nosso** (4 casos), seguido de
**inexistência de repositório onde reportar** (3 casos).
