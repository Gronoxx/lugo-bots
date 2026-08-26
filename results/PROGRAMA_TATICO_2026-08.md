# Programa de revisão tática — killua-zoldyck (16/08 → quartas 27-28/08)

> Plano aprovado em 2026-08-16 (barra nova + pacotes P0-P6 + destino do RL).
> Relatório VIVO: preencher vereditos por pacote conforme executa.
> Referências: results/ANALISE_BOTADVERSARIO1_2026-08-15.md (sessão anterior),
> results/RL_MOTHBALL_CONDICOES.md, plano em ~/.claude/plans/.

## A barra nova (em vigor)
- **Trava local por PACOTE** (anti-desastre): self-play vs v3 n=16 rejeita só saldo ≤ −0,5
  com |z|≥2; level-1 rejeita se (gf−ga) cair ≥1,5. Elegibilidade exige a métrica DENSA do
  mecanismo movendo na direção prevista.
- **Promoção pela plataforma**: 1 sortie = 5 jogos/dia; decisão por maximin da margem +
  delta das 10 stats/partida (bench/pull_matches.py; parser validado na fixture partida-01).
- **REGRAS DO TORNEIO (16/08, mudam o alvo)**: atualização PERMITIDA a qualquer momento
  ("main release" escolhível) → loop de promoção pleno. **1ª fase = seeding vs OFICIAIS**
  (L3 V=8/E=3; L2 V=7/E=3; L1 V=5/E=1; desempate: saldo vs L3 → gols vs L3 → saldo vs L2
  → …) ⇒ o alvo primário vira MARGEM vs level-3/2/1 (finalização/criação = pontos de
  seeding). Mata-mata: melhor seed = casa + **vantagem do EMPATE** ⇒ seedar acima do
  BotAdversario1 faz o 0-0 eliminá-lo; gene "proteger empate" (P5) ligável por versão antes de
  cada jogo de chave. Desclassificação por problema técnico ⇒ NUNCA arriscar init fora do
  raio legal em main release (grade fina banida de versão oficial).
- **Composição-padrão da sortie diária (revisada)**: 2× level-3 + 1× level-2 + 1× level-1
  + 1× BotAdversario1 — mede o alvo do seeding (L2/L3 só existem na plataforma) e mantém 1 leitura
  do rival de mata-mata.

## Estado dos pacotes

| Pacote | Estado | Veredito |
|---|---|---|
| P0 infra (scraper stats + pull_matches worktree + setplay_report) | **ENTREGUE** | fixture OK; setplay_report replica a mineração (kickoff 100% ganho/0% chute; 2ª bola 40%, déficit +1124d no corpus guardl1) |
| P1 finalização (consertos + finish_mode/shot_gate=slack vs GK externo) | **SCREENING FECHADO** | consertos aplicados. Vs level-1 (16/braço): **finish_mode ELEGÍVEL** — chutes 6,9→9,7/jogo (+41%), rebotes ganhos 0,06→0,50, good_chance 0,40→0,48, gols 2,06→2,38, 0 sofridos (a régua self-play julgava contra nosso próprio GK — errada, como previsto). shot_gate=slack sozinho: 93% dos chutes com folga>0 mas −24% volume, gols flat → não promove. **Combo REJEITADO** (2,62→1,56: o slack estrangula o volume do finish). **PKT-1 = finish_mode**; travas locais rodando |
| P2 kickoff (sonda grade fina + init_variant kick9 + playbook setplays.py) | **SCREENING FECHADO — ELEGÍVEL (PKT-2)** | Sondas: d=1051 REJEITADO (W.O.!); d=1451 legal mas ganho ≤1t → fine banida de oficial. A/B kick9+playbook: vs sparring, chegada ao terço pós-kickoff 7→25%, recuo −2390→−175d, ga60 pós-reset=0; vs level-1, **gols 2,12→2,62 e 0 sofridos**. Sortie S3 |
| P3 ofensivo (second_ball + attack_width + far_post) | **SCREENING FECHADO** | **second_ball ELEGÍVEL (o melhor solo até agora)**: vs level-1 gols 1,81→**2,56**, chutes 6,75→9,25, rebotes ganhos 0→0,31, 0 sofridos. attack_width+far_post: neutro → arquivado (coerente com o histórico) |
| P4 defesa/transição (def_min_depth + counterpress) | **SCREENING FECHADO — AMBOS REJEITADOS** | counterpress: sofridos 0,50→0,81 (o chaser extra desguarnece a forma); def_min_depth 1700: sofridos 0,56→0,81 (os corpos "no anel" bloqueavam chutes). 3ª confirmação: a defesa da base é ótimo local — colheita do programa é toda OFENSIVA |
| P5 placar/tempo (gs_shot_scale, gs_sb_boost, gs_retain_late, gs_draw_ok) | **CÓDIGO ENTREGUE** | consumidores do _game_aggr; `gs_draw_ok` = modo "proteger empate" ligável POR VERSÃO nos jogos de chave (a regra dá o empate ao melhor seed). Inércia OK. Validação local fraca por natureza — usar na plataforma/mata-mata |
| P5 placar/tempo (esboço) | opcional | |
| P6 modelo-de-oponente offline (esboço) | opcional | |

