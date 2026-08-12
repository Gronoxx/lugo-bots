# Plano de melhoria do bot v9 — só heurística/tática (pesquisa multiagente + revisão adversarial)

> Gerado por orquestração multiagente (RoboCup 2D, analytics tático, movimentação sem bola,
> defesa, coordenação multiagente, tuning sob ruído) + mapa do código + crítica adversarial.
> Premissas verificadas no código: genes mortos em `params.py:99-105`; `_best_pass` trava em
> `best_score=0.0` (`my_bot.py:311`) → passe lateral/pra trás é inalcançável; gate estático
> `gap < shot_min_gap` (`my_bot.py:284`); `we_are_closest`/`marking_target` em `tactics.py:108,120`.

## 1. Resumo executivo

O v9 já resolve o miolo geométrico. O gargalo real **não é ter mais ideias — é conseguir medir qualquer coisa**: a fitness de gols tem σ≈0,9/jogo, então quase nada abaixo é distinguível de ruído sem uma proxy densa. Por isso o item 1 não é "mais uma ideia", é o **portão de entrada de todas as outras**.

A tese ofensiva que sobrevive é estreita e coerente com o que medimos (passe ≫ corrida, campo esparso, folga do goleiro é tudo): **fabricar folga temporal do goleiro e finalizar antes que ele a feche**. Três alavancas baratas fazem isso reaproveitando genes já declarados mas mortos: (a) alinhar a *decisão* de chute com o *driver medido* (gate por folga temporal, quase de graça); (b) **condução de toque** (`carry_mode="touch"`); (c) o **padrão do lado fraco** — trocar o jogo/cruzar para o poste oposto e concluir *one-touch* (uma jogada, não três). Cortados: passe-em-profundidade em time (coordenação frágil entre agentes sem comunicação), e rebaixados marcação individual e consciência de placar (vs level-1 sofremos ~0 → sem sinal para otimizar).

## 2. Métrica proxy recomendada (pré-requisito de tudo)

**Folga temporal do goleiro por chance, medida em pares CRN — reportada como DUAS colunas, não somada** (somar gera peso arbitrário e mascara Goodhart):

```
para cada chance a ≤6000d com lane livre E alvo DENTRO das traves (guard on-target):
  v_final = velocidade da bola após o chute somado, limitada a 400
  t       = turns_for_ball(v_final, d)              # geometry.py
  reach   = GOALKEEPER_HALF_EXTENT + 200*t          # 560 + 200t
  slack   = |aim.y − gk.y| − reach                  # >0 ⇒ goleiro não cobre
Reportar:  (A) slack médio no chute   (B) fração de chutes com slack>0
           (C) nº de posses que chegam a ≤6000d com algum alvo de slack>0
```

- **Guard on-target (anti-Goodhart):** só conta slack se o alvo está entre as traves *e* a bola chega com `v_final` suficiente. Sem isso, o otimizador "ganha slack" mirando fora do gol. **Feche esse furo antes de qualquer A/B.**
- **Por quê:** é o fator medido (135 chutes: <1200→0%, >1800→45%), agora contínuo e denso (1 amostra/chute, não 1 gol/jogo), definido mesmo sem a bola entrar (avalia off-ball com ruído quase nulo), e sai de graça do código de finalização.
- **Métrica-fusível (guarda o zero sofrido):** *screen-breach* = nº de turnos em que um adversário teve reta livre a ≤6000d do NOSSO gol sem defensor nosso no cone `±arctan(100/s_bola)` da reta portador→nosso-gol. **Regra de aceite:** promover só se melhora (A) ou (B) com significância pareada E NÃO piora o fusível.

