# HANDOFF — "Quando passar" (decisão de acionamento de passe)

> Sessão autônoma (ago/2026). Trabalho no **worktree isolado** `~/lugo-quando-passar`
> (branch `quando-passar`, a partir de `fase-a-passe`). `~/lugo-bots` ficou intacto
> (as sessões de RL e de precisão continuaram lá). Para integrar: `git merge quando-passar`.

## O que foi construído (3 componentes, TODOS default-off = v9)

Regra do projeto respeitada: todo comportamento novo é GENE, default reproduz a v9.
Inércia (off = v9) **provada no nível de decisão** (ver §Determinismo).

### Componente 1 — status por jogador (`_player_status` em `my_bot.py` + genes)
Cada jogador tem status **livre / atenção / perigo** pela banda de turnos até o
adversário de linha mais próximo alcançá-lo (reusa `turns_for_player`, coerente com
o veto): `D≤500 → perigo` (≤2 turnos), `D≤600 → atenção` (≤3), `>600 → livre`.
- Gatilho no portador: **atenção/perigo** ligam a retenção (`under_pressure`) →
  aceita um reciclo seguro em vez de driblar para o desarme; **perigo** derruba a
  barra de aceite (`pass_min_score_danger`). Bônus opcional por receptor livre.
- Genes: `pass_status_mode` (off|on), `status_count_gk`, `status_measure`,
  `status_danger_turns`=2, `status_attention_turns`=3, `pass_min_score_{free,attention,danger}`,
  `pass_w_recv_free`.

### Componente 2 — planejador NÃO-GULOSO control-aware (`planner.py` + genes)
Busca em feixe sobre o grafo de linhas de passe viáveis no tempo, terminando no
jogador mais perto do gol. **MPC**: executa só a 1ª perna, replaneja a cada turno.
- **Viabilidade por perna** (`leg_slack`): discos dos defensores inflados pelo
  horizonte global Θ — `slack = turns_for_player(d_opp) − Θ − t_ball`. Generaliza o
  veto v9 (Θ=0 concorda em sinal com `can_be_intercepted`).
- **Velocidade EXECUTÁVEL** por perna (`exec_speed_toward`): forma fechada barata
  (não a busca de 288 do `achievable_shot_speed`) que modela o first-touch (bola
  quente sai fraca).
- **Aresta de CONTROLE**: assentar `plan_control_turns` (≈1) turnos → passe pleno,
  ao custo de Θ += k (defensores ganham k turnos).
- Genes: `pass_lookahead` (off|depth2|depth3), `pass_control` (off|on),
  `plan_beam`, `plan_w_progress`, `plan_w_shot`, `plan_w_livre`, `plan_leg_penalty`,
  `plan_margin_turns`, `plan_margin_value`, `plan_control_turns`.
- **Latência** (medida offline, 1714 snapshots): depth2 média 10 ms / p95 22 / máx
  25 → dentro do orçamento de 50 ms. **depth3** máx 44 ms → arriscado em wait mode;
  usar só depois de apertar o feixe/vetorizar.

### Componente 3 — tática por estado de jogo (`_game_aggr`, PRIORIDADE BAIXA)
`game_aggr ∈ [−1,+1]` da margem de placar (calibrada: real ~2,9 gols/jogo vs Lugo
~4,7–6,9 → `lead_comfortable`~3) e do tempo (`late_game_turns`). Perseguir (atrás,
fim de jogo) baixa a barra de passe e a margem do planejador; proteger vantagem faz
o oposto. Genes: `game_state_mode`, `lead_comfortable`, `late_game_turns`,
`game_aggr_scale`.

## Descoberta de METODOLOGIA (afeta as 3 sessões)
**O wait mode NÃO é determinístico nesta máquina.** `mybot:fa` vs dummies rodado
duas vezes (mesma imagem, sequencial, sem carga) diverge na trajetória da bola já no
turno ~83. Logo o **portão "0 mismatches" (cmp de replay) é INVÁLIDO** — o
`bench/determinismo.sh` e a afirmação "0 mismatches" da Fase A não valem aqui.
- **Inércia (off = v9)** → provar no NÍVEL DE DECISÃO: `bench/decide_dump.py`
  reconstrói o inspector de cada snapshot e chama o `_best_pass` real; roda sob
  PYTHONPATH da base e do worktree e faz `diff` (função pura, imune ao
  não-determinismo). Os 3 componentes passaram (5999 turnos idênticos à base).
