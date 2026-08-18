# METAMORFO — EIXO A: o gerador de gols vs level-3 (17/08/2026)

Forense de vídeo completa de 4 goleadas + anti-padrão, complementando o núcleo (cerco do
BotAdversario2 12×2; predação do BotAdversario1; mercy ~+10). Método: detecção de gols por diff do placar
(pares gol+eco ~9s), mosaicos 2×4 dos 8s pré-gol, painéis t−2 dos demais. Frames em
`scratchpad/eixoA/`. **Nota de método: a métrica `campo_adv` do site tem semântica
inconsistente entre jogos (leituras contraditórias em BotAdversario6/BotAdversario12/BotAdversario10) — foi
DESCARTADA das conclusões.**

## Gols localizados (t = segundo de vídeo do início da animação)

| jogo | mid | gols (t) |
|---|---|---|
| BotAdversario4 10×0 L3 | 93d4c064 | 13, 111, 131, 150, 171, 197, 228, 280, 311, 375 |
| BotAdversario10 10×0 L3 (away) | 225a6722 | 26, 63, 80, 116, 137, 155, 191, 215, 268, 288 |
| BotAdversario13 10×0 L3 (away) | 76949afd | 47, 63, 91, 137, 153, 184, 276, 292, 314, 330 |
| BotAdversario2 7×0 L3 | 7c531e81 | **11**, 75, 111, 202, 251, 272, 295 |
| BotAdversario14 3×0 L3 | 655a4e4a | 16, 166, 305 |

## Anatomia por bot

**BotAdversario4 (INFO JR) 10×0 — TRANSIÇÃO EM BLOCO.** Gol 1 aos t=13 (04:52 de relógio, ~8s
de jogo): anel de ~8 no círculo central sobre o kickoff do L3 → roubo → enxame → gol
(replica o kickoff-press do BotAdversario1 descrito pelo núcleo — CONFIRMAÇÃO INDEPENDENTE em outro
bot). Demais gols: roubada no meio (42 no jogo) → o BLOCO INTEIRO (5–8 jogadores) avança
junto → arco de 6+ na frente da área → chute da entrada COM apoio para rebote. G10 aos 00:04
do fim (não desliga nunca). Volume 27 = cada roubada vira ataque com massa; conversão 37% =
chute + corpo + rebote contra GK saturado.

**BotAdversario10 10×0 (away) — CIRURGIA DE QUINA.** Estrutura RADICAL visível em todos os frames:
**5 jogadores fixos em coluna vertical na frente da própria área o jogo inteiro** + 4–5
atacantes + GK. Os 4 furam bloco de 8–9 do L3 com 96,6% de acerto; entradas preferenciais
pelas QUINAS/linha de fundo da área (g1 quina baixa t=26; g3 quina alta t=135 — a mesma
anatomia do nosso gol 1 da v6), finalização só de dentro. **Joga o shot clock até 02–06
antes de penetrar** (paciência calibrada pelo relógio de posse). Transição curta quando
rouba no meio (g8). Conversão 62% com apenas 16 finalizações. Defesa: L3 fez 1 finalização —
contra-ataque morre na coluna de 5.

**BotAdversario13 10×0 (away) — ISCA + BOTE.** Resolve o paradoxo (acerto de passe 27,8%, posse líq.
11,1%, e 32 fin/31%): deixa o L3 SUBIR com 7–8 (posse bruta do L3 58,7%), defende com a
mesma espinha 5-fixos+GK do ecomp (colunas visíveis em t=274/312), e na recuperação lança
IMEDIATAMENTE longo nas costas da linha alta → 2–4 corredores atacam metade vazia → chance
3v2/2v1. O acerto baixo é FEATURE: lançamento de risco barato — bola perdida na frente,
longe do próprio gol, recomeça no ciclo. Viés de zona: quase todos os gols vistos entram
pela quina baixa da área. Por que o L3 não pune: o BotAdversario13 nunca perde a bola atrás.

**BotAdversario2 7×0 — a segunda cara: PRESSING + BLITZ DE KICKOFF PRÓPRIO.** Gol 1 aos t=11
(04:53, ~7s): o PRÓPRIO kickoff convertido em blitz — saída + avanço do time inteiro em
bloco + gol antes do primeiro reset do shot clock. Demais: pressing que estrangula o L3 no
meio (57 roubadas; o L3 tentou jogar com 43,5% de posse) → enxame no terço final, entradas
pelas quinas (g2 t=73, g6 t=270). Mesma assinatura de cerco do 12×2 (núcleo), dosada com
pressing mais alto. Conversão 54%.

**BotAdversario14 3×0 — ANTI-PADRÃO (a "nossa v4" dos outros).** 55 finalizações on-goal, 3 gols
(5,5%); o GK do L3 fez **52 defesas** (94,5%). Frames: ataca com 1–2 corpos (resto atrás),
chuta de zonas defensáveis (média/longa com GK posicionado), NENHUMA estrutura de rebote —
as 52 defesas caem no vazio. Defensivamente recua 10 mas não pressiona (8 roubadas) e ainda
sofre 17 finalizações do L3. Posse líquida 10%: não controla nada. Diagnóstico: volume-cego
= chute defensável + ausência do 2º/3º homem. Nossa v4 (44 fin/2,3%, 43 defesas) era
EXATAMENTE isto; a v6 curou a distância do chute mas não adicionou o apoio → por isso 7
finalizações.

## Respostas às perguntas do eixo

**(a) Enxame de rebote é geral?** NÃO — é um de DOIS geradores. BotAdversario4 e BotAdversario2: SIM
(bloco/enxame chega junto; rebote cai no pack). BotAdversario10 e BotAdversario13: NÃO — geram volume por
outra via (quina/linha de fundo com GK deslocado; contra-ataque em superioridade). O comum é
outro (ver c).

