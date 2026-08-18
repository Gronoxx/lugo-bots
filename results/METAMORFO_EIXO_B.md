# METAMORFO — EIXO B: o problema BotAdversario1 (17/08/2026)

Forense do matchup BotAdversario1: como sobreviver a ele e como furá-lo. Fontes: vídeo completo de
BotAdversario12 1×1 BotAdversario1 (`partida-21`, **17/08 17:10 UTC — BotAdversario1 NOVO, o mesmo do nosso exame 2**),
defesa do BotAdversario1 10×0 L3 (`partida-27`), amostras de partida-11/partida-22 (6×0 home, 13/07 e 09/07) e
a60c3be1 (0×10 away, 09/07), stats da tabela mestra (`scratchpad/metamorfo_stats.csv`).
Complementa o núcleo (kickoff-press do BotAdversario1 antigo; BotAdversario2 5×0 = saída imune + re-roubo).

## 1. O jogo BotAdversario12 1×1 BotAdversario1 (a peça central — BotAdversario1 ATUAL)

Linha do tempo (vídeo 483s, dígitos do placar + relógio):
- **t≈73 (03:58 do 1º tempo): GOL DO BotAdversario12** — a ÚNICA finalização dele no jogo (conv
  100%). Anatomia: todo o time (8–9) empurrando a segunda bola no campo do BotAdversario1, a bola escapa
  para a **quina alta direita** (linha de fundo) e sai chute de ângulo fechadíssimo. Não foi
  construção: foi chutão + enxame + caos na borda da área.
- **t≈98 (03:42): GOL DO BotAdversario1, 16s de relógio depois** — kickoff do BotAdversario1 → condução direta pelo
  meio (~10s) → penetra o bloco **ainda desorganizado pós-gol** com 3–4 atacantes → finaliza de
  DENTRO da área. **Não foi o chute de média/canto longe** que nos matou: contra bloco baixo ele
  penetrou; e só conseguiu porque o bloco não estava assentado.
- **t≈98→467 (~8 min de relógio, incl. OT inteira até −01:57): NADA.** O BotAdversario1 finalizou 2× no
  jogo TODO. O bloco assentado nunca mais foi furado — nem no gol de ouro que contra nós saiu.

Estruturas observadas:
- **BotAdversario12**: bloco de ~10 no próprio campo/meio, compacto e central; posse líquida 3,7%,
  30,8% de acerto de passe — ele NÃO constrói: chutão para frente (campo_adv 91,4%: as raras
  posses dele acontecem quase todas no campo do BotAdversario1) + enxame pontual atrás da segunda bola.
  As **52 roubadas do BotAdversario1 foram todas em zona inofensiva** (meio, com o bloco já pronto atrás):
  roubada sem transição = roubada estéril.
- **BotAdversario1 novo**: pressiona a saída adversária com 6–7 (t=8–13; não vimos o anel pré-kickoff de
  julho), mas mantém **3 fixos + GK SEMPRE** — inclusive na OT precisando do gol de ouro
  (t=406–426: BotAdversario12 empurra o jogo pro campo do BotAdversario1 e o BotAdversario1 não se lança). BotAdversario1 novo é
  mais conservador e **pouco letal contra bloco assentado**.

## 2. Como o BotAdversario1 defende (10×0, `partida-27`; data não listada no perfil — págs cobrem até set/2025 sem ele; estilo consistente com julho/2026)

- Quando o adversário tem a bola, o BotAdversario1 **recua em massa: 9–10 corpos atrás da linha da bola
  no próprio terço** (flagrado em t=45 e t=255 — exatamente as DUAS únicas chegadas do L3 no
  jogo, que morrem na densidade; GK do BotAdversario1: 2 defesas). Zera por ESTRUTURA (16 roubadas
  apenas), não por desarme.
- Com bola: 6–7 avançam, 3+GK ficam. Home nos 6×0: **modo isca** — circula no próprio campo
  (campo_adv 34%), o L3 avança (65% da posse do L3 no campo do BotAdversario1), facada nas costas.
  Away no 0×10 (julho): pressing altíssimo na saída do L3 com 7 → **0–5 em <2 min de relógio**
  (cascata roubo→gol→kickoff→roubo). O BotAdversario1 escolhe o modo pelo contexto.
- Leitura do `campo_adv` validada como consistente: fração do tempo de posse do time passada no
  campo adversário (BotAdversario12 91,4% com pl 3,7% = só chutão; BotAdversario1 8,6% = circulou atrás).

## 3. Blueprint anti-BotAdversario1 (BotAdversario12 ∩ BotAdversario2)

**O que os dois casos de sucesso têm em comum: NEGAR A TRANSIÇÃO.** O BotAdversario1 vive de bola ganha
em zona de facada (saída adversária, bloco desorganizado). O BotAdversario12 nega por não construir
(chutão: nenhum passe interceptável na saída); o BotAdversario2 nega por construir de forma imune
(5 erros de passe no jogo inteiro) E re-roubar imediatamente pós-perda (BotAdversario1: 21 roubadas,
0 finalizações no 5×0). Onde divergem: bunker 10-atrás + 1 chute (BotAdversario12, empate) vs
domínio com posse + counter-press (BotAdversario2, 5×0).