**Protocolo (corta n de ~315 para ~10-30 jogos):**
- **CRN pareado:** base e variante nas MESMAS seeds/adversário; Δ por seed (Wilcoxon/t-pareado). Var(Δ)=2σ²(1−ρ); ρ≈0,7 → ~30% do custo.
- **Uma feature por vez**, portão sequencial: pare quando o IC pareado exclui 0.
- **Contrafactual in-game (custo zero de jogos):** a cada chute/passe, logar slack da ação tomada vs. da alternativa que a variante escolheria — mede o efeito da regra sem jogos extras.
- **Gols só na confirmação final** do pacote campeão (~50-70 jogos pareados), validando uma vez que Δproxy ⇒ Δgols (checagem de Goodhart).

---

## Antes das quartas

### 1. Gate de chute por folga temporal + termo one-touch  `[ataque | valor: alto | esforço: baixo]`
- **O que:** trocar o gate estático (`gap < shot_min_gap=1300`, `my_bot.py:284`) pela **folga temporal real** `|aim.y−gk.y| − (560+200·t_bola)`, e preferir miras *one-touch* (quando a velocidade atual da bola já aponta ao alvo, `factor`≈1 e a soma eleva `v_final` → `t` cai → slack sobe).
- **Teoria:** é a *própria* proxy aplicada à decisão — alinhar o chute ao driver nº 1 medido. Física do `_apply_server_kick` (`factor=0.5+0.5((180−ang)/180)`, somado, cap 400).
- **Implementação:** em `_best_shot_target()` (`my_bot.py:215`): computar `t_ball` e `slack`; exigir `slack > shot_min_slack` (gene novo, 0-1500) com `score=slack`; somar `w_onetouch·max(0, cos∠(ball.vel, aim−ball.pos))`. Manter `dangerous_shot_range` + rejeição por interceptação. O(9 miras). Reaproveita `shot_gate` como modo `"slack"`.
- **Como testar:** proxy (A)/(B) na hora + contrafactual in-game — sem jogos novos para o 1º sinal. Menor esforço, maior alavancagem.

### 2. Condução de toque (self-pass)  `[ataque | valor: alto | esforço: baixo]`
- **O que:** empurrar a bola ao espaço livre à frente e correr atrás, em vez de segurar colado. Bola 4× o jogador → progressão muito maior.
- **Teoria:** Short-Dribble (agent2d/HELIOS); explora "chute soma velocidade". É o caso seguro do passe-ao-espaço: o passador É o receptor → zero coordenação entre agentes.
- **Implementação:** preencher o gene morto `carry_mode="touch"` em `_carry_target()` (`my_bot.py:379`). Achar o ponto de máximo `nearestOpp` num cone ~±40° rumo ao gol, a `carry_step`, **alcançável por mim antes de qualquer adversário no instante de chegada da bola** (a bola desacelera 10/turno; ponto lento em espaço vazio é interceptável — esse teste protege contra turnover). `geo.kick_to(...)` com `speed_for_distance`; fallback `"hold"`. ~12 pontos × 11 opp/turno.
- **Como testar:** proxy = progressão de `ball.x` por posse + turns-to-arco (muitas amostras/jogo, ruído baixo). Fusível: turnovers no nosso meio-campo.

### 3. Padrão do lado fraco: switch/cruzamento → poste oposto → one-touch  `[ataque | valor: alto | esforço: médio]`
- **O que:** UMA jogada. (i) `_best_pass` floora em `best_score=0.0` (`my_bot.py:311`) → switch lateral pro flanco livre nunca é escolhido; habilitar. (ii) Bola no terço de ataque → promover 1 dos 9 a **campar o poste oposto** (`y≈5000+1500·sign(5000−ball.y)`, `x≈16200`). (iii) Receptor finaliza *one-touch*. O switch vale como **criador de folga**: GK anda 200/turno vs bola 400 → switch rápido + conclusão bate o rastreamento; recirculação por recirculação NÃO move o placar.
- **Teoria:** overload-to-isolate + switch, far-post/cutback receiver.
- **Implementação:** em `_best_pass()` somar `pass_w_switch·max(0,|mate.y−5000|−|me.y−5000|)·[mate no lado oposto da bola]` + `pass_w_space·min(nearestOpp(target),1700)/1700`; baixar o piso de 0.0 para aceitar passe seguro de alto ganho de folga; clamp `target.x` (nunca pra trás). Em `on_supporting()` (`my_bot.py:100`), com `ball_advance_frac>~0.6`, reservar 1 "far-post mover" por *nearest-to-anchor* (todos calculam o mesmo → sem conflito). **Cap defensivo rígido: máx. 3 à frente da bola; recolhem no turno da perda** — protege o zero sofrido (item mais arriscado).
- **Como testar:** proxy = slack do far-post mover quando o portador chuta/cruza; logar `gk.y` antes/depois do switch (prova causal). A/B pareado ~30 jogos. Fusível: "jogadores à frente da bola no turnover".