**(b) Segundo gerador de volume além do rebote?** SIM, três:
1. **Reinícios armados (os dois lados do kickoff)**: blitz do próprio kickoff (BotAdversario2, gol
   em 7s) e anel sobre o kickoff adversário (BotAdversario4 t=13; = kickoff-press do BotAdversario1).
   Gols baratos e repetíveis — a cascata gol→kickoff→gol comprime o tempo.
2. **Transição vertical pós-roubo** (BotAdversario13; BotAdversario4 em bloco): lançar nas costas ANTES
   da defesa voltar; aceitar passe errado como custo (perda na frente ≈ grátis).
3. **Entrada pela quina/linha de fundo** (BotAdversario10; BotAdversario2; nosso gol 1 da v6): desloca o
   GK ao poste e abre o gol — conversão 54–62% sem depender de rebote.

**(c) O que os 4 goleadores têm que o BotAdversario14 não tem?** (i) **Apoio no lance de chute** —
2º/3º homem SEMPRE (para rebote no modelo-bloco, para o passe da quina no modelo-cirurgia);
(ii) **chute só de zona não-defensável** (perto/quina/GK deslocado/superioridade) OU com
rebote garantido; (iii) **estrutura defensiva posicional constante** (coluna de 5 do
ecomp/BotAdversario13; bloco que volta junto do BotAdversario4) em vez de "todo mundo atrás
desorganizado"; (iv) **reinícios tratados como jogadas** e não como neutros.

**(d) Absorção → genes candidatos** (todos ofensivos, default-off, esteira
screening→C1/C2/C3→exame; nenhum tira corpo do jogo — lei da passividade preservada):

| # | gene | comportamento | mecanismo replicado | ganho esperado | risco |
|---|---|---|---|---|---|
| 1 | `kickoff_blitz` | no NOSSO kickoff: saída ensaiada + avanço em bloco dos 5 da frente ao terço final em ≤5s | BotAdversario2 g1 (gol aos 7s); sinergia com kick9/playbook (que já converte reinícios 0→38% de terço) | +1 gol/jogo vs L3; comprime cascata pós-gol | baixo (janela curta; se falhar, vira jogo normal) |
| 2 | `kickoff_ring` | no kickoff DELES: 4–6 em anel na borda do círculo, salto coordenado no 1º toque → roubo → blitz | BotAdversario4 t=13; BotAdversario1 (núcleo) | +1–2 gols/jogo vs L3 (L3 entrega a saída) | verificar legalidade do posicionamento no reinício (REFERENCIA_LUGO); fallback = recuo normal |
| 3 | `swarm_rebound` | a cada chute nosso, 2–3 corpos convergem ao cone frontal do GK antes do impacto | BotAdversario4/BotAdversario2 (pack); é o nosso second_ball com massa | 7→15+ fin mantendo conv. ≥25% (o rebote do GK deixa de morrer no vazio) | médio: tira 1–2 jogadores de posições — dosar por distância do lance |
| 4 | `counter_launch` | pós-roubo no nosso campo com ≥3 adversários à frente da linha da bola: lançamento imediato à zona das costas + 2 corredores | BotAdversario13 (isca+bote); explora L3/rivais que sobem | chances 2v1 baratas; métrica = chances criadas, NÃO acerto de passe | baixo (perda na frente é barata); não conflita com wait — é gatilho situacional |
| 5 | `quina_entry` | com área povoada, portador ataca a linha de fundo/quina em vez do centro; passe atrasado ao pack se fechar | BotAdversario10 (62% de conv.); nosso g1 da v6 já foi assim | conversão ↑ nas entradas que hoje morrem no centro | baixo |
| 6 | `shot_clock_patience` | reter penetração até shot clock ~5 quando não há janela (não chutar cedo de longe) | BotAdversario10 | menos chutes doados | CUIDADO: parente da inanição da v5 — só com contador corrigido e trava anti-estéril |

**Sequência recomendada**: 2+1 (reinícios: ganho maior e ortogonal ao resto) → 3
(multiplicador de volume; par natural com o hybrid da v6) → 4 (monetiza adversário que
sobe) → 5 → 6 (opcional). Observação estrutural para o Eixo B (sem propor): a solidez
defensiva de ecomp/BotAdversario13 vem de coluna POSICIONAL de 5 — dado, não recomendação, dado o
nosso histórico de passividade.

## Contrastes de triangulação (stats-only)

BotAdversario11 6×0 (15 fin/40%, posse líq. 15,7%): perfil transição-direta, consistente com o
modelo BotAdversario13-lite. BotAdversario6 4×0 (9 fin/44%, 500 passes, posse 77,6%): modelo ecomp-like de
posse, volume baixo — prova que posse SEM os 4 cirurgiões rápidos gera pouco volume.
BotAdversario4 0a9ae22d (23 fin/43%, 30 roubadas): reprodutibilidade do modelo-bloco em duas
partidas. BotAdversario13 5×0 home (19 fin/26%, 33 bolas perdidas!): o isca-e-bote funciona até
perdendo 33 bolas — confirma que perda na frente é custo aceitável.

## Implicação direta para o nosso bot

A v6 já tem o chute certo (42,9%) e a defesa certa (0 sofridos, 59 roubadas). O que falta é
**fábrica de situações**: reinícios armados (genes 1–2), massa de rebote (3) e verticalidade
situacional (4). Com 15–20 finalizações de qualidade/jogo, o saldo vs L3 sai de +3 para a
faixa +6–10 da elite — que é o critério de desempate do seeding.
