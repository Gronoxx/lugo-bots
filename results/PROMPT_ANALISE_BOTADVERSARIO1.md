# Prompt — análise da derrota 3-0 vs BotAdversario1 + plano de ação

> Cole numa nova sessão. Objetivo: pegar os dados desta derrota, analisar o que dizem
> sobre o time, forense no CÓDIGO, identificar as causas e gerar um PLANO DE AÇÃO
> priorizado. NÃO implementar ainda — diagnóstico + plano primeiro.

## Contexto
- Bot `killua-zoldyck` (imagem v2 = Fase A + `pass_status_mode` + `cover_mode`), submetido à
  plataforma lugobots.ai. Código no worktree **`~/lugo-quando-passar`** (branch `quando-passar`),
  sobre `fase-a-passe`. (`~/lugo-bots` é o `fase-a-passe`, código antigo — outra sessão de RL
  trabalha lá; NÃO mexer.)
- Histórico plataforma: v9+FaseA deu 1V-1E-1D vs o topo (level-3 2-1, BotAdversario4 0-0, BotAdversario1 0-1).
  Agora com status+cover: **BotAdversario1 0-3 (PIOR).**
- **Régua forte local = self-play** (`bench/ab_selfplay.py`). No self-play, TUDO que adicionamos é
  neutro/negativo EXCETO `pass_status_mode` (+0.28); `cover_mode` neutro-seguro (+0.08, 0 derrotas).
  **⚠️ O self-play é CEGO para os problemas desta derrota** (nosso bot não faz banheira/pressão
  contra si → transição defensiva e cobertura NUNCA são testadas no self-play). Foi por isso que
  cover/status pareceram "seguros" e falharam vs BotAdversario1. Ver §Régua.

## ⚠️ PASSO 0 — confirmar qual imagem jogou
Houve confusão de imagem (build na pasta errada, v1/v2). ANTES de analisar, confirmar que o 3-0 foi
com a **v2 forte** (FA+status+cover) e não a antiga: página do bot (digest = `f49f787f…` / config
`42cd1bc0…`) OU pelo comportamento no vídeo (há zagueiro marcando o parado? há escape?). Se foi a
antiga, cover/status não estavam ligados e a análise muda.