### 4. Nº de chasers adaptativo com histerese  `[meio/defesa | valor: médio | esforço: baixo]`
- **O que:** sempre 2 hoje. Usar `we_are_closest()` (`tactics.py:108`, nunca chamada): **1** quando ganhamos a bola com folga (libera o 2º corpo pro far-post/apoio — sinergia com a jogada 3), **2** quando disputado. Histerese p/ não trocar papel a cada turno.
- **Teoria:** pressing como escalar (Gliders v1.2); atribuição por TTB.
- **Implementação:** em `tactics.chasers()` (`tactics.py:95`) tornar `n` função de `we_are_closest()` e da margem `best_theirs−best_mine`; banda de histerese (`chase_hysteresis`). **Risco:** estimativa ruidosa de "quem é o mais perto" pode largar a bola → o fusível screen-breach é obrigatório aqui.
- **Como testar:** turns-to-recover (50-150 amostras/jogo) + turnos com 2 nossos na mesma bola. Fusível: screen-breach.

---

## Longo prazo (depois das quartas, ou se a proxy mostrar teto)

- **Mini chain-action de 1 ply + field evaluator** `[ataque | alto | alto]` — substituir a ordem fixa (`holding_order`, morto) por enumerar {chutar N miras}∪{passar a cada mate}∪{tocar K pontos}, simular (física determinística) e escolher pelo maior avaliador `w1·(6000−d_gol)+ + w2·slack + w3·raio_livre − w4/passos_adv`. **Subsome** os itens 1-3 (viram geradores) → vem depois. Não é RL (avaliador de pesos fixos sobre simulação). `on_holding()`, <20 avaliações O(1)/turno.
- **Largura no ataque por papel (SBSP-lite)** `[meio | médio | médio]` — `SHIFT_Y` comprime lateralmente sempre; abrir largura atacando (inverter sinal em fase de ataque) para esticar defesa+goleiro, deslize por papel. `formation_position()` (`tactics.py:60`) + separação (repulsão ~1700d) sobre os 9.
- **Contrapressão em janela** `[defesa | médio | médio]` — no turno da perda, 2-3 de menor TTB pressionam ~20-30 turnos mirando o corte do 1º passe; senão caem na forma. Valor é ofensivo (recuperar alto). Trava anti-supercompromisso como fusível.
- **Marcação individual top-k (OMAM-lite)** `[defesa | baixo-vs-level-1 | médio]` — HEDGE maximin p/ adversários mais fortes; vs level-1 sofremos ~0 (sem sinal). `_cover_position()` (`my_bot.py:429`), matching guloso determinístico.
- **Tuning por coordinate-ascent na proxy** `[tuning | alto | baixo-médio]` — tunar os genes novos (`shot_min_slack`, `w_onetouch`, `pass_w_switch`, `carry_step`, espaçamento) sobre a proxy densa com CRN. **Coordinate-ascent/Hooke-Jeeves basta** p/ ~5 params; CMA-ES é overkill. Seleção final por **maximin** em round-robin vs painel (level-1 + v1…v9), não pela média.

---

## Sequência recomendada até as quartas

