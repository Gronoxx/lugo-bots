#!/usr/bin/env bash
# Gera N replays de mybot:v9 (com genoma opcional via BOT_PARAMS) vs OPP e OS
# MANTÉM, para avaliar uma variante pela proxy densa (proxy_metric.py).
# Alterna lados; o nome codifica o lado do NOSSO bot: <tag>_NNN_<side>.json.
#   ./gen_replays.sh <N> <opp> <parallel> '<genome_json_compacto>' <tag>
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
N="${1:-30}"; OPP="${2:-lugobots/level-1:latest}"; PARALLEL="${3:-3}"
# NAO usar ${4:-{}} — o bash mal-parseia e anexa um '}' extra, corrompendo o JSON.
GENOME="${4:-}"; [ -z "$GENOME" ] && GENOME='{}'
TAG="${5:-gen}"
mkdir -p recordings

run_one() {
  local i="$1" side h a id
  if [ $((i % 2)) -eq 0 ]; then
    side=home; h="mybot:v9"; a="$OPP"; export HOME_PARAMS="$GENOME"; unset AWAY_PARAMS
  else
    side=away; h="$OPP"; a="mybot:v9"; export AWAY_PARAMS="$GENOME"; unset HOME_PARAMS
  fi
  id="${TAG}_$(printf '%03d' "$i")_${side}"
  TIMER_MODE=rush ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1 || echo "  $id FALHOU" >&2
}

echo "gerando $N replays da variante '$TAG' (genoma=$GENOME) vs $OPP..."
for i in $(seq 1 "$N"); do
  run_one "$i" &
  while [ "$(jobs -r | wc -l)" -ge "$PARALLEL" ]; do wait -n; done
done
wait
echo "pronto: $(ls recordings/${TAG}_*.json 2>/dev/null | wc -l) replays recordings/${TAG}_*.json"
