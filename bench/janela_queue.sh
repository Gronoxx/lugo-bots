#!/usr/bin/env bash
# janela_queue.sh — DEGRAU 1: transformar cerco em finalização.
# Autópsia (bench/shot_veto.py): 404 turnos/jogo em alcance de chute, mas só
# 3,2% viram chute; 80% dos vetos são LINHA BLOQUEADA e 0,0% é folga do
# goleiro. Precisamos de 40 chutes/jogo (temos 14) p/ chegar a 10 gols a 25%.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V10=$(cat ../bot/genome_v10_candidate.json)

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 20

# M1 — passar para quem já tem a linha limpa (dose média)
$PY ab_transition.py --tag m1_shooter --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V10" --test '{"pass_w_shooter":2000}' --mode rush \
  > ../results/screen/m1_shooter.log 2>&1

# M2 — janela + passe-para-atirador juntos (o par que multiplica o ciclo)
$PY ab_transition.py --tag m2_janela --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V10" --test '{"lane_seek":"on","pass_w_shooter":2000}' --mode rush \
  > ../results/screen/m2_janela.log 2>&1

# M3 — empurrar a bola ainda mais p/ frente (83,7% dos turnos estão fora de
#      alcance: o pool de chances começa em CHEGAR)
$PY ab_transition.py --tag m3_avanco --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V10" --test '{"pass_w_advance":4.0}' --mode rush \
  > ../results/screen/m3_avanco.log 2>&1

echo "janela_queue: M1+M2+M3 concluídos $(date '+%H:%M:%S')"
