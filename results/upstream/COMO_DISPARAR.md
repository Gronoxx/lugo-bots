# Como abrir o PR/issue depois (candidato 1 da triagem)

Decisão de 25/08/2026: **não publicar agora**. Tudo verificado e pronto; basta rodar.

Pré-requisito: `gh auth login` (hoje o `~/.config/gh/hosts.yml` está vazio — o `git push`
funciona por um token no `~/.git-credentials`, que o `gh` não lê).

```bash
gh auth login                      # uma vez

git clone https://github.com/lugobots/lugo4py.git /tmp/lugo4py
cd /tmp/lugo4py
git config user.email "100954782+Gronoxx@users.noreply.github.com"   # NÃO expor e-mail pessoal
git config user.name  "Gustavo"

git checkout -b fix-goalkeeper-size-tuple
git apply <caminho-deste-repo>/results/upstream/lugo4py_goalkeeper_size.patch
git commit -am "fix(specs): remove trailing comma making GOALKEEPER_SIZE a tuple"

gh repo fork --remote=false --clone=false          # cria o fork sob Gronoxx
git remote add fork https://github.com/Gronoxx/lugo4py.git
git push fork fix-goalkeeper-size-tuple

gh pr create --repo lugobots/lugo4py \
  --title "fix(specs): GOALKEEPER_SIZE is a tuple due to a trailing comma" \
  --body-file <caminho-deste-repo>/results/upstream/lugo4py_goalkeeper_size_PR.md

# depois, com o número do PR em mãos, trocar <NUM> no corpo da issue:
gh issue create --repo lugobots/lugo4py \
  --title "GOALKEEPER_SIZE is a tuple, not a number (trailing comma in specs.py)" \
  --body-file <caminho-deste-repo>/results/upstream/lugo4py_goalkeeper_size_ISSUE.md
```

## Verificação já feita (não precisa repetir)

| checagem | resultado |
|---|---|
| bug presente no pacote publicado 1.0.5 | sim — `(919.9999999999999,)`, `TypeError` em qualquer aritmética |
| bug presente no `master` atual | sim — `src/lugo4py/src/specs.py:95` |
| correção resolve | sim — vira `float` 919.9999999999999; `(GK+BALL)/2 = 560.0` |
| clientes Go e JS | corretos (evidência de que é engano, não intenção) |
| issue/PR já existente | nenhuma em 34 issues/PRs varridas nos 4 repositórios |
| repositório mantido? | **não** — último commit no master em 2024-09-09; issue #33 do próprio mantenedor aberta há 23 meses sem resposta |

O candidato 2 (mira do `make_order_kick`) está descrito em `results/UPSTREAM_TRIAGEM.md`
e **não deve ser aberto agora** — o mesmo cálculo existe no cliente Go, então é desenho
da biblioteca, e o desfecho provável é correção de documentação.
