# Abrir o PR manualmente pela interface do GitHub

Fork ainda não existe (`https://api.github.com/repos/Gronoxx/lugo4py` → 404 em
26/08/2026). Conta: `Gronoxx`, id `100954782`.

---

## Passo 0 — ANTES DE TUDO: esconder o e-mail

https://github.com/settings/emails

Commits feitos pela interface web são assinados com o e-mail da conta. Marque:

- [x] **Keep my email addresses private**
- [x] **Block command line pushes that expose my email**

Com isso o commit sai como `100954782+Gronoxx@users.noreply.github.com`.
**Sem isso, o e-mail pessoal vai para o histórico público do lugo4py e não sai mais.**

Confira na mesma página que o noreply mostrado é exatamente
`100954782+Gronoxx@users.noreply.github.com`.

---

## Passo 1 — Criar o fork

https://github.com/lugobots/lugo4py/fork

- Owner: `Gronoxx`
- Nome: `lugo4py` (deixe como está)
- [x] **Copy the master branch only** — pode deixar marcado

Resultado: `https://github.com/Gronoxx/lugo4py`

---

## Passo 2 — Editar o arquivo (cria o branch e o commit)

https://github.com/Gronoxx/lugo4py/edit/master/src/lugo4py/src/specs.py

Vá até a **linha 95**. O trecho é:

```python
 94| # GOALKEEPER_SIZE is the width of the goalkeeper
 95| GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,
 96|
```

Apague **só a vírgula** do fim da linha 95. Deve ficar:

```python
GOALKEEPER_SIZE = PLAYER_SIZE * 2.3
```

Clique em **Commit changes...** e preencha:

- **Commit message:**
  ```
  corrige GOALKEEPER_SIZE: virgula final a torna uma tupla
  ```
- **Extended description:** deixe vazio
- Marque **Create a new branch for this commit and start a pull request**
- Nome do branch:
  ```
  fix-goalkeeper-size-tuple
  ```
- **Propose changes**

---

## Passo 3 — Abrir o PR

O passo 2 já leva para a tela de abrir o PR. Se perder, use:

https://github.com/lugobots/lugo4py/compare/master...Gronoxx:lugo4py:fix-goalkeeper-size-tuple

**Confira o cabeçalho antes de submeter:**

```
base repository: lugobots/lugo4py    base: master
head repository: Gronoxx/lugo4py     compare: fix-goalkeeper-size-tuple
```

O diff mostrado tem que ser exatamente **1 linha alterada, 1 caractere**.

- **Título:**
  ```
  Corrige GOALKEEPER_SIZE: vírgula final a torna uma tupla
  ```
- **Corpo:** cole o conteúdo de `lugo4py_goalkeeper_size_PR.md` (mesma pasta)
- Não marque "Draft"
- **Create pull request**

---

## Passo 4 — Conferir depois de criado

1. Abra a aba **Commits** do PR e clique no hash do commit. O autor tem que
   aparecer como `Gronoxx`, e o e-mail (visível no `.patch` do commit, é só
   acrescentar `.patch` na URL) tem que ser o `noreply`. **Se aparecer o e-mail
   pessoal: feche o PR, apague o branch e o fork, corrija o Passo 0 e refaça.**
   Depois que o commit entra num repositório público, o e-mail fica em caches e
   espelhos mesmo que você apague.
2. Aba **Files changed**: `1 changed file`, `+1 −1`.
3. Anote o número do PR aqui: `#____`

Lista de PRs do upstream: https://github.com/lugobots/lugo4py/pulls

---

## O que esperar

Nenhuma resposta é o desfecho mais provável: o `master` do lugo4py não recebe
commit desde 09/09/2024, e a issue #33 — aberta pelo próprio mantenedor — está há
23 meses sem um comentário. Historicamente, porém, 14 de 16 PRs de fora foram
mergeados, com mediana de ~1 dia. Não há CI para rodar: o único workflow publica
no PyPI e o repositório não tem testes.
