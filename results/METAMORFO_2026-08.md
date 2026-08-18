# FASE DO METAMORFO — por que os fortes são fortes (17/08/2026)

Missão: destrinchar os adversários de elite (BotAdversario2, BotAdversario1), extrair o mecanismo causal
da força deles e propor absorção via genes. Contexto: desempate do seeding = **SALDO vs L3**;
nossa v6 fez 3×0 (7 finalizações, 42,9%), teto atual de margem. Forense: stats do site +
vídeo frame a frame (pipeline de crops do placar + mosaicos; frames no scratchpad da sessão).

**Documento-mestre.** Aprofundamentos: `METAMORFO_EIXO_A.md` (gerador de gols vs L3:
BotAdversario4, BotAdversario10, BotAdversario13, BotAdversario2-pressing, anti-padrão BotAdversario14) e `METAMORFO_EIXO_B.md`
(matchup BotAdversario1: BotAdversario12 1×1 com o BotAdversario1 NOVO, defesa do BotAdversario1, blueprint anti-BotAdversario1).
Consolidação de tudo nas seções 7–9.

## 0. Descoberta de regra: MERCY POR SALDO ~10

O 10×0 do BotAdversario1 (mid `partida-26`) **terminou com ~1:50 ainda no relógio** (vídeo de 282s,
placar final aos 01:5x); os DOIS 10×0 dele em julho terminam exatamente em +10, e o 12×2 do
BotAdversario2 também é saldo +10 (esse foi até o fim do tempo). Tudo indica **encerramento por
diferença de 10** (ou teto prático equivalente). Implicação: o teto de saldo por jogo vs L3
é ~+10; a régua de elite é 6–10 de saldo. Nosso 3×0 = 30–50% do teto.

## 1. Tabela comparativa (todos vs level-3, + o matchup BotAdversario1)

| jogo (mid) | placar | fin | conv | GK adv defesas | posse líq | campo_adv | acerto passe | passe adv | roubadas |
|---|---|---|---|---|---|---|---|---|---|
| BotAdversario2 12×2 (`partida-08`) | **12×2** | 51×2 | 23,5% | 39 (76,5%) | 47,9×12,6 | **83,4%** | 98,0% | 78,9% | 29×1 |
| BotAdversario2 4×0 (`partida-09`) | 4×0 | 44×2 | 9,1% | 40 (90,9%) | 40,2×13,5 | 67,1% | 97,1% | 73,3% | 29×3 |
| BotAdversario2 3×1 (`partida-10`) | 3×1 | 41×2 | 7,3% | 38 (92,7%) | 49,3×9,7 | 84,4% | 99,2% | 74,9% | 41×1 |
| BotAdversario1 10×0 (`partida-26`) | **10×0** | 12×4 | **83,3%** | 2 (16,7%) | 56,9×11,2 | 45,6% | 85,9% | 76,7% | 21×6 |
| BotAdversario1 6×0 (`partida-11`) | 6×0 | 9×5 | **66,7%** | 3 (33,3%) | 52,9×7,2 | 34,5% | 87,5% | 63,6% | 37×6 |
| **nós v6** (`partida-04`) | 3×0 | 7×6 | 42,9% | 4 (57,1%) | 35,8×24,3 | 35,3% | 97,0% | 76,8% | 59×0 |
| **nós v4** (`partida-07`) | 1×0 | 44×3 | 2,3% | 43 (97,7%) | 22,9×23,3 | 55,7% | 93,8% | 71,0% | 32×2 |
| BotAdversario2 × BotAdversario1 (`partida-12`) | **5×0** | **14×0** | 35,7% | 9 (64,3%) | 51,2×24,3 | 72,6% | 97,8% | 86,2% | 17×21 |
| BotAdversario2 × BotAdversario1 15/08 (`partida-13`) | 0×0 | 9×7 | 0% | 7+9 (100%) | 38,8×33,7 | 66,4% | 98,6% | 95,4% | 22×17 |
| nós v4 × BotAdversario1 (`partida-14`) | 0×0(+OT 0-1) | 4×3 | 0% | 100% ambos | 31,2×38,4 | 51,3% | 95,3% | 89,3% | 47×21 |

