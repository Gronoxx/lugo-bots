#!/usr/bin/env bash
# Fila v6 ENXUTA (pós-corte do cb_stagger no S3): compósito = v4 + hybrid + ot_relief.
# S1/S2 (hybrid solo) já rodaram; aqui só as travas compostas C1-C3.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python

V4='{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on","cover_mode":"on","gk_outlet":"on","gk_jump_mode":"strict","finish_mode":"on","second_ball":"on"}'
V6EXTRA='{"shot_gate":"hybrid","ot_gate_relief":260}'
L1=lugobots/level-1:latest

echo "=== v6b_queue $(date '+%F %T') ==="

# C1 — selfplay v6 vs v4 (trava: sem desastre <=-0.5 z>=2)
$PY ab_selfplay.py --reps 16 --parallel 2 --tag v6bsp \
  --base "$V4" --test "$V6EXTRA" > v6b_c1_selfplay.log 2>&1
echo "C1 done $(date '+%T')"

# C2 — v6 vs sparring (genoma EXATO da plataforma)
$PY ab_transition.py --tag v6bfull_sp --reps 8 --parallel 2 --opp sparring \
  --base "$V4" --test "$V6EXTRA" --mode rush > v6b_c2_full_sp.log 2>&1
echo "C2 done $(date '+%T')"

# C3 — v6 WAIT vs level-1 (timer real da plataforma; o teste decisivo do gf)
$PY ab_transition.py --tag v6bfull_l1w --reps 8 --parallel 2 --opp "$L1" \
  --base "$V4" --test "$V6EXTRA" --mode wait > v6b_c3_full_l1w.log 2>&1
echo "C3 done $(date '+%T')"

echo "=== v6b_queue FIM $(date '+%F %T') ==="