## Compósitos (16/08, janela autônoma)

| composto | vs level-1 (16/braço) | travas | veredito |
|---|---|---|---|
| comp_a = v3+finish+second_ball | **2,44→3,06** (+0,62); chutes 8,25→11,44; ga 0,12→0,06 | rodando | **candidato à main release do SEEDING** |
| comp_b = comp_a+kickoff | 2,19→2,94 (+0,75) | selfplay 0V/14E/2D (−0,12 n.s.); sparring ga 0,38→0,88 (n=8, limite do ruído) | passa a barra, mas com sinais; **kickoff = carta do MATA-MATA** (vs oficiais já ganhamos 100% dos kickoffs; o pacote vale contra iguais) |

Composição ofensiva EMPILHA (sem a interação negativa das defensivas). Estratégia de
versões: main release do seeding = comp_a (margem vs levels); versão de chave = comp_a
+ kickoff (+ gs_draw_ok quando o empate nos bastar).

**Estágio 3 do comp_a/v4 (16/08): travas PASSARAM (selfplay 16E/0D; sparring ga
1,25→0,38) · WAIT confirmou (+0,63 gf, saldo +1,13→+1,38; vigiar ga 0,12→0,50 n=8) ·
sweeps: finish_sure_slack=200 piora (manter 0), sb_dist=3200 promissor (+0,83; duelo
direto na noite 2) · painel rivais: 4V/0D (10-37 × 0).**