**Leitura macro: existem DOIS modelos opostos de goleada, e nós não executamos nenhum.**
- **BotAdversario2 = CERCO**: volume massivo (41–51 fin) com conversão média (7–23%) — a v4 nossa
  tinha o MESMO volume (44) com conversão 2,3%; a diferença não é chutar mais, é DE ONDE e
  COM QUANTOS CORPOS.
- **BotAdversario1 antigo = PREDAÇÃO**: volume mínimo (9–12 fin) com conversão absurda (67–83%) —
  a nossa v6 é este modelo pela metade (7 fin, 43%).

## 2. Anatomia — BotAdversario2 (forense do 12×2 e do 5×0)

**Estrutura**: 8–9 jogadores PERMANENTES no campo adversário formando um ANEL em volta do
bloco defensivo do L3; 2 sobram no meio-campo. É um "2-8". Visível em todos os frames de
jogo corrido (t=14, t=37–44 do vídeo `partida-08`).

- **g1 (04:46)**: pressão em bloco, bola trabalhada pela direita-baixa, finalização curta. ~30s após o kickoff.
- **g2 (04:29)**: bola enfiada nas costas da defesa → BAGUNÇA na pequena área com ~6 pretos
  dentro do bloco do L3 → gol no meio do bolo (segunda bola).
- **g5 (03:17)**: roubo no MEIO-CAMPO → gol em ~7s pela linha de fundo direita. Transição-relâmpago.
- **Gols sofridos (7-1 aos 02:30; 10-2)**: contra-ataque do L3 contra o cerco → bolo na área
  do BotAdversario2 → segunda bola vira gol DELE. O enxame corta dos dois lados; o BotAdversario2 aceita o
  custo (2 fin contra/jogo) porque o anel impede o L3 até de transitar (1 roubada no jogo!).
- **5×0 no BotAdversario1 — o dado de scouting mais valioso**: (i) SAÍDA DE BOLA IMUNE ao pressing
  de 4 do BotAdversario1 — passes curtos, 5 erros de passe NO JOGO INTEIRO (97,8%); furado o
  pressing, vira 6v7 no campo do BotAdversario1 com enxame; (ii) o BotAdversario1 roubou 21 bolas e
  finalizou **ZERO** — re-roubo instantâneo pós-perda mata a transição dele no berço;
  (iii) BotAdversario1 SUFOCADO: 0 finalizações em 5 minutos. Contraste 15/08→17/08 (0×0 → 5×0,
  posse líq 38,8→51,2): o BotAdversario2 recebeu UPGRADE nesses 2 dias — ele evolui AGORA.

**Mecanismo do volume+conversão**: o GK do L3 fez 39 defesas — e cada rebote cai num raio
onde o BotAdversario2 tem 2–3 corpos (o anel). Rechute imediato. 51 finalizações = ~12 posses
"enfiadas" × 3–4 tentativas cada. Conversão vem da INSISTÊNCIA ESPACIAL, não do chute limpo:
o 12º chute da sequência pega o GK fora de posição. Nosso second_ball é a mesma ideia com UM
corpo — por isso nosso teto foi 7 finalizações.

## 3. Anatomia — BotAdversario1 antigo (forense do 10×0)

**Estrutura**: 3 defensores FIXOS (x≈130, nem participam) + GK; 7 no meio/frente.

- **g1 (04:51, ~9s de jogo)**: ganhou a disputa do kickoff inicial → 2–3 passes verticais →
  finalização curta. Zero rodeio.
- **g2 (04:44) — A JOIA**: no kickoff do L3 pós-gol, o BotAdversario1 posiciona **6 jogadores em
  anel no círculo central** (t=23 do vídeo), rouba a saída em ~2s e converte em ~5s.
- **g5 (03:08)**: roubo no meio → gol em ~5s. **g8 (02:08)**: OUTRO kickoff predado → gol em ~6s.
- **CASCATA**: gol → kickoff previsível do L3 → predação → gol. 3×0 nos primeiros ~23s de
  relógio; 10 gols com apenas 12 finalizações. Conversão 83% porque TODA chance nasce contra
  defesa desorganizada (GK do L3 só defendeu 2).