## Dados da partida (0-3 vs BotAdversario1)
- **Poucos chutes ao gol** → finalização conservadora demais; sem rebote NOSSO (não pressionamos o rebote).
- **Passes: nós 143 @ 93.6% vs BotAdversario1 229 @ 92.3%** → acerto ~igual, mas **volume MUITO menor** (passamos pouco; dribla-se muito).
- **Os 3 gols sofridos:**
  1. **Rebote** — BotAdversario1 marcou de rebote (nós não aproveitamos os nossos; eles aproveitaram).
  2. **Banheira** — nosso zagueiro recuperou a posse e **perdeu logo depois conduzindo em direção a um adversário**.
  3. **Banheira (#9 deles)** — nosso zagueiro recuperou, **tentou um passe para sair da zona defensiva, foi interceptado** → gol.

## Fraquezas (hipóteses — CONFIRMAR em dados + código)
1. **Transição defensiva (sair jogando) — o #1 (2 dos 3 gols).** Ao recuperar no campo defensivo,
   perdemos a posse (condução para a pressão OU passe interceptado). A lógica de "para onde conduzir
   / é perigoso / há passe melhor" está RUIM no campo defensivo. Status/escape e cover deveriam
   mitigar — mas o gol recorreu.
2. **Criação vs defesa sólida/numerosa.** Uma só heurística de ataque; volume de passe baixo (143 vs
   229); atacantes mal posicionados (não fazem "banheira ofensiva" como eles) → não quebramos defesa
   boa → poucos chutes.
3. **Finalização conservadora.** Poucos chutes; sem rebote nosso. `finish_mode` está OFF (rejeitado
   no self-play, −0.12) — reavaliar; chutar mais / caçar rebote pode valer vs defesa que aglomera.
4. **cover_mode não plugou a banheira.** Confirmar se dispara (gene `cover_range=8000` pode ser
   grande demais → over-trigger, ou o pareamento falha) e se o problema é a MARCAÇÃO ou a TRANSIÇÃO.

## Forense no CÓDIGO — pistas concretas (worktree ~/lugo-quando-passar/bot/src)
- **Quem decide a saída do zagueiro com a bola:** `my_bot.on_holding` → em produção (status on,
  hold_logic OFF): chute(não) → `_best_pass` (com escape do status) → senão cascata v9
  (`_touch_target`/`_carry_target`). O `_carry_target` (my_bot.py ~548) conduz rumo ao gol com
  repulsão, **SEM gate de interceptação no alvo** → provável causa do gol 2 (conduz para a pressão).
- **Gol 3 (passe interceptado):** `_best_pass` só aceita passe que passa no veto
  (`can_be_intercepted`/`leg_slack`, geometry.py). Se saiu um passe interceptado, ou (a) o veto é
  ESTÁTICO e o adversário fechou depois (use_velocity OFF por default → não extrapola), ou (b) a bola
  saiu mais fraca que a planejada (first-touch/`achievable_shot_speed`) e deu tempo. Investigar o veto
  do passe de SAÍDA sob pressão (turnos até o interceptador).
- **Escape (Comp 1):** `_player_status` + retenção em atenção/perigo (my_bot `_best_pass`). Confirmar
  que dispara para ZAGUEIROS e que, quando preso, existe um reciclo seguro (senão cai no carry sem gate).
- **cover_mode:** `_cover_target` (on_supporting) marca o parado — mas o zagueiro COM a bola está em
  `on_holding`, não supporting; cover não protege o carregador. E se o nosso play-out entrega a bola
  na frente do gol, o parado capitaliza mesmo marcado. ⇒ a RAIZ é a transição, não só a marcação.
- Genes relevantes: `pass_status_mode`, `cover_mode`/`cover_range`/`cover_count`, `use_velocity`,
  `pass_endpoint_race`, `hold_logic`, `carry_mode`. (params.py)

## Régua — CRÍTICO
- **Self-play é cego para transição/banheira** (nosso bot não pressiona/estaciona contra si). Para
  medir estes problemas: **construir um sparring "banheira/pressing"** (um bot que estaciona 2
  atacantes no nosso campo e pressiona a saída) e A/B contra ele medindo GOLS SOFRIDOS e turnover no
  terço defensivo; OU validar na plataforma (re-submeter é livre, mas lento/ruidoso — n≥10).
- Ferramentas: `bench/ab_selfplay.py`, `bench/proxy_metric.py`, `analysis/frente2_possession.py`
  (composição de perda: "conducao tomada" vs "passe interceptado", por terço), `bench/why_pass.py`
  (forense de decisão em replays LOCAIS), `bench/decide_dump.py` (inércia off=v9),
  `bench/pull_matches.py` (placares/vídeos da plataforma — vídeo só, sem JSON).
- Física: jogador 100/turno sem colisão; bola grudada 200; captura ~300 (GK 560, pulo 200×3);
  zona-1400 nos DOIS gols; bola 400 decel 10; wait mode NÃO-determinístico (medir por estatística).
  fastsim tem goleiro/zona ERRADOS (não treinar isso lá).
- Docs/memória: `results/HANDOFF_QUANDO_PASSAR.md`, `results/PROMPT_RL_HANDOFF.md`; memórias
  `lugo-selfplay-ruler`, `lugo-goal-zone-rule`, `lugo-firsttouch-ablation`, `lugo-decision-quality`,
  `lugo-env-reference`, `lugo-wait-nondeterminism`.

## Tarefa
1. **Passo 0:** confirmar a imagem que jogou (v2 forte?).
2. **Vídeo:** puxar/gerar storyboard dos 3 gols (a plataforma dá só vídeo). Confirmar a mecânica de
   cada gol (rebote; banheira-condução; banheira-passe-interceptado).
3. **Código:** forense nas pistas acima — reproduzir a transição defensiva localmente vs um sparring
   "banheira/pressing" (construir) e/ou via `why_pass.py`/replays locais.
4. **Diagnóstico:** para cada fraqueza (transição defensiva, criação vs defesa sólida, finalização
   conservadora, cover), dizer a CAUSA no código + a evidência (dados/vídeo).
5. **Plano de ação priorizado** (não implementar ainda), por valor esperado:
   - (a) **Transição defensiva segura** (maior valor — 2 gols): sair da pressão sem perder posse
     (gate de segurança na condução do zagueiro; passe de saída robusto ao veto sob pressão;
     marcar o parado). 
   - (b) **Criação vs defesa sólida:** aumentar circulação/volume de passe; posicionamento ofensivo
     (nossa própria "banheira"/outlets); quebrar bloco baixo.
   - (c) **Finalização menos conservadora:** chutar mais / caçar rebote.
   Cada item: como GENE default-off, A/B-gated no self-play E num sparring adequado, validado na
   plataforma. Uma mudança por vez; medir; nunca pior que o v9.

## Lição transversal (não esquecer)
A base é fortíssima no self-play, mas a plataforma expõe o que o self-play não vê. **O gargalo real
vs o topo é: (1) transição defensiva sob pressão e (2) criação vs defesa sólida** — não a finalização
isolada. Priorizar (1) — foi o que custou 2 gols e é o mais concreto.
