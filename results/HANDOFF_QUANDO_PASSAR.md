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

## Resultados de validação
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
  ≤3 turnos); livre ⇒ dribla. 2ª rodada (com gate): [A PREENCHER]. Nota: a
  composição de posse é NÃO-confiável sob goleada (45×0 vira "1 posse" na
  segmentação) → usar GOLS como métrica sob blowout. Valor do planejador é uma
  aposta para oponente forte (plataforma); localmente o objetivo é "não piorar".

## Como testar (comandos)
```
PY=<caminho local>   # worktree nao tem .venv proprio
# inercia (off = v9):
PYTHONPATH=~/lugo-bots/bot/src:~/lugo-bots/analysis   $PY bench/decide_dump.py <replay> > base.txt
PYTHONPATH=~/lugo-quando-passar/bot/src:~/lugo-quando-passar/analysis $PY bench/decide_dump.py <replay> > qp.txt
diff base.txt qp.txt   # vazio = inerte
# efeito:
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
