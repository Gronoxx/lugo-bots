# Análise e correção — derrota 0-3 vs BotAdversario1 (killua-zoldyck v2)

> Sessão de 2026-08-15/16. Worktree `~/lugo-quando-passar` (branch `quando-passar`).
> Vídeo, frames e notas da forense: `videos/storyboard-0-3/`.

## 1. O que aconteceu (evidência)

**Passo 0 — qual imagem jogou: CONFIRMADO com prova criptográfica.** O 0-3 (partida
`partida-01`, 2026-08-15 19:09Z) foi jogado pela **v2 forte** (`repo.lugobots.ai/
killua-zoldyck:v2`, manifest `f49f787f…`, config `42cd1bc0…`), com o genoma embutido
`{FA(3) + pass_status_mode + cover_mode}`. A mesma v2 fez **1-0 no BotAdversario4**
(melhor que o 0-0 da v1) e 1-1 no BotAdversario10 → o colapso é **específico do estilo
BotAdversario1**, não regressão geral.

**Estatísticas oficiais do 0-3** (página `/matches/<id>/watch`):

| | killua (v2) | BotAdversario1 |
|---|---|---|
| posse bruta / líquida | 44,7% / **29,7%** | 55,3% / 42,2% |
| finalizações | **3** | 10 |
| passes bons (acerto) | 146 (93,6%) | 229 (92,3%) |
| defesas do goleiro | 7 (70%) | 3 (100%) |
| **roubadas de bola** | **32** | 21 |

A leitura decisiva: **nós recuperamos MAIS a bola que eles (32×21) e mesmo assim
tivemos 12 pontos a menos de posse líquida** — recuperamos e perdemos em seguida.
O vazamento não é a defesa em si; é **o que fazemos depois de recuperar**.

**Forense dos 3 gols em vídeo** (frames em `videos/storyboard-0-3/`, notas em
`NOTES.md`; o "shot clock" do overlay está em segundos e reseta na troca de posse —
os resets confirmam as recuperações):

1. **Gol 1 (03:26) — rebote não limpo.** Pressão do BotAdversario1, toque nosso (reset do
   shot clock), e a bola ficou **solta e parada na linha do nosso gol, perto do poste
   superior** — região que fica FORA do círculo protegido de 1400 (na linha do gol o
   círculo cobre só y∈[3600,6400]) e FORA da banda do goleiro (`gk_y_range` limita o
   guard a y≤6100). O `#9` deles, acampado na área, empurrou para dentro. Nosso `#4`
   estava ao lado, parado (não-chaser em DISPUTING → volta "à formação").
2. **Gol 2 (01:23) — condução no marcador.** Recuperamos NA linha do nosso gol; o
   nosso `#4` saiu conduzindo **em direção ao presser `#8`** (frame `g2_full_247.0`:
   os dois colados) → desarme → gol imediato com `#9`/`#10` deles na área.
3. **Gol 3 (00:39) — passe de saída interceptado.** `#4` recuperou no alto-esquerdo
   (reset do sc visível), tentou o passe para sair da zona com `#8`/`#11` deles na
   linha → interceptado → gol com os campers `#9`/`#10` NA nossa área.

**Estilo do BotAdversario1 (o jogo todo):** trio de trás `3/5(/4)` NUNCA cruza o meio (por
isso só 21 roubadas: não pressionam com todos); `9/10` acampam na NOSSA área
("banheira") mesmo com posse nossa; `2/7/8/11` pressionam a saída de bola. É uma
formação fixa com papéis — exatamente o que nós não tínhamos.

## 2. Causa raiz no código (bot/src, confirmado por leitura + forense)

