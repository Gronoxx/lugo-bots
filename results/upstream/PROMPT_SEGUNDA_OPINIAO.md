Quero uma segunda opinião crítica sobre se devo abrir um pull request num repositório
de terceiros, e sobre o conteúdo desse PR. Prefiro que você tente derrubar a ideia a
que a valide. Se achar que estou errado em algum ponto factual, diga; se achar que o
PR não deve ser aberto, diga isso claramente. Se não souber algo, diga que não sabe em
vez de supor.

## Contexto

Participei de uma competição de bots de futebol (plataforma Lugo Bots). O bot é escrito
em Python usando a biblioteca cliente oficial `lugo4py`, mantida pela organização
`lugobots` no GitHub. Durante o projeto encontrei o que me parece ser um bug de uma
linha nessa biblioteca, contornei localmente, e agora estou considerando reportá-lo
upstream.

## O bug

Em `src/lugo4py/src/specs.py`, linha 95, do `master` atual e da versão publicada no
PyPI (1.0.5):

```python
# GOALKEEPER_SIZE is the width of the goalkeeper
GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,
```

A vírgula final faz a constante ser uma **tupla**, não um número. Verificado no pacote
instalado a partir do PyPI:

```python
>>> from lugo4py import specs
>>> repr(specs.GOALKEEPER_SIZE)
'(919.9999999999999,)'
>>> repr(specs.PLAYER_SIZE)
'400'
>>> specs.GOALKEEPER_SIZE / 2
TypeError: unsupported operand type(s) for /: 'tuple' and 'int'
```

Qualquer aritmética com a constante levanta `TypeError`, então ela é inutilizável para
o propósito documentado no próprio comentário acima dela ("a largura do goleiro").

## Fatos que verifiquei (e como)

1. **A constante não é usada em lugar nenhum dentro do pacote.** `grep` recursivo no
   repositório inteiro, incluindo o diretório `example/`, retorna duas ocorrências: a
   definição e o comentário acima dela. Por isso o `import` nunca falha e nenhum teste
   interno exercita o valor — o erro só aparece na máquina de quem escreve um bot.

2. **Os clientes irmãos definem a mesma constante corretamente**, o que sugere que a
   versão Python é transliteração do literal de objeto do JavaScript, onde a vírgula é
   um separador de propriedades inofensivo:

   | cliente | definição | correto? |
   |---|---|---|
   | Go (`lugo4go/specs/specs.go`) | `GoalkeeperSize = PlayerSize * 2.3` | sim |
   | JS (`lugo4node/src/specs.ts`) | `GOALKEEPER_SIZE: player_size * 2.3,` | sim (literal de objeto) |
   | Python (`lugo4py/src/lugo4py/src/specs.py`) | `GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,` | **não — tupla** |

3. **Ninguém reportou.** Varri as 34 issues e PRs (abertas e fechadas) do `lugo4py`,
   e as dos repositórios irmãos: nenhuma menciona `GOALKEEPER_SIZE`.

4. **A constante foi introduzida no último commit substantivo do repositório** — PRs
   #31/#32, "adding missing constant with the goalkeeper size", de 30/08/2024 e
   09/09/2024.

5. **O repositório está dormente.** Último commit no `master`: 09/09/2024, quase dois
   anos atrás. A issue #33, aberta pelo **próprio mantenedor** em 25/09/2024 sobre outro
   bug, está há 23 meses **sem um único comentário**. Há um PR #34 do mantenedor aberto
   desde 24/06/2025, também sem comentários. O pacote no PyPI tem cerca de 232 downloads
   por mês, então está em uso.

6. **Historicamente, PRs de fora eram aceitos, e rápido.** 14 dos 16 PRs de
   contribuidores externos foram mergeados; a mediana do tempo até o merge é de cerca de
   um dia, e o mais lento levou 81 dias. O último merge de PR externo foi em março de
   2024. Ou seja: a dormência parece ser abandono do repositório, não hostilidade a
   contribuições.

7. **Não há CI que valide o PR.** O único workflow em `.github/workflows` é
   `python-publish.yml`, que publica no PyPI. **O repositório não tem nenhum teste.**

## O patch que proponho

```diff
diff --git a/src/lugo4py/src/specs.py b/src/lugo4py/src/specs.py
--- a/src/lugo4py/src/specs.py
+++ b/src/lugo4py/src/specs.py
@@ -92,7 +92,7 @@ GOALKEEPER_JUMP_SPEED = 2 * player_max_speed
 GOALKEEPER_NUMBER = 1

 # GOALKEEPER_SIZE is the width of the goalkeeper
-GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,
+GOALKEEPER_SIZE = PLAYER_SIZE * 2.3

 # Number of turns each teams has on attack before losing the ball possession.
 SHOT_CLOCK_TIME = 300
```

