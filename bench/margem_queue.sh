#!/usr/bin/env bash
# margem_queue.sh — SWEEP DE MARGEM (18/08): abrir volume de finalização SEM
# piorar a defesa. base = v7.4 (cenas 130/130); adversário = BotAdversario2clone
# (muralha vertical = melhor proxy local de defesa forte tipo level-3).
# Espera a fila anterior liberar (máx 2 partidas simultâneas / 15G RAM).
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V74=$(cat ../bot/genome_v74_candidate.json)

# aguarda o teto de memória liberar
while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 30

# M1 — alívio do gate por corpo no arco (a economia do cerco)
$PY ab_transition.py --tag m1_srr300 --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V74" --test '{"srr_per_body":300}' --mode rush \
  > ../results/screen/margem_m1_srr300.log 2>&1

# M2 — idem + corpo no 2º poste (mais um rebatedor na área)
$PY ab_transition.py --tag m2_srrfp --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V74" --test '{"srr_per_body":300,"far_post_run":"on"}' --mode rush \
  > ../results/screen/margem_m2_srrfp.log 2>&1

# M3 — versão crua: gate threshold da v4 (volume máximo) + swarm
$PY ab_transition.py --tag m3_thresh --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V74" --test '{"shot_gate":"threshold"}' --mode rush \
  > ../results/screen/margem_m3_thresh.log 2>&1

echo "margem_queue: M1+M2+M3 concluídos $(date '+%H:%M:%S')"