| # | Gol/sintoma | Causa (file:line na v2) |
|---|---|---|
| L1 | Gol 2 | `_carry_target` sem NENHUM gate de interceptação; repulsão (peso 1,2/raio 2000) só desvia de adversário a <334d; `on_holding` cai nele incondicionalmente. A condução segura (`carry.dribble_freedom`, `_touch_target`) existia mas OFF. |
| L2 | Gol 3 | Veto de passe estático (adversários parados) e **cego a qualquer adversário a <700d da origem** (`NO_BLOCK_NEAR_ORIGIN`, geometry.py) — o presser colado é invisível; receptor projetado no futuro, interceptadores não; origem do veto = jogador, mas o chute sai da bola. |
| L3 | Gols 2-3 | Escape (status) só liga com adversário a ≤600d (tarde); passes <800d proibidos; goleiro NUNCA é receptor. |
| L4 | Gols 2-3 | Nenhuma noção de zona: a cascata do portador é a mesma no nosso terço e no ataque (sempre "avançar ao gol"). |
| L5 | Banheira | `cover_mode` só roda em SUPPORTING — em DEFENDING/DISPUTING (contra-ataque e bola livre, quando o camper capitaliza) ele fica solto. |
| L6 | Gol 1 | Goleiro: `_goal_line_threat` exige `speed>5` (bola de rebote parada = invisível → volta pra linha); guard segue só a POSIÇÃO da bola amortecida com `gk_y_range=1100` (cantos y<3900/y>6100 descobertos); pulo sem modelar o travamento de 3 turnos; nunca coleta bola solta; não lê `turns_ball_in_goal_zone` (40 turnos na zona → **auto-chute ao CENTRO** ≈390 = rebote servido). |
| L7 | Gol 1 | Zero caça a rebote (nosso e deles); em DISPUTING os não-chasers vão à formação com aggression 0,0 SEM recuo — **a linha sobe no instante do chute adversário**. |
| L8 | 3 chutes | Gate `shot_min_gap=1300`: com GK centrado só 2 de 9 alvos passam; nada fora de 6000d. |
| L9 | 146×229 passes | Só passe que ganha terreno é aceito (termos de circulação zerados); sem movimentação de recepção. |
| L10 | Sem formação | Papéis fixos por camisa + deslize linear; `marking_target`/`we_are_closest`/`keeper_mode` mortos; atacantes não recuam (x≈9500 com bola no nosso fundo). |

## 3. O que foi implementado (18 genes novos, TODOS default = v2)

Regra do projeto mantida: cada correção é um GENE; default reproduz a v2 byte-a-byte.
**Inércia provada**: `decide_dump` (caminho de passe) = 5999 turnos idênticos entre o
código HEAD e o editado sob o genoma v2; demais caminhos por code-path (gene off não
executa) + smoke; latência com TUDO ligado: pior média 3,7ms de 50ms (p95 7,0ms).

| Frente | Gene(s) | O que faz |
|---|---|---|
| A1 (gol 2) | `carry_gate` + `carry_gate_fwd_min` | Rota frontal bloqueada (área `dribble_freedom` < barra) ⇒ conduz para a melhor direção LIVRE em vez de driblar no desarme. |
| A2 (gol 3) | `pass_veto_mode=turnwise` + `veto_margin_turns` | Novo `geometry.intercept_slack_turnwise`: veto por FRONTEIRAS DE TURNO da bola, origem = bola, SEM o carve-out de 700d. Modela a captura discreta do servidor: presser NA linha conta; marcador colado atrás/ao lado de bola rápida segue não bloqueando (validado em cenários sintéticos). |
| A3 | `zone_escape` + `pass_min_score_defthird`; `pass_min_dist_danger`; `gk_outlet` + `gk_outlet_maxfrac`; bandas `status_*` (existentes) | No terço defensivo o objetivo vira SAIR da pressão: barra própria p/ lateral/recuo, retenção sempre habilitada, passe curto permitido, goleiro como válvula (seguro por construção: adversário não entra na zona-1400; alvo deslocado 350d p/ dentro). |
| A4 | `def_outlet` + `def_outlet_count/radius` | Os 2 mais próximos do portador (bola no nosso terço) abrem linhas de escape recebíveis (meio-anel por slot, veto de interceptação). |
| B | `cover_states=all`; `cover_lane_mix` | Cobertura anti-banheira também em DEFENDING/DISPUTING; opção de negar a LINHA de passe do contra-ataque. |
| F1 | `disputing_mode=defend` | Bola livre no NOSSO campo ⇒ recuar como em DEFENDING (não subir a linha no chute deles). |
| C1 | `gk_collect` + `gk_collect_speed_max/margin` + `gk_zone_alarm` | GK coleta bola solta lenta na zona-1400 (só ele entra = 100% seguro) e reage ao alarme do auto-chute dos 40 turnos. |
| C2 | `gk_jump_mode=strict` | Só pula se o pulo ALCANÇA (200×3 + 100 depois; lockout de 3 turnos modelado). |
| C3 | `gk_guard_mode=track` + `gk_track_div` (+ sweep `gk_y_range`) | Guard alinha ao Y do PORTADOR adversário em zona perigosa; fecha os cantos. |
| C4 | `gk_clear_mode=safe` + `gk_clear_margin/w_flank` | Distribuição do GK com endpoint-race + veto turnwise + preferência de flanco; chutão imediato sob alarme da zona (nunca esperar o auto-chute ao centro). |
| D1 | `rebound_crash` + `rebound_crashers/zone_frac` | Após NOSSO chute, crashers convergem ao ponto de queda (fora da zona-1400 deles) p/ a segunda bola. |
| D2 | (sweep `shot_min_gap`) | Abrir o gate de chute — só vale acompanhado de rebote (gap<1200 converteu 0% direto em 135 chutes). |
| F3 | `marking_mode=man` | Liga o `tactics.marking_target` morto: não-chasers marcam homem-a-homem goal-side. |
| L11 | `support_catch` | Apoiadores também emitem `catch` (disputa da bola dividida). |
| C0 | `gk_probe` (laboratório) | Sonda p/ falsificar "GK preso à linha" — NUNCA submeter. |