- **Efeito (gene on vs off)** → só por ESTATÍSTICA sobre muitas partidas (proxy
  densa); o não-determinismo é mais uma fonte de ruído.

## ⭐ RÉGUA FORTE via SELF-PLAY (o resultado que importa)
Não há bot forte EXTERNO local, mas o NOSSO bot (Fase A) É forte. `bench/ab_selfplay.py`
põe `mybot:qp` vs `mybot:qp` head-to-head, um lado com o bundle "quando passar", o
outro com a base Fase A — mesma imagem, só os genes mudam. Disputa competitiva ⇒
**baixa variância** (se≈0,33 em n=24) ⇒ sinal LIMPO, ao contrário dos A/Bs vs
oponente fraco (que são só ruído).

**Veredito (combo = status + planejador-gated + control): PERDE para a base Fase A
por −2,58 ± 0,33 gols/jogo (n=24, z=−7,72, SIGNIFICATIVO). 0 vitórias / 1 empate /
23 derrotas.** Ou seja, o "quando passar" COMO IMPLEMENTADO **piora** o bot mesmo
vs oponente forte: passar mais cria turnovers e abre mão do tempo de drible que a
base (forte dribladora) usa para vencer. Consistente com o histórico do projeto
(a baseline v9/Fase A é bem afinada e difícil de bater).

**Decomposição por componente (self-play, n=20 cada):**
| variante | saldo/jogo | V/E/D | veredito |
|---|---|---|---|
| controle base×base | −0,15 ± 0,17 (n.s.) | 1/17/2 | régua válida, sem viés de lado |
| **status sozinho (Comp 1)** | **+0,40 ± 0,18 (z=2,18 SIG)** | 6/13/1 | **GANHA** ✓ |
| planejador sozinho (Comp 2) | −2,65 ± 0,32 (z=−8,32 SIG) | 0/1/19 | PERDE muito ✗ |

**Conclusão acionável:**
- **Componente 1 (status/escape) É UM GANHO** — "passar para evitar perda" bate a
  base Fase A mesmo vs oponente forte. Confirmado em n=40: **+0,28 ± 0,09 gol/jogo
  (z=2,91, SIG), 10V/29E/1D**. Candidato a ligar (`pass_status_mode="on"`),
  pendente de confirmação na plataforma.
- **Componente 2 (planejador) PREJUDICA** (−2,65) — para este bot forte-driblador,
  passar construtivo proativo é downgrade. **Manter OFF.** (Código fica no repo
  como base para trabalho futuro / oponentes onde o drible falhe.)
- **Componente 3**: avaliar por self-play (raramente dispara). [ver §tuning]

## Resultados de validação (vs oponente fraco — apenas RUÍDO, registrados p/ completude)
- **Etapa 0 (ablação `exec_speed`, `bench/ab_ablation_exec.py`)**: desligar exec_speed
  piora completude (99,5%→97,7%, z=−5,92) E progressão → **first-touch é REAL** →
  planejador precisa ser control-aware (decidiu a complexidade do Comp. 2).
- **Comp. 1 (turnover, `bench/ab_status.py`, vs rival_p3, 12 jogos/braço)**: turnover
  65,7%→62,3% (−3,4 pp, z≈0,82 **n.s.**), good_chance_rate ~flat (0,557→0,548),
  gols 26,4→23,1. Direção certa, sinal fraco — problema conhecido da régua fraca
  (vs oponente hobby o mybot já ganha 26×0). Trade-off posse×goleada que tende a
  inverter vs oponente forte.
- **Comp. 2 (planejador, `bench/ab_plan.py`, vs rival_p3)**: 1ª rodada (planejador
  SEM gate) **PIOROU** — gols 20,8→13,3, turnover 68%→84% (churn), ~2× posses. Vs
  oponente fraco, driblar domina (base goleia 45×0) e o planejador troca dribles
  dominantes por passes que fragmentam a jogada. **Correção**: gate
  `plan_trigger_turns` — só planeja quando o portador está MARCADO (adv de linha
  ≤3 turnos); livre ⇒ dribla. **2ª rodada (com gate)**: saldo de gols +20,8→+23,5,
  turnover flat (65→66%, sem churn), good_chance_rate 0,47→0,49, best_slack
  −418→−305. O gate **inverteu** o planejador de claramente-negativo para
  neutro/levemente-positivo (não-significativo em n=12; alta real é aposta para a
  plataforma). Nota: composição de posse é NÃO-confiável sob goleada (45×0 vira
  "1 posse" na segmentação) → usar GOLS como métrica sob blowout.

