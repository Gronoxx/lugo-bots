# Como abrir o PR (candidato 1 da triagem)

Revisado em 26/08/2026, depois de consultar três avaliações externas.

**Decisão: abrir APENAS o PR, sem issue separada.** Para uma correção de um
caractere, o PR já é o relatório do bug; abrir os dois é burocracia para uma fila
que ninguém está triando. O arquivo `lugo4py_goalkeeper_size_ISSUE.md` fica no
diretório só como registro do caminho descartado.

**Idioma: português.** O mantenedor é brasileiro e escreve issues em português
(a #33 é dele, inteira em português). O código e os comentários não são tocados
pelo patch — ele só remove um caractere.

Pré-requisito: `gh auth login` — o `gh` mantém a própria credencial, separada
da que o `git push` deste repositório usa.

```bash
gh auth login                      # uma vez, interativo

git clone https://github.com/lugobots/lugo4py.git /tmp/lugo4py
cd /tmp/lugo4py
git config user.email "100954782+Gronoxx@users.noreply.github.com"   # NÃO expor e-mail pessoal
git config user.name  "Gustavo"

git checkout -b fix-goalkeeper-size-tuple
git apply <caminho-deste-repo>/results/upstream/lugo4py_goalkeeper_size.patch
git commit -am "corrige GOALKEEPER_SIZE: virgula final a torna uma tupla"

gh repo fork --remote=false --clone=false          # cria o fork sob Gronoxx
git remote add fork https://github.com/Gronoxx/lugo4py.git
git push fork fix-goalkeeper-size-tuple

gh pr create --repo lugobots/lugo4py \
  --title "Corrige GOALKEEPER_SIZE: vírgula final a torna uma tupla" \
  --body-file <caminho-deste-repo>/results/upstream/lugo4py_goalkeeper_size_PR.md
```

## Verificação já feita (revalidada em 26/08/2026)

| checagem | resultado |
|---|---|
| bug no pacote publicado 1.0.5 | sim — `(919.9999999999999,)`, `TypeError` em qualquer aritmética |
| bug no `master` atual (`7f4a257`) | sim — `src/lugo4py/src/specs.py:95` |
| o patch aplica limpo hoje | sim — `git apply --check` passa |
| valor depois da correção | `919.9999999999999` (float); `/2 = 459.99999999999994` |
| é API pública de primeiro nível? | **sim** — `__init__.py:26` faz `from .src.specs import *`, então `lugo4py.GOALKEEPER_SIZE` existe |
| clientes Go e JS | corretos (evidência de que é engano, não intenção) |
| Go tem o mesmo artefato de float? | **não** — constante não-tipada em Go dá 920 exato; o valor Python é idêntico ao do **JS**, não ao do Go |
| issue/PR já existente | nenhuma em 34 varridas |
| CI valida o PR? | não — o único workflow é `python-publish.yml`; o repositório **não tem testes** |
| repositório mantido? | **não** — último commit 2024-09-09 (23,5 meses); issue #33 do próprio mantenedor sem resposta há 23 meses |
| PRs externos são aceitos? | **sim, historicamente** — 14 de 16 mergeados, mediana ~1 dia; o último em março/2024 |

## Decisões de conteúdo (e por quê)

| decisão | escolha | motivo |
|---|---|---|
| expressão ou literal `920` | manter `PLAYER_SIZE * 2.3` | mantém o valor idêntico ao JS e acompanha `PLAYER_SIZE` se ele mudar; diff mínimo |
| oferecer o `920` ao mantenedor | **cortado** | convida discussão num repo sem ninguém para discutir; assumir a decisão é menos atrito |
| citar a quebra de compat. (`[0]`) | **não citar** | levantar a lebre cria debate de SemVer sem necessidade; se perguntarem, responde-se na hora |
| arqueologia (quem introduziu, por que ninguém viu) | **cortada** | soa condescendente e não ajuda o merge |
| tabela Go/JS/Python | **comprimida em uma frase** | o argumento causal sobrevive sem empurrar a correção para baixo da dobra |

O candidato 2 (mira do `make_order_kick`) está descrito em
`results/UPSTREAM_TRIAGEM.md` e **não tem código pronto** — o script de
reprodução nunca foi salvo como arquivo. Continua não valendo a pena: o mesmo
cálculo existe no cliente Go, então é desenho da biblioteca, e o desfecho
provável é correção de documentação.