**Caminho compatível com o NOSSO bot: o do BotAdversario2.** O bunker do BotAdversario12 viola a lei da
passividade (5 rejeições) e rebaixa nosso ataque (que já converte 42,9%). Nossa base já é
sólida atrás (0 sofridos vs L3, GK 6/6, saída 99,6% nos benches). O que falta é cirúrgico:
1. **Não dar a saída ao pressing** (nosso modo-de-perder nº3: passe de saída interceptado);
2. **Counter-press pós-perda** no campo adversário (a roubada estéril do BotAdversario1 prova que perder
   a bola com estrutura atrás não é perigo — perigo é deixá-lo transitar);
3. **Cobrir a janela pós-kickoff** (o único gol do BotAdversario1 novo no 1×1 nasceu aí; nossos ~15s
   pós-gol/kickoff são a janela dele).

**Sobre o canto-longe** (arma que nos matou na OT): com bloco central denso o BotAdversario1 NÃO tentou
média distância no 1×1 — a janela do chute some com miolo compacto na frente da área. Antídoto
direto continua sendo o gk_track (patrick-bench, ainda não testado vs BotAdversario1 real).

## 4. Exame 2 (v6 × BotAdversario1 novo): expectativa honesta

- A v6 muda o ATAQUE, não a defesa: dos nossos 3 modos de perder pro BotAdversario1 (rebote não-limpo,
  condução no presser, passe de saída interceptado), a v6 **não mitiga nenhum diretamente** —
  mas reduz o combustível dele: menos chutes doados = menos defesas do GK deles = menos
  transições (e o BotAdversario1 novo quase não cria contra bloco pronto: 2 finalizações em 10 min).
- Nosso pressing alto (59 roubadas×0 vs L3) contra a construção conservadora do BotAdversario1 (3 fixos
  circulam) pode gerar a chance rara — é o mecanismo do 5×0 do BotAdversario2 em versão embrionária.
- **Previsão: 0×0/1×1 com OT provável.** Na OT, o BotAdversario1 do 1×1 circulou passivo; o
  `ot_gate_relief=260` nos faz chutar primeiro — vantagem real num jogo de uma chance só.
- **Riscos concretos: (a) os ~15s pós-kickoff (nosso E deles) e pós-gol — é ONDE o BotAdversario1 novo
  marca; (b) rebote não-limpo na nossa área (modo nº1, inalterado).** Meta do exame (≥0-0 no
  normal) é realista; vitória exige converter UMA transição alta.

## 5. Genes candidatos do Eixo B (default-off, esteira screening→C1/C2/C3→exame)

| # | gene | comportamento | mecanismo que replica | risco/lei da passividade |
|---|---|---|---|---|
| 1 | `outlet_press_detect` | sob pressing de ≥3 na zona de saída, proibir passe curto lateral/central; outlet longo pro corredor (estende o gk_outlet aos jogadores de linha) | saída imune do BotAdversario2 / chutão do BotAdversario12 (zero interceptações em zona letal) | ofensivo-neutro; não tira corpo do jogo |
| 2 | `counter_press_window` | 2–3s pós-perda no campo adversário: os 2–3 mais próximos caçam a bola; depois recuo normal | re-roubo do BotAdversario2 (BotAdversario1: 21 roubadas e 0 finalizações) | janela curta e local — é ADIÇÃO de agressividade |
| 3 | `kickoff_shield` | ~10s pós-kickoff (qualquer), meio-campo compacto antes de abrir o leque | única brecha que o BotAdversario1 novo achou no 1×1 | posicional e temporário; medir custo ofensivo no screening |
| 4 | `mid_deny` | bola adversária conduzida na zona de média central (d≈2500–4500 do nosso gol): marcador mais próximo fecha a LINHA DE CHUTE em vez de recuar | anti canto-longe (nosso 0×1); bloco denso do BotAdversario12 tirou esse chute do BotAdversario1 | posicionamento do corpo existente, não corpo a menos |
| — | `gk_track` (já pronto, patrick-bench) | GK rastreia a linha, não a bola | antídoto direto do canto-longe | validar vs BotAdversario1 real na quota do patrick |

Prioridade: 1 e 2 (atacam o mecanismo central do BotAdversario1 E são genes de agressividade), 3 barato e
cirúrgico, 4 experimental. Nada entra na main sem o exame — e o exame 2 atual roda com a v6
como está.

## Apêndice de método

Gols localizados por diff nos crops PGM do placar (clusters: bit×BotAdversario1 t≈{74,83,99,107,467} =
2 gols + fim; 10×0 t≈{70,106,151,191,216,241,319,339,358,381}); relógio da OT em formato
NEGATIVO (−00:00→−02:00). Mosaicos 2×4/2×2 no scratchpad (`bg1/bg2/bkick/bot/ddef/s6a/s6b/saw`).
BotAdversario12 aparece como "AVENGERS" no player. Datas por scrape dos perfis (BotAdversario12 pág 1;
BotAdversario1 págs 1–11). Vizinhança do 1×1 no perfil do BotAdversario12: ele fez 0×1 vs BotAdversario1 em 16/08
(`partida-24`) e 2×0/0×0/0×0 vs L3 — bot fraco no ataque que ANULA o BotAdversario1: a prova de que negar
transição ≫ qualidade geral no matchup.