- campo_adv baixo (45,6%/34,5%): ele NÃO acampa — mora no meio, rouba e mata. Passes ruins
  altos (31–41): verticalidade arriscada, paga porque cada acerto = chance limpa.

## 4. Diagnóstico causal — nós vs eles

| dimensão | nós (v6) | BotAdversario2 | BotAdversario1 antigo |
|---|---|---|---|
| corpos no campo adversário | 4–5 (35%) | **8–9 (83%)** | 5–7 só em transição (45%) |
| finalizações vs L3 | 7 | **51** | 12 (10 gols) |
| origem das chances | construção + shot_gate | enxame de rebote | kickoff roubado + transição 5s |
| corpos no rebote | 1 (second_ball) | **2–3 no cone do GK** | — (chance já limpa) |
| kickoff adversário | recuamos | pressiona | **6 no círculo (predação)** |
| saída sob pressing | ok vs L3; frágil histórica vs presser | **imune (98%)** | — |
| sofridos vs L3 | **0** (GK 6/6) | 2 | 0 |

Nosso 3×0 é o modelo BotAdversario1 PELA METADE: convertemos bem (42,9%) mas (a) não predamos
reinícios (fonte de 4+ gols dele por jogo), (b) não temos enxame (fonte das 51 do BotAdversario2),
(c) com 4–5 corpos na frente cada posse rende no máximo 1 finalização. Somos os mais SÓLIDOS
da amostra atrás (0 sofridos, GK 100%, 59×0 roubadas) — a base defensiva para acomodar mais
agressividade JÁ EXISTE.

## 5. Propostas de absorção (priorizadas)

Todas OFENSIVAS/de pressão — nenhuma tira corpo do jogo (lei da passividade preservada; o
risco delas é exposição a contra, que nossa retaguarda 0-sofridos pode pagar). Todas
default-off, esteira normal: screening → travas C1/C2/C3 → exame.

1. **`kickoff_press`** (BotAdversario1) — no reinício ADVERSÁRIO, 4–6 jogadores em anel na borda
   permitida do círculo + bote na primeira janela de passe. O L3 sai do kickoff de forma
   padronizada = presa. Impacto esperado: 2–4 roubos altos/jogo ≈ +1–2 gols com nossa
   conversão. Métrica de screening: roubos ≤5s e gols ≤10s pós-kickoff.
2. **`swarm_rebound`** (BotAdversario2) — generalizar o second_ball: quando chute nosso sai OU bola
   entra na área, 2–3 atacantes convergem ao cone de rebote do GK (hoje: 1). É a fábrica das
   51 finalizações. Meta: fin/jogo 7→15+ mantendo conversão ≥25%. Nosso g3 do exame 1 já foi
   um rebote convertido — industrializar.
3. **`high_block`** (BotAdversario2, DOSADO) — com posse no terço final, subir suporte para 6–7 no
   campo adversário (não 8–9; manter 3 atrás como o BotAdversario1). Alimenta o swarm e o re-roubo
   (L3 não transita: 1 roubada contra o cerco). Risco real: contra-ataque (BotAdversario2 tomou 2
   assim) — validar no C3 que ga não sobe.
4. **`outlet_press_resist`** (BotAdversario2 vs BotAdversario1) — saída SÓ com passes curtos de endpoint
   seguro sob pressing; proibir o passe médio atravessando o bloco de 4 (nosso gol sofrido
   histórico). Alvo: matchup BotAdversario1 (os gols dele nascem de erro de saída; o BotAdversario2 provou
   que sem erro o pressing dele vira déficit numérico).
5. **`transition_verticality`** (BotAdversario1) — pós-roubo no meio: progressão obrigatória em ≤3
   passes (não recircular). Métrica: tempo roubo→finalização.

**Sequência sugerida**: 1+2 primeiro (ganho direto de saldo vs L3, ortogonais entre si),
depois 3 (potencializa 2), 4 antes de reencontrar o BotAdversario1, 5 por último (endpoint_race já
cobre parte). Meta pós-absorção vs L3: saldo +5–8/jogo (régua de elite, sob o teto ~+10).

## 6. Apêndice — método e fontes

