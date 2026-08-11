#!/usr/bin/env bash
# Avalia UM genoma para o evolve.py: roda REPS*2 partidas (os dois lados) do
# nosso bot (BOT_PARAMS=genoma) contra OPP, em paralelo, e imprime um saldo de
# gols (pró-contra, do nosso ponto de vista) por linha no stdout.
#
# Reusa o padrão de paralelismo bash já comprovado (sweep.sh/compare.sh) em vez
# de threads do Python + subprocess, que se mostraram instáveis com docker.
#
#   ./eval_genome.sh '<json_compacto>' <reps> <opp> <mode> <parallel> <tag>
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"

GENOME="$1"; REPS="$2"; OPP="$3"; MODE="$4"; PARALLEL="$5"; TAG="$6"
PARTDIR=$(mktemp -d "recordings/.eval_${TAG}_XXXXXX")

run_one() {
  local side="$1" rep="$2"
  local id="ev_${TAG}_${side}_${rep}" h a sc hg ag saldo
  if [ "$side" = home ]; then
    h="mybot:v9"; a="$OPP"; export HOME_PARAMS="$GENOME"; unset AWAY_PARAMS
  else
    h="$OPP"; a="mybot:v9"; export AWAY_PARAMS="$GENOME"; unset HOME_PARAMS
  fi
  if ! TIMER_MODE="$MODE" ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1; then
    return
  fi
  sc=$(python3 match_done.py "recordings/${id}.json" 2>/dev/null)
  hg=$(echo "$sc" | awk '{print $1}'); ag=$(echo "$sc" | awk '{print $3}')
  if [ -n "$hg" ] && [ -n "$ag" ]; then
    if [ "$side" = home ]; then saldo=$((hg - ag)); else saldo=$((ag - hg)); fi
    echo "$saldo" > "$PARTDIR/$id"
  fi
  rm -f "recordings/${id}.json"
}

for rep in $(seq 1 "$REPS"); do
  for side in home away; do
    run_one "$side" "$rep" &
    while [ "$(jobs -r | wc -l)" -ge "$PARALLEL" ]; do wait -n; done
  done
done
wait

cat "$PARTDIR"/* 2>/dev/null
rm -rf "$PARTDIR"
