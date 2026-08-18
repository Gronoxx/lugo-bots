# FORENSE DO 10×0 — como se produz um chute que o goleiro NÃO defende (18/08)

Missão: nossa v8 faz 3,12 gols/jogo no level-1 com 9,1 finalizações (**34%**), enquanto
BotAdversario6 faz 10×0 no level-2 com 11 finalizações (**91%**). O gargalo é CONVERSÃO. Este
relatório mede a GEOMETRIA dos gols de quem goleia e a compara com a nossa.

Método: vídeo da plataforma (1440×810, 16 fps). Calibração verificada e **fixa em todos os
vídeos**: retângulo do campo em px `x[130,1329] y[120,714]` ⇒ **16,68 unidades/px**. Detecção
por componentes conexos (`scratchpad/f10/an10.py`): jogadores por cor, bola = blob escuro
pequeno FORA de qualquer círculo branco. Ressalva honesta: o rastreio da bola **congela no
instante em que ela cruza a linha** (último ponto válido = ponto de ENTRADA no gol) e a origem
do chute é aproximada pela posição da bola 0,2–0,3 s antes. Distâncias têm erro ~±150.

## 1. BotAdversario6 10×0 level-2 (`REDACTED`)

Gols detectados por mudança do dígito do placar em t = 15, 62, 92, 143, 159, 186, 222, 273,
313, 345 s.

| # | t (s) | d_gol na origem | entrada \|y−5000\| | y do GK | folga GK→bola | def a <4k | atq a <4k |
|---|---|---|---|---|---|---|---|
| 1 | 15 | ~2300 (bola vinha de y=8258) | 1911 | 5177 | 1735 | 10 | 5 |
| 2 | 62 | 2288 | 1477 | 5210 | 1267 | 9 | 3 |
| 3 | 92 | **1316** | 1271 | 4892 | 1163 | 12 | 3 |
| 4 | 143 | 2132 | 1506 | 4941 | 1447 | 12 | 6 |
| 5 | 159 | ~2400 | 1659 | 5328 | 1330 | 8 | 3 |
| 6 | 186 | 2872 | 1574 | 5480 | 1095 | 6 | 5 |
| 7 | 222 | 2645 | 1552 | 5412 | 1139 | 4 | 4 |
| 8 | 273 | 2466 | 1653 | 5330 | 1323 | 3 | 4 |
| 9 | 313 | ~2660 | 1540 | 5430 | 1110 | 11 | 4 |
| 10 | 345 | **1701** | 1270 | 4722 | 993 | 5 | 2 |
| **mediana** | | **~2400** | **1530** | **5270** | **1230** | **9** | **4** |

**PADRÃO DOMINANTE (10/10 gols, sem exceção):**
1. **A bola entra colada a um POSTE.** A boca vai de y=3500 a 6500 (meia-largura 1500) e a
   mediana da entrada é |y−5000| = **1530** — ou seja, exatamente na quina do gol. Nenhum gol
   entrou pelo meio.
2. **O goleiro está CENTRALIZADO** (mediana y=5270, contra o centro 5000). Ele nunca está no
   poste onde a bola entra: a folga mediana é **1230**.
3. **O chute sai de PERTO: mediana 2400, faixa 1300–2900.** Nenhum gol veio de >3000.
4. **A aproximação é pelo FLANCO/linha de fundo.** Em 6 dos 10 gols a bola vinha de
   |y−5000| = 2100–3300 (fora da faixa da boca, na beirada) antes de entrar no poste próximo.
5. **Bastam 3–5 corpos no terço de ataque** (mediana 4) — não é preciso o cerco de 8–9.

Leitura tática complementar (mosaicos `scratchpad/f10/mos/gol_*.png`): o **level-2 persegue a
bola em bando** — nos frames pré-gol aparecem 9–12 jogadores dele amontoados num raio pequeno.
Isso deixa os flancos e a linha de fundo VAZIOS, e é por ali que o BotAdversario6 entra. Ele não
"fura o bloco": ele contorna o bando.

## 2. BotAdversario1 10×0 level-3 (`REDACTED`) — modelo diferente, MESMA geometria

Gols em t = 14, 28, 43, 124, 148, 164, 215, 232, 249, 265 s (note os **três primeiros em 43 s**
— a cascata de predação de kickoff já descrita em METAMORFO §3). O rastreio automático da bola
não é confiável neste vídeo (os dois times são coloridos e há artefatos estáticos escuros), então
a leitura foi VISUAL (`mos/adv1_*.png`).

- **Gol t=43**: a bola chega até a quina direita quase na linha de fundo; o GK do level-3 está
  deslocado para BAIXO e a finalização entra por cima dele. 5 defensores na área não impedem.
- **Gol t=265**: medido no frame −0,7 s → bola em (19766, 6147), **colada ao poste inferior**,
  com o GK em (19933, 5338) — folga ~800. Chute de dentro da área, de lado.

**CONFIRMA a hipótese**: o BotAdversario1 chega ao mesmo TIPO de chute (perto + poste + GK fora do
eixo); o que muda é o MECANISMO de chegada (transição/predação de reinício contra defesa
desorganizada, em vez da condução pelo flanco do BotAdversario6). Dois caminhos, um mesmo destino
geométrico.

