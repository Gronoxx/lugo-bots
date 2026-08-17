#!/usr/bin/env bash
# Travas do PKT-1 (finish_mode) + fila noturna P2→P3→P4.
set -u
PY=<caminho local>
cd "$(dirname "$0")"
V3=$(cat ../bot/genome_submit.json)
mkdir -p ../results/screen

echo "[$(date +%H:%M)] travas PKT-1 (finish_mode)"
$PY ab_selfplay.py --base "$V3" --test '{"finish_mode":"on"}' --tag tf --reps 8 \
    --parallel 2 > ../results/screen/trava_finish_selfplay.log 2>&1 &
A=$!
$PY ab_transition.py --tag tfs --base "$V3" --test '{"finish_mode":"on"}' \
    --opp sparring --reps 4 --parallel 2 > ../results/screen/trava_finish_sparring.log 2>&1 &
B=$!
wait $A $B
echo "[$(date +%H:%M)] par concluído: travas PKT-1"

./p234_queue.sh
echo "NOITE_CONCLUIDA $(date +%H:%M)"