Vídeos: `https://storage.googleapis.com/lugobots-prod-videos/<mid>.mp4`. Detecção de gol:
crop dos dígitos do placar (x=600 e x=815, 50×55px) @1fps em PGM, diff médio >8 = animação;
gols = pares de clusters ~9s; atribuição lida em mosaicos de placar. Anatomia: mosaicos 2×4
(720px, 8s pré-gol) de 8 lances do 12×2, 2 do 5×0, 4 do 10×0 + gols sofridos. Durações:
12×2=425s (fim normal), 5×0=377s, 10×0=282s (mercy). BotAdversario2 é home nos mids dele; BotAdversario1
home no 10×0. Stats: `analysis/scrape_profiles.parse_match_stats`.

---

## 7. TEORIA DO META (consolidação: núcleo + Eixo A + Eixo B, 16 partidas)

**P1. O jogo se decide em transições e reinícios, não em posse corrida.** Fontes de gol da
elite: (a) kickoff dos DOIS lados — blitz do próprio (BotAdversario2: gol aos 7s) e predação do
adversário (BotAdversario1 antigo e BotAdversario4: anel no círculo, roubo→gol em ~8s); (b) 10–15s
pós-roubo contra defesa desorganizada; (c) rebote com massa (cerco); (d) quina/linha de fundo
com GK deslocado (BotAdversario10, 62%). Posse alta sozinha rende pouco (zemop: 77% de posse → 4×0,
9 fin); acerto de passe 28% rende 10×0 (BotAdversario13) — importa ONDE/QUANDO a bola vira chance.

**P2. GK é imbatível de zona defensável; há DOIS jeitos de furá-lo.** Deslocar (perto/quina/
superioridade: conv. 54–83%) ou saturar (enxame de rebote: cada defesa vira nova chance —
BotAdversario2 tomou 39 defesas e fez 12 gols). BotAdversario14 (52 defesas contra, 5,5%) e nossa v4 (43,
2,3%) não fazem nenhum dos dois — **volume-cego é a estratégia mais punida do meta**.

**P3. Defesa de elite é estrutura posicional, não desarme.** Coluna-de-5 (ecomp/BotAdversario13), 9–10
atrás da linha da bola (BotAdversario1), 3 fixos permanentes (BotAdversario1, até na OT). Contra isso o L3 finaliza
1–2×. Roubada sem transição é estéril (52 roubadas do BotAdversario1 no BotAdversario12 = 0 finalizações).
NÓS já somos elite defensiva vs L3 (0 sofridos, 59×0) SEM abrir mão do pressing — a base está
pronta para pagar risco ofensivo.

**P4. O preço da perda de bola é assimétrico.** Na frente ≈ grátis (BotAdversario13 perde 33 e faz
10×0; BotAdversario2 aceita 2 contra/jogo); atrás/na saída = morte (nossas derrotas pro BotAdversario1;
cascatas 0–5 dele). Regra: risco máximo no último terço, risco ~zero na saída.

**P5. Goleada é cascata auto-alimentada.** Gol → kickoff previsível → predação → gol (3×0 em
~23s do BotAdversario1; g1 aos 7–8s de BotAdversario2/BotAdversario4) + mercy em ~+10. Quem arma reinícios
comprime o relógio até o teto; quem não arma (nós) depende de construção lenta a cada posse.

**P6. O BotAdversario1 NOVO (17/08) é conservador e pouco letal contra bloco assentado** (2 finalizações
em 10 min no 1×1 com o BotAdversario12; sem gol de ouro na OT inteira; só marca na janela
pós-kickoff). O trono está vago: o BotAdversario2 o goleou 5×0 e evolui agora.

**Eficaz:** reinícios armados; massa no rebote; verticalidade pós-roubo; entrada pela quina;
counter-press de 2–3s; saída imune ao pressing. **Punido:** volume de zona defensável sem 2º
homem; posse estéril; bunker passivo (empata, não vence); tirar corpo do jogo (lei 5×).

## 8. Genes candidatos CONSOLIDADOS (dedupe dos 3 relatórios; todos default-off, esteira screening→C1/C2/C3→exame)