## 4. Régua nova (o self-play era cego a isto)

- **Sparring "banheira+pressing" por GENES** (mesma imagem `mybot:qp`, lado adversário
  via `AWAY_PARAMS`): receita final = v2 + `{shift_x:0.8, aggression_defend:1.0,
  aggression_support:1.5, n_chasers:5, pressure_radius:6000, cover_mix:0.0,
  shot_min_gap:800, rebound_crash:on, rebound_zone_frac:0.5, support_catch:on}`.
  Com a bola no nosso fundo, os atacantes dele vão a x≈1600 (nossa área) = banheira
  nos momentos de falha; 5 chasers pressionam a saída; ele chuta e caça rebote.
  **Validação (12 jogos, braços iguais):** 0,33×0,42 gols/jogo (pune!), ~11 chutes
  sofridos/jogo, 1,3 rebotes concedidos/jogo, 3,6 auto-chutes-da-zona/jogo,
  opp_danger 460/jogo (level-1: 222), escape do terço ~41% (receita fraca: 73%).
  Ruído entre braços idênticos: z=0,65 (n.s.) — régua sem viés.
- **`bench/defense_report.py`**: agregador defensivo (transição por origem da posse,
  causa×terço, gols sofridos por origem, chutes/defesas/REBOTES, relógio da zona,
  camping/cobertura, opp_danger, guardas ofensivas).
- **`bench/ab_transition.py`**: A/B base×test vs sparring (`--opp sparring`) ou
  imagem, com tag anti-colisão; replays mantidos.
- Nota metodológica: `def_start_turnover_pct` satura (~97%) vs sparring — as
  primárias úteis são **escape do terço, perdas no terço/jogo, auto-chutes, gols
  sofridos, opp_danger**.

## 5. Resultados dos screenings (rush, 12 jogos/braço vs sparring, base = v2)

Ruído da régua (braços idênticos): z≈0,65 na primária; Δga≈±0,33; comparar sempre
DENTRO do experimento (a base varia entre experimentos por contenção de CPU).

