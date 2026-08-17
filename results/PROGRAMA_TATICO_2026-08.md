# Programa de revisão tática — killua-zoldyck (16/08 → quartas 27-28/08)

> Plano aprovado em 2026-08-16 (barra nova + pacotes P0-P6 + destino do RL).
> Relatório VIVO: preencher vereditos por pacote conforme executa.
> Referências: results/ANALISE_BotAdversario1_2026-08-15.md (sessão anterior),
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

**Plano da quota de 17/08 (rev. pós-0-0):**
1. BotAdversario9 × **v4k** (pendente — teste do perfil-inanição)
2. level-2 × **v5** (1º dado de L2 da história + estreia da v5)
3. level-3 × **v5** (o exame do gate adaptativo contra o GK de 97,7%; baseline: 1-0/44 chutes da v4)
4. BotAdversario1 × **v5** (repete o 0-0? vs eles a v5 ≡ v4 — nunca chegamos a 12 chutes)
5. BotAdversario6 × v5 (scouting posse)
Fluxo: subir `:v5` (`docker push repo.lugobots.ai/killua-zoldyck:v5`) e marcar main; para o jogo 1, main temporária = v4k e VOLTAR para v5 depois.
**Bancada-patrick**: `docker push repo.lugobots.ai/patrick-estrela:v2bench` (imagem local pronta: v3+gk_track) → marcar main do patrick → 2-3× BotAdversario1 com a quota DELE = evidência real dos genes defensivos.

## Scouting de adversários (mata-mata)

| bot | ranking | perfil | counter recomendado |
|---|---|---|---|
| BotAdversario1 | topo | pressing 4 + campers 9/10 + trio fixo; conversão letal; EVOLUI entre jogos | **v4: 0-0 no tempo normal, 0-1 por GOL DE OURO na prorrogação** (−1:41, #8 de média distância no canto longe — 4º gol dessa anatomia em 2 jogos). Trajetória 0-3→0-3→0-0(+OT). **REGRA NOVA: desafios têm prorrogação/gol de ouro — CONFIRMAR se jogos oficiais de chave também** (muda o valor do gs_draw_ok). Prioridade do matchup: patrick-bench com gk_track (o antídoto do canto-longe) vs BotAdversario1 real |
| BotAdversario9 (BotAdversario3) | 2º | **FORA DO TORNEIO OFICIAL (confirmado 17/08)** — segue disponível como SPARRING de desafio. MURALHA vertical; vive de devoluções | vira LABORATÓRIO (testar inanição/v4k e wall-breakers por fora); sem urgência de torneio |
| BotAdversario6 | 4º | POSSE (líq. 68% contra a muralha; 93% passe; 25 roubos) | kickoff pack (ganhar os reinícios) + second_ball; a definir com dados |

## Ações do usuário (D0)
1. Confirmar a POLÍTICA DE ATUALIZAÇÃO do bot inscrito durante o torneio (regras/suporte).
2. Verificar QUAL versão está inscrita (digest da página do bot; comparar com
   `mybot:submit-v3`); se v2 e atualização possível → subir a v3.
3. Gastar a quota do dia: 5 jogos (3× BotAdversario1, 1× BotAdversario4, 1× level-3); depois
   `python3 bench/pull_matches.py` (worktree) para puxar placares+stats+vídeos.