| prio | gene | lado | comportamento | fonte | objetivo |
|---|---|---|---|---|---|
| 1 | `kickoff_ring` | of. | 4–6 em anel no kickoff DELES, bote na 1ª janela de passe | BotAdversario1 antigo; BotAdversario4 t=13 | saldo L3 (+1–2 gols/jogo) |
| 2 | `kickoff_blitz` | of. | NOSSO kickoff ensaiado: bloco ao terço final em ≤5s (sinergia kick9/playbook) | BotAdversario2 g1 (gol aos 7s) | saldo L3 (+1) |
| 3 | `swarm_rebound` | of. | 2–3 corpos convergem ao cone de rebote do GK a cada chute nosso | BotAdversario2/BotAdversario4 (pack) | volume: 7→15+ fin, conv. ≥25% |
| 4 | `outlet_press_detect` | saída | sob pressing ≥3: proibir passe curto central; outlet longo de corredor | BotAdversario2 5×0 (5 erros/jogo); BotAdversario12 | BotAdversario1 (modo-de-perder nº3) |
| 5 | `counter_press_window` | of. | 2–3s pós-perda no campo adv.: os 2–3 mais próximos caçam; depois recuo normal | BotAdversario2 (BotAdversario1: 21 roubadas, 0 fin) | BotAdversario1 + sustenta o cerco |
| 6 | `kickoff_shield` | def. | ~10s pós-kickoff (qualquer) compactos antes de abrir o leque | única brecha do BotAdversario1 novo (1×1) | BotAdversario1 (janela pós-kickoff) |
| 7 | `counter_launch` | of. | roubo com ≥3 adv. à frente → lançamento imediato às costas + 2 corredores (métrica: chances criadas, NÃO acerto) | BotAdversario13 (isca+bote) | saldo vs quem sobe a linha |
| 8 | `quina_entry` | of. | com área povoada, portador ataca linha de fundo/quina; passe atrasado se fechar | BotAdversario10 (62%); nosso g1 da v6 | conversão |
| 9 | `mid_deny` | def. | na média central: fechar LINHA DE CHUTE em vez de recuar | bloco do BotAdversario12 tirou o canto-longe do BotAdversario1 | anti canto-longe |
| 10 | `shot_clock_patience` | of. | segurar penetração até ~5 no shot clock sem janela | BotAdversario10 | OPCIONAL — parente da inanição v5; só com trava anti-estéril |
| — | `gk_track` | GK | JÁ PRONTO (patrick-bench): GK rastreia a linha, não a bola | antídoto canto-longe | validar vs BotAdversario1 real (quota patrick) |
| — | `high_block` dosado | of. | 6–7 no campo adv. com posse no terço final (3 atrás) | cerco BotAdversario2 | potencializa 3/5; validar ga no C3 |

Fusões aplicadas: kickoff_press(núcleo)=`kickoff_ring`; outlet_press_resist(núcleo)=
`outlet_press_detect`; transition_verticality(núcleo)=`counter_launch`; `swarm_rebound`
proposto independentemente por núcleo e Eixo A (convergência = confiança).

## 9. Implicações imediatas

1. **Exame 2 (v6 × BotAdversario1 novo), sem mudar nada:** previsão 0×0/1×1 com OT provável; risco nº1 =
   ~15s pós-kickoff/pós-gol (única janela onde o BotAdversario1 novo marcou hoje); na OT o `ot_relief`
   nos faz chutar primeiro contra um BotAdversario1 passivo — vantagem real. Meta ≥0-0 realista;
   vitória exige converter UMA transição alta (nosso pressing 59×0 vs a construção dele).
2. **Pacote-L3 (seeding; desempate = saldo):** genes 1+2+3 → alvo +6–10/jogo (hoje +3, teto
   ~+10 pelo mercy). Primeiro pacote a implementar.
3. **Pacote-BotAdversario1 (mata-mata):** genes 4+5+6 (+9 e gk_track). Antes de reencontrá-lo com chave
   em jogo.
4. **Bancada patrick:** validar gk_track vs BotAdversario1 real (quota própria do patrick).
5. **Vigiar o BotAdversario2:** evolui AGORA (0×0→5×0 no BotAdversario1 em 2 dias); re-scrape antes de cada dia
   de torneio; é a régua do teto e provável final.
6. **Nota de método:** `campo_adv` tem semântica dúbia entre jogos (Eixo A descartou; Eixo B
   achou consistente) — nenhuma conclusão acima depende só dela; não usar isolada.
