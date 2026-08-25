#!/usr/bin/env bash
# P1 — finalização na régua certa (GK externo = level-1). 3 A/Bs, base = v3.
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
V3=$(cat ../bot/genome_submit.json)
mkdir -p ../results/screen
echo "[$(date +%H:%M)] par: p1f + p1s"
$PY ab_transition.py --tag p1f --base "$V3" --test '{"finish_mode":"on"}' \
    --opp lugobots/level-1:latest --reps 8 --parallel 2 > ../results/screen/p1f.log 2>&1 &
P1=$!
$PY ab_transition.py --tag p1s --base "$V3" --test '{"shot_gate":"slack"}' \
    --opp lugobots/level-1:latest --reps 8 --parallel 2 > ../results/screen/p1s.log 2>&1 &
P2=$!
wait $P1 $P2
echo "[$(date +%H:%M)] par concluído: p1f + p1s"
$PY ab_transition.py --tag p1c --base "$V3" --test '{"finish_mode":"on","shot_gate":"slack"}' \
    --opp lugobots/level-1:latest --reps 8 --parallel 4 > ../results/screen/p1c.log 2>&1
echo "[$(date +%H:%M)] par concluído: p1c"
echo "P1_QUEUE_CONCLUIDA $(date +%H:%M)"
