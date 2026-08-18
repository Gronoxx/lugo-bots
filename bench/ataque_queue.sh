#!/usr/bin/env bash
# ataque_queue.sh — MAXIMIZAR GOLS contra os BOTS OFICIAIS (18/08).
# Contexto: faltam level-2 e level-3 no seeding; desempate = SALDO; os fortes
# fazem 10x0 em todo mundo. Adversário local oficial = level-1 (o único
# disponível; level-2/3 só existem na plataforma).
# base = v8 (defesa v7.4 + goleada G1: 16V/0E, gf 3,12 vs level-1).
# Guarda-corpo: gols sofridos não podem explodir; cenas de BotAdversario1/level-3
# (as que importam no torneio) continuam sendo a régua defensiva.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V8=$(cat ../bot/genome_v8_candidate.json)

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 20

# H1 — MAIS CORPOS na área: 3 no arco de rebote + 2º poste + largura.
#      É o cerco do BotAdversario2 (51 finalizações de ~12 posses: cada defesa do GK
#      cai onde ele tem 2-3 corpos).
$PY ab_transition.py --tag h1_corpos --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V8" --test '{"sw_count":3,"far_post_run":"on","attack_width":"on","attack_width_shift":-0.2}' \
  --mode rush > ../results/screen/h1_corpos.log 2>&1

# H2 — APOIO ATIVO: recebedores sobem oferecendo linha, para sustentar o cerco
#      em vez de perder a bola conduzindo (condução tomada é nossa maior causa).
$PY ab_transition.py --tag h2_offer --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V8" --test '{"support_mode":"offer"}' --mode rush \
  > ../results/screen/h2_offer.log 2>&1

# H3 — CHUTAR DE MAIS LONGE: vs GK fraco (level-1/2) o chute de fora entra.
$PY ab_transition.py --tag h3_longe --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V8" --test '{"dangerous_shot_range":7500,"shot_min_gap":800}' --mode rush \
  > ../results/screen/h3_longe.log 2>&1

echo "ataque_queue: H1+H2+H3 concluídos $(date '+%H:%M:%S')"
