#!/usr/bin/env bash
# Estágio 2 da janela autônoma: COMPÓSITOS (a lição da composição manda validar
# o pacote junto). comp_a = v3+finish+second_ball; comp_b = comp_a+kickoff.
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
V3=$(cat ../bot/genome_submit.json)
CA='{"finish_mode":"on","second_ball":"on"}'
CB='{"finish_mode":"on","second_ball":"on","init_variant":"kick9","kickoff_play":"on"}'
mkdir -p ../results/screen

echo "[$(date +%H:%M)] par: compa_l1 + compb_l1"
$PY ab_transition.py --tag compa --base "$V3" --test "$CA" \
    --opp lugobots/level-1:latest --reps 8 --parallel 2 > ../results/screen/compa.log 2>&1 &
A=$!
$PY ab_transition.py --tag compb --base "$V3" --test "$CB" \
    --opp lugobots/level-1:latest --reps 8 --parallel 2 > ../results/screen/compb.log 2>&1 &
B=$!
wait $A $B
echo "[$(date +%H:%M)] par concluído: compa_l1 + compb_l1"

echo "[$(date +%H:%M)] par: compb_spar + trava selfplay compb"
$PY ab_transition.py --tag compbs --base "$V3" --test "$CB" \
    --opp sparring --reps 4 --parallel 2 > ../results/screen/compb_sparring.log 2>&1 &
A=$!
$PY ab_selfplay.py --base "$V3" --test "$CB" --tag cb --reps 8 \
    --parallel 2 > ../results/screen/compb_selfplay.log 2>&1 &
B=$!
wait $A $B
echo "[$(date +%H:%M)] par concluído: compb_spar + selfplay"
echo "COMP_QUEUE_CONCLUIDA $(date +%H:%M)"