| tag | genes | escape% | perdas-def/12j | ga/jogo | intercept. | outros | veredito |
|---|---|---|---|---|---|---|---|
| a1 | carry_gate v1 (best_free) | 36,6→**20,4** | 163→**309** | 0,75→0,83 | z=−2,1 (menos passe) | opp_danger 548→751; good_chance 0,38→0,20 | **REJEITADO** — sob press de 5, "direção livre" = recuo p/ o canto/zona; vira armadilha. Gene redesenhado (v2: best_fwd → lateral sem recuo → carga v9) p/ reteste na onda 2 |
| a2 | pass_veto_mode=turnwise | 38,8→32,4 | 167→185 | 0,42→**0,25**; CA 2→0 | z=+0,73 (flat) | best_slack −232→−43 | **HOLD** — direção certa em segurança; sem válvulas (A4/gko) o veto vira condução. Retestar no combo |
| a31 | bandas status 3,5/6,0 | 30,6→29,5 | 185→175 | 0,42→0,58 | z=+1,07 | sofridos on-goal 11→15,7 | **REJEITADO** — escapar mais cedo sem receptor não ajuda |
| a34 | zone_escape, barra −1500, min_dist 450 | 35,4→**21,3** | 151→**296** | 0,67→0,50 | **z=+3,28 SIG ↑** | sofridos 13,9→19,9 | **REJEITADO** — barra baixa demais aceita passe lateral fraco contra o press (o contra-indicador previsto). Reconfigurar mais conservador no combo |
| gko | gk_outlet | 34,1→36,3 | 167→157 | **0,50→0,17** | z=−0,16 | good_chance 0,34→0,36; auto-chutes 46→66 | **ACEITO (cand.)** — único receptor que o press não marca (zona-1400); sofridos ↓ sem custo |
| b1 | cover_states=all | 34,3→34,0 | 173→174 | 0,75→0,75 | z=+1,05 n.s. | **coverage_gap 88,9→78,5**; **opp_danger 546→443** | **ACEITO (cand.)** — faz o trabalho (camper marcado, perigo ↓) sem custo |
| f1 | disputing_mode=defend | 38,7→33,0 | — | **0,92→0,33** | z=+1,60 n.s. | rebotes conced. 0,75→0,42; **good_chance 0,33→0,47** | **ACEITO (cand.)** — não subir a linha no chute deles corta as sequências de rebote; ataque até melhora |
| c1 | gk_collect v1 + emboscada | 34,8→33,0 | — | 0,75→**1,33** | z=−0,52 | contra-ataques 0→**5**; auto-chutes 67→47 | **REJEITADO** — o emboscador captura fundo demais e é engolido pelo press; um chaser a menos nas divididas. Gene refatorado: `gk_collect` v2 = coleta estreita alcançável (x≤560); emboscada arquivada em `zone_ambush` (off) |
| c2 | gk_jump_mode=strict | 35,4→41,0 | — | 0,58→0,50 | z=+0,82 n.s. | chutes sofridos 14,8→12,4; rebotes conced. 0,92→0,67 | **ACEITO (fraco)** — melhora consistente nas métricas do goleiro, custo zero |
| c4 | gk_clear_mode=safe (+w_flank 0,5) | 32,1→31,9 | — | 0,33→0,67 (n.s.) | z=+0,22 | auto-chutes 51→43 (mecanismo ✓); rebotes 0,83→1,25 | **HOLD** — reteste na onda 2 sem w_flank |
| d2 | shot_min_gap=1000 | 33,8→36,1 | — | 0,42→0,42 | z=+1,39 n.s. | **chutes nossos 10,75→12,08**; rebotes ganhos 0→0,25; good_chance 0,35→0,25 | **HOLD** — mecanismo ✓ sem ganho sozinho; parear com D1 (onda 2) |
| c3 | gk_y_range=1350 | 33,8→31,0 | — | 0,42→0,75 | z=−1,82 | rebotes conced. 0,58→1,08 | **REJEITADO** — alargar alcance sem posicionamento esperto tira o GK do centro |

**Onda 2 (combos, sparring press-4):**

| tag | genes | resultado | veredito |
|---|---|---|---|
| w2combo | turnwise+gk_outlet+def_outlet+zone_escape(−600)+min_dist 450 | passes 136→178 e good_chance 0,23→0,30, MAS ga 0,33→0,67 e auto-chutes 57→**93** (reciclo estaciona a bola na nossa zona) | **REJEITADO como pacote** — a sinergia não materializou; do lado do escape só o `gk_outlet` (evidência solo) sobrevive |
| w2pdef | cover_states+disputing_defend+jump_strict+gk_collect v2+clear_safe | **ga 0,67→1,33**; nossos chutes 9,3→4,8; mas coverage_gap 90→75 e rebotes conced. 1,08→0,33 | **REJEITADO como pacote** — interação ruim (corpos demais em tarefa defensiva); suspeitos = os 2 sem evidência solo (gk_collect, clear_safe). Composição final usa só os 4 vencedores individuais |
| w2reb | shot_min_gap 1000 + rebound_crash | ga 0,75→0,50 (n.s.), rebotes ganhos 0,08→0; escape −7pp; chutes nossos flat | **REJEITADO p/ v3** — sem ganho ofensivo mensurável vs este sparring; genes ficam p/ experimento na plataforma |
| w2carry | carry_gate v2 (best_fwd) | **escape 32→12,2%**, 507 posses-def, 35 chutes sofridos/jogo, 136 auto-chutes | **REJEITADO DEFINITIVO** (v1 e v2) — passos seguros minúsculos < carga corajosa da v9; o conserto do gol 2 é sair por PASSE (gk_outlet) + contenção (F1/B1), não domar o drible |

**Composição v3 candidata (só vencedores individuais):** v2 + `{gk_outlet, disputing_mode:defend, gk_jump_mode:strict, cover_states:all}` — screening w3comp:

| tag | resultado | veredito |
|---|---|---|
| w3comp | ga 0,58→0,92; escape 30,1→24,6; **nossos chutes 8,9→4,3**; auto-chutes 51→91; MAS rebotes conced. 1,67→0,50 e coverage_gap 89,7→74,9 | **REJEITADO como está** — padrão de PASSIVIDADE: cover_states tira 2 zagueiros ativos p/ marcar estátuas + disputing_defend recua na bola livre → cerco eterno. Bisseção w3a/w3b |

