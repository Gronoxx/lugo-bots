# Prompt para a sessão de RL — trabalhar EM CIMA do trabalho heurístico

> Cole isto na sessão de RL. Ela foi concluída (a finalização heurística terminou) e
> agora tem contexto novo que muda a estratégia de RL.

---

Contexto: outra sessão terminou o trabalho HEURÍSTICO de decisão (quando passar,
condução/marcação, finalização, cobertura) e colheu dados na PLATAFORMA real. Isso
muda onde o RL deve focar. Leia antes de retomar o RL.

## 1. Realidade da plataforma (régua forte real)
Bot `patrick-estrela` (config = v9 + Fase A ON) vs o topo: **level-3 2–1 (V), BotAdversario4
0–0 (E), BotAdversario1 0–1 (D)** → 1V-1E-1D, n=1/adversário (ruidoso). **Somos competitivos com
o topo** — a estimativa pessimista caiu.
- **Gargalo MEDIDO = CRIAÇÃO vs boa defesa**, NÃO finalização. Em 2 dos 3 jogos fizemos 0
  gols e sofremos pouquíssimo (0,0,1). Defesa forte; contra boa defesa **nem criamos o
  suficiente para chegar a finalizar**. → o alvo de maior valor é **quebrar defesa
  organizada / criação**, não o chute.

## 2. O que a régua forte (self-play) mostrou — confirma a conclusão do RL
`bench/ab_selfplay.py --test '<genes>'` (nosso bot vs si; um lado com o gene, outro a base
Fase A; alterna lados). **Baixa variância (se≈0,1), sinal SIGNIFICATIVO** — é a melhor régua
LOCAL (muito melhor que vs rivais fracos, onde gols são só ruído). Resultado: **TUDO que a
sessão heurística adicionou EMPATA ou PERDE vs a base** — planejador −2,6; condução por Casos
neutro; marcação-por-área pior que raio; tática por placar ~0; finalização −0,12/0; 8 genes
dormentes todos n.s. **O ÚNICO ganho validado = escape/status (+0,28).**
- ⇒ **A base v9/Fase A é MUITO forte.** Isso corrobora a sua conclusão (RL-do-zero não bate
  o v9). Ajustes de decisão contra o nosso próprio bot estão saturados. **O ganho restante
  exige régua externa (plataforma) ou um método fundamentalmente diferente (RL bem-mirado).**

## 3. Estratégia de RL recomendada (o pivô, refinado)
NÃO fazer RL do zero (estrutural: não bate o v9; você já mostrou). Fazer **módulo(s) ESTREITO(s)
aprendido(s) EM CIMA do v9, A/B-gated vs v9 puro (nunca pior que o v9)**. Priorize por valor:
1. **CRIAÇÃO vs defesa organizada** (o gargalo medido): política aprendida de **movimentação
   sem bola / build-up** que abre linhas contra uma defesa boa. A heurística de condução deu
   neutro; é sequencial e difícil de afinar à mão → bom para RL. Reward = criação de chance
   (proxy densa) + gols na plataforma; não-farmável, esforço-based (lição lugo-rl-training).
2. **Opponent-modeling**: aprender `P(posição do defensor | estado)` para explorar o vão entre
   pior-caso e defesa real (medimos: o conjunto seguro por pior-caso encolhe muito mais rápido
   que vs a defesa real — gap 0→27pp em t=10). RL/predição de oponente é a rota para "horizonte
   longo em esperança" (garantia determinística longa é vazia — provado).
3. **Finalização = manobrar o goleiro** (timing sequencial vs goleiro reativo): a heurística não
   cravou; um módulo aprendido PODE — MAS só valide no **servidor real**, nunca no fastsim.

## 4. Guardrails (críticos — vêm dos nossos dados)
- **fastsim tem mecânica de goleiro/zona ERRADA** (catch = argmin ≠ servidor; zona-1400 só no
  gol adversário; no servidor real vale nos DOIS gols). Foi por isso que o BC do v9 falhou.
  ⇒ **NÃO treine nada dependente de goleiro/finalização/zona no fastsim** — use o servidor real.
- **wait mode é NÃO-determinístico aqui** → não compare replays byte-a-byte; meça por estatística
  (self-play/proxy) ou no nível de decisão (`bench/decide_dump.py`).
- **Integrar como GENE default-off** (regra do projeto: versão = gene, default = v9), e **A/B-gate
  cada módulo vs v9 puro** no self-play E na plataforma. Nunca fica pior que o v9.
- Espere ganhos PEQUENOS: a base é forte. Não re-fazer seleção de passe/drible (medido neutro/
  negativo). O frontier é CRIAÇÃO + opponent-modeling.

## 5. Recursos prontos (reuse — não reconstruir)
Base: branch **`fase-a-passe`** em `~/lugo-bots`. Trabalho heurístico: branch **`quando-passar`**
(worktree `~/lugo-quando-passar`), tudo default-off.
- **Régua/ferramentas:** `bench/ab_selfplay.py` (self-play, régua forte), `bench/proxy_metric.py`
  (good_chance_rate, danger_poss, best_slack — baixo ruído), `analysis/frente2_possession.py`
  (composição de turnover), `bench/pull_matches.py` (puxa placares/vídeos da plataforma),
  `bench/decide_dump.py` (inércia no nível de decisão). Plataforma = VÍDEO (sem JSON); re-submeter
  é livre; deep-forense só em jogos locais (docker→JSON).
- **Primitivos reusáveis** (bot/src): `geometry.py` (`intercept_risk` = folga contínua de
  interceptação; `turns_for_ball/player`; `_apply_server_kick` = modelo de chute inferido, mas
  empiricamente BOM); `planner.py` (`leg_slack` = linha viável com discos inflados por horizonte);
  `carry.py` (`dribble_freedom` = ÁREA de condução segura = marcação por área/direção);
  `shooting.py` (`coverage_prob` = openness PROBABILÍSTICA por profundidade — a "moeda" de
  pitch-control; `keeper_expected_y`; `shot_slack` com pulo; `best_goal_shot`).
- **Física verificada:** jogador 100/turno, sem colisão, bola grudada 200 à frente, captura por
  proximidade ~300 (goleiro ~560, pulo 200×3 travado); bola 400/turno, decel 10, d(t)=v0t−5t²;
  zona-1400 nos DOIS gols; goleiro CENTRADO cobre a boca toda de 1400 (slack −635) → gol exige
  DESLOCAR o goleiro.
- **Docs/memória:** `results/HANDOFF_QUANDO_PASSAR.md`; memórias `lugo-selfplay-ruler`,
  `lugo-wait-nondeterminism`, `lugo-firsttouch-ablation`, `lugo-goal-zone-rule`, `lugo-rl-training`,
  `lugo-env-reference`.

## 6. Ganhos heurísticos prontos p/ ligar (contexto — não é tarefa de RL)
`pass_status_mode=on` (escape/status, +0,28, único ganho validado) e `cover_mode=on` (cobertura
anti-banheira — pluga o gol de contra-ataque sofrido vs BotAdversario1). Genoma de produção sugerido:
`{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on","cover_mode":"on"}`.
O RL entra ONDE a heurística não chega: **criação vs boa defesa**.

## 7. Tarefa
Retome o RL com foco em **criação vs defesa organizada** (item 3.1) como módulo estreito sobre o
v9, A/B-gated no self-play e re-submetido à plataforma. Comece propondo o desenho do módulo
(entrada/saída, como pluga no v9, reward não-farmável, ruler) antes de treinar. Reuse os
primitivos acima. Reporte com números da régua (self-play + proxy; plataforma quando possível).