Verifiquei que ele aplica limpo no `master` atual (`git apply --check` passa) e que
depois da correção `GOALKEEPER_SIZE` vira o float `919.9999999999999` e a aritmética
funciona.

## Decisões sobre as quais quero sua opinião

**(a) Manter a expressão ou trocar por um literal?** Optei por manter
`PLAYER_SIZE * 2.3` em vez de escrever `920`, para que o valor Python continue
bit a bit igual ao do cliente JS (`400 * 2.3` em ponto flutuante dá
`919.9999999999999`, não `920`). Detalhe que descobri depois: em Go, `GoalkeeperSize`
é uma constante não-tipada de precisão arbitrária, então lá o valor é 920 exato — o
artefato de float não existe. Isso significa que os três clientes já divergem
ligeiramente entre si hoje. Mantenho a expressão, ou escrevo `920`, ou proponho as duas
e deixo o mantenedor escolher?

**(b) A quebra de compatibilidade é uma objeção real?** Se alguém já contornou o bug
escrevendo `GOALKEEPER_SIZE[0]`, o patch quebra esse código. Acho o argumento fraco
(consertar um tipo obviamente errado vale mais que preservar o contorno de um bug), mas
quero saber se você discorda, e se eu deveria mencionar isso proativamente no PR.

**(c) Issue, PR, ou os dois?** Meu plano era abrir a issue com a reprodução **e** o PR
anexado, com a issue referenciando o número do PR. O raciocínio é que uma issue sozinha
morreria como a #33 do próprio mantenedor. Faz sentido, ou abrir os dois é ruído para
uma correção de um caractere?

**(d) Vale abrir, dado o item 5?** O custo é de dez minutos e o material já está pronto.
O risco que enxergo não é rejeição, é silêncio. Há alguma desvantagem em abrir um PR que
provavelmente nunca será respondido, que eu não esteja considerando?

## O corpo do PR que escrevi

Critique o texto: tom, tamanho, o que está sobrando, o que está faltando, e se algo
soaria condescendente para o mantenedor.

---

## Problem

`GOALKEEPER_SIZE` is defined with a trailing comma, which makes it a **tuple** instead of
a number. Any arithmetic on it raises `TypeError`, so the constant cannot be used for
anything.

```python
# pip install lugo4py==1.0.5
from lugo4py import specs

print(repr(specs.GOALKEEPER_SIZE))   # (919.9999999999999,)   <- tuple
print(repr(specs.PLAYER_SIZE))       # 400                    <- int, as expected

specs.GOALKEEPER_SIZE / 2
# TypeError: unsupported operand type(s) for /: 'tuple' and 'int'
```

Source, `src/lugo4py/src/specs.py`:

```python
GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,
#                                  ^ this comma
```

## Why it went unnoticed

Nothing inside the package uses `GOALKEEPER_SIZE` — it is only consumed by bot authors,
so the import never fails and no internal test exercises it.

## Cross-check with the sibling clients

Both other clients define the same constant correctly, which suggests the Python version
was transliterated from the JS object literal, where the trailing comma is a harmless
property separator:

| client | definition | correct? |
|---|---|---|
| Go — `lugo4go/specs/specs.go` | `GoalkeeperSize = PlayerSize * 2.3` | yes |
| JS — `lugo4node/src/specs.ts` | `GOALKEEPER_SIZE: player_size * 2.3,` | yes (object literal) |
| Python — `lugo4py/src/lugo4py/src/specs.py` | `GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,` | **no — tuple** |

The constant was added in #31 / #32.

## Fix

Removes the trailing comma. After the change:

```python
print(repr(specs.GOALKEEPER_SIZE))   # 919.9999999999999
print(specs.GOALKEEPER_SIZE / 2)     # 459.99999999999994
```

I kept the expression `PLAYER_SIZE * 2.3` untouched so the value stays identical to the
JS client. Happy to change it to a literal `920` instead if you prefer.

---

## O que eu quero de você

1. Há **algum erro factual ou técnico** no que afirmei acima? Aponte.
2. Há algum efeito colateral do patch que eu não vi?
3. Sua resposta a cada uma das quatro decisões (a) a (d), com o motivo.
4. Uma crítica direta do corpo do PR: o que você cortaria, o que reescreveria.
5. No fim, um veredito de uma linha: **abrir** ou **não abrir**, e por quê.

Não amenize. Se a conclusão honesta for "isso é irrelevante e não vale o tempo de
ninguém", diga exatamente isso.
