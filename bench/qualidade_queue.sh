#!/usr/bin/env bash
# qualidade_queue.sh — DEGRAU 1 DA ESCADA (10 gols vs level-1).
# Lição do G3: subir a agressividade além da v8 dá +20% de chutes e ZERO gols
# (conversão 32%->27%). O gargalo virou QUALIDADE da chance, não volume.
# Hipótese: chegamos perto o bastante? A v8 faz 8,6 chutes/jogo com 235 passes
# — ainda circulamos muito e o portador é cercado (o level-1 persegue em bando).
# Estes testes atacam a PENETRAÇÃO (chegar perto) em vez do volume.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V8=$(cat ../bot/genome_v8_candidate.json)

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 20

# I1 — TOQUE PRO ESPAÇO: progredir por self-pass em vez de conduzir. A bola é
#      4x mais rápida que o jogador; contra bot que persegue em bando (level-1
#      roubou 137 bolas de nós no oficial) conduzir é entregar.
$PY ab_transition.py --tag i1_touch --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V8" --test '{"carry_mode":"touch"}' --mode rush \
  > ../results/screen/i1_touch.log 2>&1

# I2 — HIERARQUIA DE CASOS: decisão por área de condução segura (passe p/ frente
#      a receptor desmarcado > rota segura ao gol > escape).
$PY ab_transition.py --tag i2_caso --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V8" --test '{"hold_logic":"caso"}' --mode rush \
  > ../results/screen/i2_caso.log 2>&1

# I3 — CHUTE SÓ COM POTÊNCIA DE CHEGADA: piso na velocidade real de chegada
#      (mata o chute fraco que o GK segura) + ângulo lateral antes de finalizar.
$PY ab_transition.py --tag i3_qual --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V8" --test '{"shot_arrival_min":200,"angle_seek":"on"}' --mode rush \
  > ../results/screen/i3_qual.log 2>&1

echo "qualidade_queue: I1+I2+I3 concluídos $(date '+%H:%M:%S')"