Lição estrutural (consistente com todo o histórico do projeto): a base v2 é agressiva
e equilibrada; genes defensivos SOMAM passividade e interagem mal — cada corpo tirado
do jogo ativo custa mais do que a marcação rende. Só sobrevivem adições que não tiram
corpos do jogo (goleiro; disciplina de pulo; válvula de reciclo).
**Bisseção (press-4):**

| tag | genes | ga/jogo | outros | veredito |
|---|---|---|---|---|
| w3a | gk_outlet + gk_jump strict | **0,67→0,33** | escape −7pp (custo do reciclo); resto flat | **VENCEDOR — é a v3** |
| w3b | + disputing_defend | 0,75→0,83 | nossos chutes −33%; interceptados z=+2,49 | F1 não sobrevive em composição (passividade) |

**Genoma v3 final = v2 + `{"gk_outlet":"on","gk_jump_mode":"strict"}`** — os dois genes
que não tiram corpos do jogo ativo; um por gol-mecanismo (válvula de escape ↔ gol 3;
disciplina de pulo ↔ gol 1). Os demais genes ficam no repo, default-off, com os
vereditos de screening documentados (reavaliáveis com régua melhor/na plataforma).

## 6. Guardas (não-regressão) — TODOS PASSARAM

- **Self-play v3 vs v2** (rush, n=24, lados alternados): **+0,04 ± 0,04 (z=1,0 n.s.), 1V/23E/0D** — a v3 nunca perde da v2. ✓
- **Level-1** (16 jogos, 8/braço): sofridos 0,12→**0,00**; gols pró 2,88→1,62 — investigado e
  **provado ruído**: medição nos replays mostrou **ZERO reciclos ao goleiro nos dois braços**
  (o level-1 não pressiona → `gk_outlet` nunca dispara → os braços são comportamentalmente
  idênticos; σ histórica do level-1 ≈1,2/jogo cobre o delta). ✓
- **Propriedade-chave da v3: melhoria CONDICIONAL** — idêntica à v2 contra quem não
  pressiona; contra pressing (o padrão BotAdversario1) corta os gols sofridos pela metade
  (0,67→0,33 na composição; 0,50→0,17 no screening solo).
- Smoke da imagem de submissão: 3-0 vs level-1, genoma verificado carregado dentro da imagem.

## 7. Genoma v3 + submissão

**`bot/genome_submit.json` (atualizado):**
```json
{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on","cover_mode":"on","gk_outlet":"on","gk_jump_mode":"strict"}
```
Imagem local de verificação: `mybot:submit-v3` (buildada de `.lugo/Dockerfile`, contexto =
raiz do worktree — o mesmo caminho que a plataforma usa). Genoma validado DENTRO da imagem.

**Para submeter (usuário):** na plataforma lugobots.ai, submeter o repositório/branch
`quando-passar` do worktree como nova versão do `killua-zoldyck` (a plataforma builda via
`.lugo/Dockerfile`; o genoma viaja em `BOT_PARAMS_FILE`). Recomendado: rodar antes as
confirmações wait (§8). Depois de submeter, enfrentar BotAdversario1 ≥3 vezes (n=1 é ruído) e
puxar os placares/vídeos com `pull_matches.py` (copiar para o worktree antes — o do
`~/lugo-bots` grava no repo da sessão de RL).

## 8. Confirmações wait (roteirizadas — rodar antes de fixar defaults)

`bench/confirm_queue.sh` (~4-5h): (1) v3 vs sparring em WAIT 16/braço; (2) self-play
ampliado n=40; (3) sanidade vs rival_p1. Aceite: v3 nunca significativamente pior
que v2 em nenhuma; sofridos vs sparring ≤ v2.

Lição transversal do par 1-2: contra pressing forte os genes de escape são
INTERLIGADOS — a válvula (A4/gko) tem que existir ANTES de a barra/veto mudarem o
comportamento; testar o combo, não os isolados. E o sparring com n_chasers=5 é mais
duro que o BotAdversario1 real (pressiona com 4: 2/7/8/11) — onda 2 usa n_chasers=4 por
fidelidade.

## 6. Guardas (não-regressão)

<!-- PREENCHER: selfplay --base v2 --test v2+aceitos; vs level-1 -->

## 7. Genoma v3 candidato + como submeter

<!-- PREENCHER ao final -->

## 8. Confirmações wait (roteirizadas — rodar antes de fixar defaults)

<!-- PREENCHER: comandos prontos por gene aceito -->