1. **Harness de proxy + CRN pareado + guard on-target + fusível screen-breach** (§2). Gargalo de tudo; nada abaixo é confiável sem isto.
2. **Gate de chute por folga temporal + one-touch** (`_best_shot_target`). Menor esforço, ataca o driver nº 1, mensurável na hora.
3. **Condução de toque** (`carry_mode="touch"`). Slot pronto, maior ganho de progressão, teste de baixo ruído.
4. **Padrão do lado fraco** (switch + far-post + one-touch). Converte 2-3 em gols; cap defensivo e recolhimento na perda protegem o zero.
5. **Nº de chasers adaptativo** (`chasers`/`we_are_closest`). Libera o corpo que a jogada 4 precisa; screen-breach obrigatório.
6. **Coordinate-ascent na proxy** dos genes de 2-5 + seleção maximin; **só então** confirmar o pacote campeão em gols (~50-70 jogos pareados, checando Δproxy⇒Δgol).

**Cortado/rebaixado:** passe-em-profundidade em time (coordenação frágil → virou self-pass); ocupação de rebote (raro, ruidoso → sub-nota do far-post); marcação individual e consciência de placar (vs level-1 sem sinal → hedge/longo prazo); CMA-ES (coordinate-ascent basta).

---

## Resultados da execução autônoma (ago/2026)

### O que foi implementado (todos como GENE, default = v9 — nunca regride)
- **Item 1 — harness de proxy densa** (`bench/proxy_metric.py`, `gen_replays.sh`): folga temporal
  do goleiro por chance, `gk_reach_speed=75` calibrado (AUC 0,87 vs gol). É o selecionador de
  baixo ruído usado em tudo abaixo. **Entregue e validado.**
- **Item 2 — gate de chute por folga temporal** (`shot_gate="slack"`): neutro em gols vs o gate
  empírico da v9. A v9 já estava bem calibrada aqui. Fica como gene.
- **Item 3 — condução de toque** (`carry_mode="touch"`): **o ganho real.** Ver funil abaixo.
- **Item 4 — switch/lado fraco** (`pass_w_switch`): **piorou** (cancela o ganho do touch). Cortado.
- **Item 5 — chasers adaptativo** (`chase_mode="adaptive"`, `tactics.adaptive_chasers`): sinal
  positivo consistente na proxy (perigo adversário ↓, taxa de chance ↑). Em confirmação.
- **Item 6 — tuning `carry_step`** (bracket 1900/2200/2600): ganho do round-1 (n20) **regrediu**
  no round-2 (n24); 2600 piorou a taxa de chance. Sem base para mexer no default 1500 (winner's
  curse evitado).

### Funil de criação de chance (proxy densa, por jogo)
| config | danger_poss | taxa good_chance (2→3) | conv_boa (finalização) | gols(ruído) |
|---|---|---|---|---|
| v9 | 5,5 | 0,40 | 0,34 | 0,75 |
| touch | 6,7 (**+22%**) | 0,42 | 0,37 | 1,04 |
| touch+adaptive | 7,0 | 0,45 | 0,37 | 1,15 |

**Mecanismo do touch:** melhora **levando a bola à zona mais vezes** (+22% de posses-perigo),
não a conversão de cada posse. A taxa 2→3 (~0,42) e a finalização (~0,37) são tetos estáveis
(coerente com o xG não ter batido a heurística).

### Próximo gargalo (trabalho futuro, ofensivo)
A taxa **good_chance/danger ≈ 0,42** é o teto: 58% das posses que chegam a ≤6000d têm o goleiro
cobrindo. Melhorar isso exige **fabricar o alvo aberto por movimentação sem bola** — o item 4
(switch lateral) atacava esse gargalo mas piorou; a alavanca é real, a implementação estava
errada. Tentar **tabela/corredor ao poste (give-and-go)** em vez de troca lateral. A finalização
(conv_boa 0,37) é teto calibrado — não perseguir.

### Confirmação final em gols (v9 vs touch vs touch+adaptive, wait, pareado)
<!-- PREENCHER quando a confirmação b4zjw5iny terminar -->