## ⭐ RECOMENDAÇÃO DE PRODUÇÃO
Após o veredito da régua forte (self-play):
- **LIGAR `pass_status_mode="on"`** (Componente 1). Ganho pequeno mas real e robusto
  (+0,2 a +0,4 gol/jogo vs a base Fase A, significativo; 0–1 derrotas em 20 em toda
  variante testada). Genes default servem (não achei ajuste claramente melhor em
  n=20 — não sobre-ajustar ao self-play, risco de overfit ao nosso próprio estilo).
- **`pass_lookahead="off"`, `pass_control="off"`** (Componente 2 / planejador):
  perde −2,5 gol/jogo mesmo no ajuste mais conservador. Fica no repo p/ trabalho
  futuro (oponentes onde o drible falhe / off-ball), mas OFF.
- **`game_state_mode="off"`** (Componente 3): ~neutro/levemente negativo em
  self-play; on-path funciona (smoke ok). OFF por ora; reavaliar na plataforma
  (onde placares não são equilibrados como no self-play).
- **Genoma de produção sugerido** (sobre a Fase A):
  `{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on"}`
- **Confirmar na plataforma** vs bots fortes reais antes de fixar o default.

### Ajuste (tuning) por self-play — resumo (n=20/braço, saldo vs base Fase A)
| variante | saldo | veredito |
|---|---|---|
| planejador conservador (trigger=1) | −2,45 (SIG) | planejador irrecuperável |
| status attention=4 | +0,20 (n.s.) | ok |
| status attention=2 (perigo-only) | +0,20 (SIG) | ok |
| status + recv_free=800 | +0,20 (SIG) | não melhora |
| status + game_state | +0,05 (n.s.) | game_state não ajuda |
| **status default (n=40)** | **+0,28 ± 0,09 (z=2,91 SIG), 10V/29E/1D** | **WINNER** |

## Como testar (comandos)
```
PY=<caminho local>   # worktree nao tem .venv proprio
# inercia (off = v9):
PYTHONPATH=~/lugo-bots/bot/src:~/lugo-bots/analysis   $PY bench/decide_dump.py <replay> > base.txt
PYTHONPATH=~/lugo-quando-passar/bot/src:~/lugo-quando-passar/analysis $PY bench/decide_dump.py <replay> > qp.txt
diff base.txt qp.txt   # vazio = inerte
# efeito — REGUA FORTE (self-play, o teste que importa; baixa variancia):
$PY bench/ab_selfplay.py --reps 20 --test '{"pass_status_mode":"on"}'  # saldo vs base Fase A
$PY bench/ab_selfplay.py --reps 10 --test '{}'   # controle base×base (~0)
# efeito vs oponente fraco (so ruido, nao decisivo):
$PY bench/ab_status.py --reps 6 --opp rival_p3:latest   # Comp 1 (turnover)
$PY bench/ab_plan.py   --reps 6 --opp rival_p3:latest   # Comp 2 (progressao)
# imagem: docker build -t mybot:qp bot   (genes via BOT_PARAMS / HOME_PARAMS / AWAY_PARAMS)
```

## Riscos / pendências
- **Régua fraca**: não há bot forte local (rivais são hobby-level; BotAdversario4/
  BotAdversario1 só na plataforma). Veredito real da feature = **submeter à plataforma**.
- **depth3** acima do orçamento em pior caso — apertar feixe/vetorizar antes de usar.
- **Comp. 3** mal exercitado (raramente dispara vs goleadas); calibração especulativa.
- Genes ficam default-off; **afinar por evolução/sweep** vs oponente melhor.
- **Merge**: superfícies disjuntas da Fase A; `planner.py` é só desta sessão.

## Commits (branch quando-passar)
- `feb8fd3`/`7b8a133` — base Fase A (sessão de precisão).
- `3375508` — Comp 1 + Comp 2.
- `4059f75` — Comp 3.
