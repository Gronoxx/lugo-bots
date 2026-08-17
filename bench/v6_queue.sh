#!/usr/bin/env bash
# Fila de validação da v6 (hybrid + cb_stagger) sobre a base v4.
# Sequencial; máx 2 partidas simultâneas (teto de memória 15G).
# Saídas: bench/v6_*.log — cada etapa imprime o resumo A/B ao final.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python

V4='{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on","cover_mode":"on","gk_outlet":"on","gk_jump_mode":"strict","finish_mode":"on","second_ball":"on"}'
L1=lugobots/level-1:latest

echo "=== v6_queue $(date '+%F %T') ==="

# S1 — hybrid vs level-1 (guarda: gf não pode regredir; conversão deve subir)
$PY ab_transition.py --tag v6hyb_l1 --reps 6 --parallel 2 --opp "$L1" \
  --base "$V4" --test '{"shot_gate":"hybrid"}' --mode rush \
  > v6_s1_hyb_l1.log 2>&1
echo "S1 done $(date '+%T')"

# S2 — hybrid vs sparring (qualidade: slack>0 nos chutes longe, volume perto)
$PY ab_transition.py --tag v6hyb_sp --reps 6 --parallel 2 --opp sparring \
  --base "$V4" --test '{"shot_gate":"hybrid"}' --mode rush \
  > v6_s2_hyb_sp.log 2>&1
echo "S2 done $(date '+%T')"

# S3 — cb_stagger vs sparring (alvo: sofridos ↓; press deles reproduz portador-fundo)
$PY ab_transition.py --tag v6cbs_sp --reps 6 --parallel 2 --opp sparring \
  --base "$V4" --test '{"cb_stagger":"on"}' --mode rush \
  > v6_s3_cbs_sp.log 2>&1
echo "S3 done $(date '+%T')"

# S4 — cb_stagger vs level-1 (guarda de não-regressão)
$PY ab_transition.py --tag v6cbs_l1 --reps 4 --parallel 2 --opp "$L1" \
  --base "$V4" --test '{"cb_stagger":"on"}' --mode rush \
  > v6_s4_cbs_l1.log 2>&1
echo "S4 done $(date '+%T')"

# C1 — selfplay compósito v6 vs v4 (trava: sem desastre <=-0.5 z>=2)
$PY ab_selfplay.py --reps 16 --parallel 2 --tag v6sp \
  --base "$V4" --test '{"shot_gate":"hybrid","cb_stagger":"on","ot_gate_relief":260}' \
  > v6_c1_selfplay.log 2>&1
echo "C1 done $(date '+%T')"

# C2 — compósito vs sparring (genoma EXATO da plataforma)
$PY ab_transition.py --tag v6full_sp --reps 8 --parallel 2 --opp sparring \
  --base "$V4" --test '{"shot_gate":"hybrid","cb_stagger":"on","ot_gate_relief":260}' \
  --mode rush > v6_c2_full_sp.log 2>&1
echo "C2 done $(date '+%T')"

# C3 — compósito WAIT vs level-1 (timer real da plataforma)
$PY ab_transition.py --tag v6full_l1w --reps 8 --parallel 2 --opp "$L1" \
  --base "$V4" --test '{"shot_gate":"hybrid","cb_stagger":"on","ot_gate_relief":260}' \
  --mode wait > v6_c3_full_l1w.log 2>&1
echo "C3 done $(date '+%T')"

echo "=== v6_queue FIM $(date '+%F %T') ==="