**Noite 2 (vereditos):** sonda `sym` LEGAL (22/22, #10 a d=1500) · `gk_guard_mode=track`
REJEITADO vs sparring (ga 0,38→0,50; sem sinal) · `camper_shadow` REJEITADO (ga
0,56→0,88 — 4ª confirmação da lei da passividade) · `sym`+kickoff: vantagem bruta da
corrida NÃO materializa vs mesma classe (captura disputada = moeda; support_catch do
sparring pesa), mas o playbook segue convertendo (terço 0→38%; jogo geral ga
0,81→0,50); sym = conserto cosmético · `sb_dist`: **2600 confirmado** no duelo direto
(2,80×2,38; o +0,83 do sweep era ruído entre experimentos). Defensivos reprovados vão
p/ a bancada-patrick na plataforma. **v4 = versão de seeding final.** Noite 3: travas
da v4k (mata-mata: v4+shot_gate=slack+gs_retain_late+gs_draw_ok — perfil inanição
anti-muralha/anti-GK-forte) + top-up wait da v4 (firmar ga n=16).

**Plataforma 16/08 (jogos 4-5 da quota):** BotAdversario9 (muralha) **3-7 com v4** — recorde
ofensivo vs top (34 chutes, 3 gols) mas 34 doações (GK deles 91,2%; nosso 78,1%); o 0-0
BotAdversario6×BotAdversario9 revelou o blueprint INANIÇÃO (posse líq. 68%, 11 chutes seletivos →
muralha só gerou 6). Breakaway 3-vs-GK perdido = gate threshold cego ao tempo (chuta de
5000+ onde t_bola≈18 deixa o GK cobrir ±2360; slack-gate aproxima antes de soltar).
Level-3 com v4: aguardando placar do usuário.

## Sorties de plataforma (5 jogos/dia; mix: 2×L3, 1×L2, 1×L1, 1×BotAdversario1)

| # | Data | Candidato | Jogos (adv → placar) | Maximin | Decisão |
|---|---|---|---|---|---|
| S1 | 16/08 (2 jogos) | v3 | BotAdversario1 → **0-3**; level-3 → (pendente) | — | v3 fechou os vazamentos da v2 (roubadas deles 21→7, acerto 96,5%, chutes deles 10→7, nossos 3→6) mas anatomia NOVA de gol: cerco → chute no canto oposto ao GK (guard rastreia a bola, não a linha) + conversão nossa 0/6. Alvos: gk_track solo + v4 (conversão). Vídeo/forense: `videos/storyboard-v3/` |
| S2 | | **v4-candidato = v3 + finish_mode** (travas locais PASSARAM: selfplay 1V/15E/0D; sparring sofridos 0,75→0,38) | | | |

**Como submeter a v4 quando for a vez (S2):**
```bash
cd ~/lugo-quando-passar
cp bot/genome_v4_candidate.json bot/genome_submit.json
docker build -f .lugo/Dockerfile -t repo.lugobots.ai/killua-zoldyck:v4 .
docker push repo.lugobots.ai/killua-zoldyck:v4   # e marcar como main release
```
(Para voltar à v3: re-marcar a :v3 como main release na plataforma — as versões ficam lá.)

> Backlog vivo de melhorias não-realizadas: **results/BACKLOG_MELHORIAS.md** (A: ideias
> com desenho; B: genes off sem veredito; C: validações pendentes de canal).

## Dossiê de versões (fechado 16/08 ~23:40, janela autônoma)

| versão | genoma | papel | evidência |
|---|---|---|---|
| **v4 (MAIN DO TORNEIO — decisão 17/08)** | v3 + finish_mode + second_ball (`bot/genome_v4_candidate.json`) | **Seeding oficial** | rush 2,44→3,06; **wait n=16: 2,31×0,25**; painel rivais 4V/0D; 1-0 vs level-3; 0-0(+OT) vs BotAdversario1 |
| v5 (**REPROVADA no exame — LAB**) | v4 + adaptive 12/0 + ot_relief (`:v5` no registry) | experimental | **PERDEU 0-1 do level-3 (1ª derrota histórica p/ level)**: BUG — o contador `_our_shots` contava passes longos como chutes (337 passes → "12 chutes" no 1º min → slack travado → **3 chutes no jogo**, 65% de posse estéril). Contador CORRIGIDO (só trajetórias que cruzam a boca); v5b só volta via desafio, nunca direto à main. Insight: controle estéril (3 chutes=0-1) e volume cego (44=1-0) empatam em mediocridade vs GK-elite — fronteira real segue sendo deslocar o goleiro |
| **v4k** | v4 + shot_gate=slack + gs_retain_late + gs_draw_ok (`bot/genome_v4k_knockout.json`) | **Mata-mata** vs muralha/GK-forte (inanição + empate-serve) | selfplay vs v4 −0,12 (sem desastre); vs sparring: chance 0,44→**0,83**, slack>0 77%, gf 0→0,62 |
| v3 | (tag :v3 na plataforma) | rollback | — |
| kickoff pack (kick9+playbook) + sym | genes prontos | carta vs iguais (converte reinícios ganhos: terço 0→38%) | não entra na main até evidência de plataforma |
| **v6 (17/08 — TRAVAS OK; EXAME 1/2 PASSOU: 3-0 no level-3)** | v4 + shot_gate=**hybrid** + **gk_reach_speed=100** + ot_relief 260 (`bot/genome_v6.json`; `:v6` push verificado por digest `eaab5b5b16d5...`) | **arma anti-GK-elite** (L3/BotAdversario1/mata-mata) | **EXAME 1 (mid partida-04): 3-0, conversão 42,9% (3/7) vs 2,3% (1/44) da v4; doação ao GK deles 43→4; roubadas 59×0; nosso GK 6/6** — falta o exame 2 (BotAdversario1). hybrid = threshold perto (d≤3200) + slack-100 longe (100 = cap físico do GK; retro: nega 53/74 longes estéreis). **C1 selfplay n=32: 0V/32E/0D, saldo 0,00 (sem desastre). C2 sparring: good_chance 0,384→0,866, conv. 2,4→3,1%, doação de longe 59%→23%, opp_danger −19% (ga 0,31→0,56 n.s., ~1σ). C3 wait vs L1: 1,25×0,19, 10V/6E/0D, conversão mantida 30%** — MAS gf cai de 2,38 (−1,13, z≈3): os 14 gols-de-longe da v4 vs GK fraco somem. **⇒ v6 NÃO é versão única de seeding: 6/16 empates vs L1 = 3,5 pts esperados vs ~5,0 da v4 (E vale 1, V vale 5).** Papel: main vs L2/L3/BotAdversario1; v4 segue main vs L1 |
| ~~cb_stagger~~ (**REJEITADO S3**, 17/08) | gene fica no repo, off | — | vs sparring: ga 0,42→**1,00**, sofridos on-goal 16,5/jogo, opp_danger +90. **5ª lei da passividade**, forma sutil: o não-zagueiro substituto chega DEPOIS do CB trocado → pressão efetiva mais lenta → mais chute contra. O anti-gol-de-ouro tem que vir de outro mecanismo (ex.: gs_retain_late/gs_draw_ok já protegem o 0-0 no normal; na OT o problema é ofensivo — chutar primeiro via ot_relief) |
| **v7 (EM CONSTRUÇÃO, 17/08 — genes do METAMORFO implementados, screening RODANDO)** | v6 + genes default-off dos commits c0–c9: `init_variant=race` (kickoff é CORRIDA; race d=1500 ganha de qualquer init ≥1581 — posse em TODO reinício), `kickoff_blitz`, `kickoff_race` (arco na corrida perdida), `swarm_rebound` (arco de rebote pré+pós chute), `ot_press`, `outlet_press_detect`, `counter_press_window` (revisita c/ morte pré-declarada), `kickoff_shield` (idem), `quina_entry` | **fábrica de situações** (fin 7→12+; saldo vs L3 = desempate) + pacote-BotAdversario1 | Commits pequenos, tríade por commit (edge_cases 140 ×combos; decide_dump byte-igual com genes off; latency 1,6ms/50ms com TUDO on). Fix estrutural c0: `setplays.active()` anulava `_reset_turn` no aborto. opd verificado no dump: 31/31 divergências na semântica exata. Sonda v7probe vs L1: registro race 22/22 OK, 1×0. Instrumentação nova no A/B (kickoff/rebote/roubo→fin). Screening S1–S5 em `bench/v7_queue.sh` (~4h) → compor v7-candidata com os aprovados → travas C1/C2/C3 → exame |

**Resultado da quota de 17/08:** v4 × BotAdversario1 **0-0 (+0-1 gol de ouro na OT)**; v4 × level-3 **1-0** (44 chutes/2,3% conversão); v5 × level-3 **0-1** (bug do contador → REPROVADA; usuário reverteu main p/ v4 — nasce a REGRA DO EXAME); v6 × level-3 **3-0** (EXAME 1 — autópsia abaixo).

**Próxima quota — EXAME DA v6 (regra nova, nada entra na main sem passar):**
1. Validação local termina primeiro (`bench/v6_queue.sh`: screenings hybrid/cb_stagger + compósito selfplay/sparring/wait). Se alguma trava reprovar, o exame é adiado e o gene culpado bissectado.
2. Subir `:v6` e marcar main TEMPORÁRIA:
```bash
cd ~/lugo-quando-passar
cp bot/genome_v6.json bot/genome_submit.json
docker build -f .lugo/Dockerfile -t repo.lugobots.ai/killua-zoldyck:v6 .
docker push repo.lugobots.ai/killua-zoldyck:v6   # marcar main na plataforma
```
3. **1× level-3** (meta: vitória com conversão >2,3% e MENOS de ~20 chutes doados) e **1× BotAdversario1** (meta: ≥0-0 no tempo normal; na OT estreia o ot_relief).
4. **REVERTER main p/ v4** (re-marcar :v4) → só promover v6 se os DOIS exames ≥ v4. Depois `cp bot/genome_v4_candidate.json bot/genome_submit.json` para o repo refletir a main.
**Bancada-patrick** (mesma conta, cota compartilhada): `docker push repo.lugobots.ai/patrick-estrela:v2bench` (v3+gk_track pronto) → 1× BotAdversario1 = evidência do antídoto ao canto-longe.

**PARTIDA OFICIAL vs LEVEL-1 (18/08, mid `partida-25`): 1×0 — PROBLEMA DE SALDO.** Stats:
**218 passes certos (99,1%) para 2 finalizações**, `campo_adv` 27,6% (posse quase toda no NOSSO
campo), 137 bolas roubadas pelo L1 (que persegue em bando; nosso portador conduz sozinho).
**Régua do mesmo dia: BotAdversario2 10×0, BotAdversario11 5×0, BotAdversario5 3×0, nós 1×0** — e o desempate do
seeding é SALDO, com só 8 vagas. Temos o melhor acerto de passe da competição e o pior volume:
jogamos para não errar. **Causa no código:** no score de `_best_pass` os termos de segurança
(clearance/pressão) superam o AVANÇO → o bot prefere o lateral seguro, 218×. Genes novos
(inertes por default, decide_dump byte-igual): **`pass_w_advance`** (peso do avanço) e
**`shot_rebound_relief`** (o gate afrouxa por corpo no arco de rebote — economia do BotAdversario2).

**PACOTE DE GOLEADA (G1) — o lever que faltava era SUBIR A LINHA.** vs level-1 (16 jogos,
rush): G1 = `pass_w_advance 2,5` + `aggression_support 0,6→1,0` + `shift_x 0,30→0,45` +
`shot_gate threshold` + `shot_min_gap 1000` + swarm + `srr 300` → **gf 1,56→2,88 (+85%),
finalizações 5,06→9,06 (+79%), ga 0,00→0,00, 10V/6E → 15V/1E**. G2 (mesmo ataque SEM mexer na
formação): gf 2,12→2,62 (+24%), fin 6,19→8,25. **A formação alta vale ~60 pontos percentuais
de gol.** Custo defensivo medido nas cenas: v8 (defesa v7.4 + ataque G1) = 128/130, e a perda
está TODA na `adv9_v4_169` (caos de área do BotAdversario9 — bot FORA do torneio oficial); as cenas
de BotAdversario1 e level-3 seguem 10/10. Sem as mudanças de formação: 130/130 mas só +24% de gol.

**BISSEÇÃO DA 6ª LEI + v7.3/v7.4 (18/08).** Blocos isolados vs level-1 (32 jogos rush cada,
base=v6): **kickoff-pack** (race+play+blitz+ring) **✓ +29% finalizações** (4,31→5,56), gf
1,81→2,00; **gk-pack+ot** (gk_clear=safe+gk_collect+ot_press) **✓** gf 2,31→2,81; **BotAdversario1-pack**
(cpw+shield+opd) **✓ +34% finalizações**, gf 1,62→2,50; **swarm+quina ✗** (−24% fin — quina
descartada, swarm solo era +25%); **dd+holdmark ✗** (−26% fin, passes +40% = posse estéril:
a assinatura da inanição). v7.3 (dd_maxfrac=0,33) melhorou mas não curou: C1 ✓ (32E, sem
desastre), C2 gf 0,12→0,19 mas ga 0,50→0,75 e fin −42%; C3 gf 2,12→1,81, fin 5,31→4,44,
passes +29% (estéril). **Diagnóstico final: o dreno é o RECUO em meio-campo, não o pacote-cenas
em si.** Busca do pacote-cenas mínimo (4 variantes × 130 runs): só-positivos 126/130, +holdmark
126, +dd(0,33) 129, ambos **130**; e o recuo mantém 130/130 com gatilho apertado a 0,22/0,25/0,28
— ou seja, **basta recuar nos 22% mais fundos** (ameaça real; não é passividade).
**v7.4-candidata = v6 + kickoff-pack + swarm + BotAdversario1-pack + gk-pack + ot + dd(0,22) + holdmark**
(`bot/genome_v74_candidate.json`, 26 genes): cenas **130/130**.
**TRAVAS DA v7.4 — PASSARAM pelos critérios pré-declarados.** C3 wait-L1: **empate técnico
exato** (gf 1,88=1,88, ga 0,12=0,12, finalizações 4,19=4,19; opp_danger 556→503) — o dreno da
v7.3 SUMIU. C2 sparring: gf 0,12=0,12 e **ga 0,62→0,50** (−19%), interceptados z=−1,75; custo =
finalizações 7,62→4,38 contra pressing pesado. **A descoberta que explica o C3 neutro: contra o
level-1 os DOIS braços já ganhavam 100% dos kickoffs (sem margem); contra bot da NOSSA CLASSE
(sparring) a corrida foi 43%→100% (16 perdidas→0).** O pacote foi desenhado para L3/BotAdversario1/
BotAdversario2, não para o L1 — as travas locais são guarda-corpo ("não pode piorar"), e o ganho só
mede na plataforma ou vs muralha local. Em curso: v7.4 × BotAdversario2clone (muralha = proxy de L3) e
C1 self-play.

**TRAVAS DA v7.2-COMPLETA (18/08): C1 OK (31E/1D, sem desastre) mas C2/C3 REPROVARAM —
6ª LEI DA PASSIVIDADE, forma nova: A COMPOSIÇÃO.** Cada gene passou solo; os 26 juntos
drenaram o corpo ofensivo: C2 sparring gf 0,38→0,06 (chutes 7,06→3,25, opp_danger 637→835,
contra-ataques 0→5); C3 wait-L1 gf 1,81→0,94 (fin 4,88→2,38, posse estéril 184→247 passes;
ga 0,12→0,06 perfeito — inanição clássica). Kickoff-pack segue funcionando (ko 100%, rebote
aproveitado 78%). **Bisseção em curso** (3 blocos vs L1 rush): B1=ofensivos (race/play/blitz/
ring/swarm/quina/ot/gksafe), B2=dd+holdmark (núcleo-cenas), B3=cpw+shield+opd. Tensão a
resolver: o pacote-cenas (130/130 nos 13 gols) usa exatamente dd+holdmark — se forem os drenos,
calibrar versão situacional (recuo só no terço, não no campo) em vez de descartar.

**SCREENING v7 — CONSOLIDAÇÃO (18/08 madrugada, 32 jogos rush/bloco):**
S2 kickoff-pack (race+play+blitz+ring) **APROVADO no mecanismo**: corrida do reinício 50%→
**100%** (ko_lost 14→0, 1º toque 12t), opp_danger 698→618, sofridos 8→7 (vs sparring o kickoff
ganho ainda não vira gol — o valor real é vs L3/defesas que recuam). S3 opd+cpw **APROVADO**:
interceptados/posse z=−1,54 (direção certa), fin/jogo 7,75→8,69, gols pró intactos. S4 shield
**APROVADO com folga**: sofridos 12→6 (−50%!) sem custo ofensivo (gf 0,19=0,19; chutes 6,69→
7,56). S5 quina aprovado-fraco (+0,31 gf vs L1, ga igual). S1 swarm vs sparring: mecanismo não
moveu (banheira pune cerco); S1b vs L1 2× inválido por infra (rede docker; depois tag com
MAIÚSCULA — compose exige project lowercase; lição de fila) → S1c re-rodando. **v7.2-candidata
composta** (`bot/genome_v72_candidate.json` = v6 + 13 genes): cenas 130/130 ✓, edge ✓, latency
2,6ms ✓; travas C1/C2/C3 = `bench/v72_queue.sh`.

**CENAS SIMULADAS (17/08 noite — ESTEIRA NOVA, proposta do usuário): 13 gols sofridos
reconstruídos dos vídeos e re-simulados com o my_bot real.** Pipeline: `sim/scene_extract.py`
(visão: campo calibrado ~14d/px, tracking conjunto 22, bola por DP; valida: o passe fatal do
0×1 passou a d=315 do presser — perdido por 15d no real) + `sim/scene_runner.py` (ghosts com
trajetória real + bola-fantasma; nossos 11 VIVOS; captura de passe em trânsito = contrafactual)
+ 2 fixes de fidelidade no fastsim expostos pelas cenas (glue atravessando a linha = auto-gol
falso; GK re-pegando a própria saída em loop). **RESULTADO: v6 baseline 123/130; PACOTE-CENAS
= `disputing_mode=defend` + `press_hold_mark` + `gk_clear_mode=safe` + `gk_collect` (+ veto
C4b no clearance) → 130/130 (13/13 na réplica exata + 10 seeds de jitter).** Reprovados nas
cenas: `panic_clear` (chutão alimenta a muralha), `press_shadow` (neutro aqui; segue candidato
p/ A/B). Genes novos c10-c11: press_shadow, press_hold_mark, panic_clear (off). Falta: travas
C1/C2/C3 do pacote-cenas composto com a v7 (lei da passividade: dd+holdmark são defensivos).

**EXAME 2 — AUTÓPSIA (17/08 ~22h, exame 2): REPROVOU — v6 0×1 BotAdversario1 no TEMPO NORMAL** (344s, sem OT; pior que o baseline v4 = 0-0+gol de ouro). O gol
saiu a **19s do fim**: condução do BotAdversario1 no meio sob pressão de 3-4 nossos → passe nas costas
dos pressers (modo-de-perder nº2) → penetração → ~4s de caos na nossa pequena área → gol.
Ataque: **1 finalização nossa em 344s** (inanição vs bloco de 9-10; hybrid não solta de longe).
Roubadas 29×16 e acerto 97,9% (a saída não vazou em volume). **Decisão: reverter main p/ `:v4`
(v6 não promovida); v6 = arma anti-L3 se a main puder trocar entre desafios (pendência
suporte).** Lições: (a) a 19s do fim, gs_retain_late+gs_draw_ok (OFF na v6) protegeriam o 0-0;
(b) plano-OT (ot_press+ot_relief) segue válido — falta CHEGAR à OT; (c) nova esteira anti-BotAdversario1
= CENAS SIMULADAS (reconstruir os gols sofridos e validar variantes localmente antes da quota).

**EXAME 1 — AUTÓPSIA (17/08 17:58 local, exame 1): PASSOU COM FOLGA.**
v6 × level-3 **3-0** no tempo normal (vídeo 361s, sem OT). Todas as 3 metas batidas:

| métrica | v4×L3 (partida-07) | v6×L3 (partida-04) |
|---|---|---|
| placar | 1-0 | **3-0** |
| finalizações nossas / conversão | 44 / 2,3% | **7 / 42,9%** |
| doação ao GK deles (defesas) | 43 (97,7%) | **4 (57,1%)** |
| finalizações deles / nosso GK | 3 / 100% | 6 / **100%** |
| posse líquida | 22,9% | **35,8%** |
| passes bons/ruins | 137/9 (93,8%) | **226/7 (97,0%)** |
| roubadas | 32×2 | **59×0** |

Leitura: o hybrid entregou exatamente o mecanismo desenhado — em vez de 44 chutes doados ao
GK-elite, segurou/aproximou e finalizou 7× com 3 gols; e NÃO caiu na inanição da v5 (3 chutes,
0-1). As duas patologias (volume cego e controle estéril) evitadas no mesmo jogo. Custo: doamos
6 chutes ao L3 (baseline 3), todos defendidos.
**Anatomia dos gols (forense de vídeo, frames em `scratchpad`):** os TRÊS saíram de finalização
curta na pequena área, zero bombas de longe — g1 (t≈32s vídeo, 04:35 do 1º tempo, a ~23s de
jogo!): passe diagonal p/ o espaço, #11 domina na linha de fundo direita e entra com #10 de
carona, chute à queima-roupa com GK deslocado; g2 (t≈242s, 01:28 do 2º): condução do #11 até a
quina alta da área, entrada diagonal, #10 finaliza de perto; g3 (t≈280s, 00:56): chute curto
defendido + **rebote no #10** (second_ball pagando). Mecanismo "deslocar o goleiro" confirmado
no servidor real — não foi acaso.
**Calibração da régua (aviso do usuário, 17/08): 3-0 NÃO é dominância.** BotAdversario2 fez **12×2**
no L3 e **5×0 no BotAdversario1**; BotAdversario1 antigo fazia 6×0/10×0 no L3. Como o desempate do seeding é
**SALDO vs L3**, margem importa: v6 resolveu conversão (42,9%) mas com 7 finalizações não se
faz 12 — o gargalo agora é VOLUME×conversão (→ fase metamorfo, `results/METAMORFO_2026-08.md`). **Decisão (árvore do handoff): seguir ao EXAME 2
(BotAdversario1)** — meta ≥0-0 no normal; na OT estreia o ot_relief (chutar primeiro). Main permanece
`:v6` até o fim do exame 2; SÓ ENTÃO reverter p/ `:v4` (repo local já está = v4). Quota: exame 1
foi o 5º jogo killua na janela de 24h (patrick parado desde 16/08 19:21 UTC); se a janela for
rolante, próximo slot ~19:47–20:09 local de 17/08; se for por dia UTC, há 2 slots hoje.

## Scouting de adversários (mata-mata)

| bot | ranking | perfil | counter recomendado |
|---|---|---|---|
| BotAdversario1 | topo | pressing 4 + campers 9/10 + trio fixo; conversão letal; EVOLUI entre jogos | **v4: 0-0 no tempo normal, 0-1 por GOL DE OURO na prorrogação** (−1:41, #8 de média distância no canto longe — 4º gol dessa anatomia em 2 jogos). Trajetória 0-3→0-3→0-0(+OT). **BotAdversario1 NOVO (17/08): anulado 1×1 pelo bloco do BotAdversario12 (2 finalizações em 10 min, SEM gol de ouro na OT inteira); só marca na janela ~15s pós-kickoff; perdeu 5×0 do BotAdversario2. Previsão exame 2: 0×0/1×1 com OT provável (METAMORFO_EIXO_B).** **REGRA NOVA: desafios têm prorrogação/gol de ouro — CONFIRMAR se jogos oficiais de chave também** (muda o valor do gs_draw_ok). Prioridade do matchup: patrick-bench com gk_track (o antídoto do canto-longe) vs BotAdversario1 real |
| BotAdversario9 (BotAdversario3) | 2º | **FORA DO TORNEIO OFICIAL (confirmado 17/08)** — segue disponível como SPARRING de desafio. MURALHA vertical; vive de devoluções | vira LABORATÓRIO (testar inanição/v4k e wall-breakers por fora); sem urgência de torneio |
| **BotAdversario2** | forte (novo no radar 17/08) | **GOLEADOR: 12×2 vs L3 (`partida-08`), 5×0 vs BotAdversario1 (`partida-12`), 10×0 L1, 7×0 L2**; evoluiu entre 15/08 (0×0 BotAdversario1) e 17/08 (5×0); variância vs L3 (3×1 hoje 14:32) | **FASE METAMORFO** (results/METAMORFO_2026-08.md): destrinchar o volume×conversão dele e o desmonte do BotAdversario1; absorver via genes pela esteira normal |
| BotAdversario6 | 4º | POSSE (líq. 68–78%; 500 passes; 4×0 no L3 com só 9 fin) — posse SEM cirurgiões rápidos = volume baixo (EIXO_A) | kickoff pack + second_ball; menos ameaçador do que o ranking sugere |
| BotAdversario4 | forte | TRANSIÇÃO EM BLOCO: 10×0 no L3 ×2 (27 fin/37%, 42 roubadas); kickoff-press idêntico ao BotAdversario1 antigo (gol aos 8s) | `kickoff_shield` + não subir a linha sem bola |
| BotAdversario10 | forte | CIRURGIA DE QUINA: 10×0 no L3 (16 fin/**62%**, posse líq. 62%, coluna-de-5 fixa atrás, paciência de shot clock) | fechar quinas/linha de fundo; `counter_launch` pune a subida dos 4 dele |
| BotAdversario13 | médio-forte | ISCA+BOTE: 10×0/5×0 no L3 com acerto de passe 28% (lançamento nas costas da linha alta; 5 fixos) | NÃO subir a linha contra ele; nosso wait já nega a isca |
| BotAdversario11 | ? (stats-only) | transição-direta: 6×0 no L3 (15 fin/40%, posse líq. 15,7%) — perfil BotAdversario13-lite | idem BotAdversario13; forense pendente |
| BotAdversario14 | fraco-médio | ANTI-PADRÃO: 3×0 no L3 com 55 fin/5,5% (52 defesas do GK) — volume-cego, 1–2 corpos no ataque | vitória esperada; punir os 17 chutes que ele doa |
| BotAdversario12 | fraco no ataque | BUNKER: 1×1 com o BotAdversario1 NOVO (bloco de ~10 + chutão; BotAdversario1: 2 fin em 10 min) | referência tática (negar transição ≫ qualidade geral), não ameaça direta |

## Ações do usuário (D0)
1. Confirmar a POLÍTICA DE ATUALIZAÇÃO do bot inscrito durante o torneio (regras/suporte).
2. Verificar QUAL versão está inscrita (digest da página do bot; comparar com
   `mybot:submit-v3`); se v2 e atualização possível → subir a v3.
3. Gastar a quota do dia: 5 jogos (3× BotAdversario1, 1× BotAdversario4, 1× level-3); depois
   `python3 bench/pull_matches.py` (worktree) para puxar placares+stats+vídeos.