## 3. O CONTRASTE — de onde NÓS chutamos (v8, 16 replays vs level-1)

`bench/shot_distance_curve.py` sobre `abt_v8_l1_test_*`: 146 chutes on-goal, 50 gols (34,2%).

| faixa de distância | chutes | gols | conversão |
|---|---|---|---|
| 0–2000 | 13 | 11 | **84,6%** |
| 2000–2600 | 24 | 15 | **62,5%** |
| 2600–3200 | 18 | 8 | 44,4% |
| 3200–3800 | 20 | 5 | 25,0% |
| 3800–4500 | 22 | 6 | 27,3% |
| **4500–6000** | **48** | **5** | **10,4%** |
| 6000+ | 1 | 0 | 0% |

**O DIAGNÓSTICO EM UMA LINHA: um terço dos nossos chutes (48 de 146) sai de 4500–6000, onde
convertemos 10%.** Na faixa em que o BotAdversario6 vive (≤2600) nós convertemos **62–85%** — ou
seja, nossa FINALIZAÇÃO não é pior que a dele; nossa SELEÇÃO de chute é.

Cuidado com a conclusão fácil: cortar os chutes longes sozinho NÃO resolve (foi o que o gate
híbrido da v6 fez, e o volume desabou — 3 finalizações no exame vs BotAdversario1). Os 48 chutes
longes representam 48 posses que chegaram a 4500–6000 **e não souberam continuar**. O ganho
está em converter essas posses em chegada, não em descartá-las.

## 4. SÍNTESE — condições geométricas do chute de alta conversão

Critérios avaliáveis em tempo real pelo bot (todos já computáveis com o que existe em
`geometry.py`):

| condição | valor-alvo | evidência |
|---|---|---|
| distância ao gol | **≤ 2600** (ótimo ≤2000) | conv. 62–85% nossa; mediana 2400 do BotAdversario6 |
| ponto de mira | **poste**: \|y_alvo−5000\| ≈ 1300–1500 | 10/10 gols do BotAdversario6 |
| folga do GK ao ponto de mira | **≥ 1000** | mediana 1230 (BotAdversario6), 993 no mínimo |
| posição do chutador | preferir **\|y−5000\| ≥ 2000** (flanco/linha de fundo) | 6/10 gols |
| corpos nossos no terço | **3–5 bastam** | mediana 4 |
| densidade adversária | **irrelevante** (9–12 defensores perto em metade dos gols) | não bloqueiam |

**Mecanismos de chegada, por frequência observada:**
1. Condução/progressão pelo FLANCO até a linha de fundo, depois chute ao poste próximo (6/10 —
   BotAdversario6; é também o mecanismo do nosso gol 1 no 3×0 vs level-3).
2. Transição rápida contra defesa desorganizada, com o GK ainda a caminho do centro (BotAdversario1;
   nossos gols de rebote).
3. Rebote/segunda bola dentro da área (ambos, minoritário).

## 5. MUDANÇAS PRIORIZADAS NO NOSSO BOT

1. **Gate por distância COM alternativa de penetração** (o mais importante). Hoje
   `dangerous_shot_range=6000` autoriza chute até 6000 e `shot_gate=threshold` da v8 não olha
   distância. Proposta: manter o gate aberto até ~3200 e, **acima disso, em vez de chutar,
   PENETRAR** (conduzir/tocar rumo à quina). Sem a alternativa, repete-se a inanição da v6.
   Genes: `shot_gate=hybrid` com `hybrid_close_range≈3200` **junto de** `quina_entry=on` —
   o `quina_entry` foi descartado numa bisseção anterior por perder volume, mas ele é
   exatamente a peça que faltava para o híbrido não travar. Testar o PAR, não cada um.
2. **Mirar o poste, não o melhor ponto genérico.** `_best_shot_target` escolhe o ponto de maior
   folga, o que tende ao centro quando o GK está descentrado. Com o GK centralizado (o caso
   real), a maior folga JÁ é o poste — verificar se `shot_post_margin=200` está empurrando a
   mira para dentro demais; reduzir para ~120 amplia a mira de canto.
3. **Buscar posição de flanco antes de finalizar.** `angle_seek` (off) leva o portador a
   `shot_lateral=1750` do centro — perto do alvo de |y−5000| ≥ 2000 observado. Ligar junto com
   o item 1.
4. **Não gastar posse com chute de 4500–6000.** É onde estão 33% dos nossos chutes e 10% de
   conversão. Cada um desses é uma posse doada ao goleiro adversário.
5. Manter `swarm_rebound` (o rebote é o 3º mecanismo) e o pacote de kickoff — eles já estão
   validados e não conflitam com o acima.

**Ordem de teste sugerida:** (A) `hybrid_close_range 3200` + `quina_entry on` + `angle_seek on`
contra o level-1, medindo finalizações E conversão; (B) se a conversão subir mas o volume cair,
adicionar `carry_mode=touch` para acelerar a chegada ao flanco.
