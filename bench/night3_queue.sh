#!/usr/bin/env bash
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
V4=$(cat ../bot/genome_v4_candidate.json)
V3=$(cat ../bot/genome_submit.json)
mkdir -p ../results/screen
echo "[$(date +%H:%M)] travas v4k (selfplay vs v4 + sparring)"
$PY ab_selfplay.py --base "$V4" --test '{"shot_gate":"slack","gs_retain_late":"on","gs_draw_ok":"on"}' \
    --tag v4k --reps 8 --parallel 1 > ../results/screen/v4k_selfplay.log 2>&1
$PY ab_transition.py --tag v4ks --base "$V4" --test '{"shot_gate":"slack","gs_retain_late":"on","gs_draw_ok":"on"}' \
    --opp sparring --reps 4 --parallel 2 > ../results/screen/v4k_sparring.log 2>&1
echo "[$(date +%H:%M)] par concluído: travas v4k"
echo "[$(date +%H:%M)] wait top-up da v4 (8+8 adicionais)"
$PY ab_transition.py --tag cw2 --base "$V3" --test '{"finish_mode":"on","second_ball":"on"}' \
    --opp lugobots/level-1:latest --reps 4 --parallel 2 --mode wait \
    > ../results/screen/comp_wait2.log 2>&1
echo "[$(date +%H:%M)] par concluído: wait top-up"
echo "NOITE3_CONCLUIDA $(date +%H:%M)"
