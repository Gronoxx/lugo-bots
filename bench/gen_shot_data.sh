#!/usr/bin/env bash
# Gera N replays de mybot:v9 vs level-1 (rush, paralelo) e OS MANTÉM para
# extrair chutes rotulados (o modelo de finalização precisa ser treinado no
# adversário e na arquitetura reais: level-1, amd64 — não no dado antigo do Mac).
#
# O nome do replay codifica o lado do NOSSO bot (home/away) para a extração
# saber qual time é o nosso.
#   ./gen_shot_data.sh [N=40] [opp=lugobots/level-1:latest] [parallel=3]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
N="${1:-40}"; OPP="${2:-lugobots/level-1:latest}"; PARALLEL="${3:-3}"
mkdir -p recordings

run_one() {
  local i="$1" side h a id
  if [ $((i % 2)) -eq 0 ]; then side=home; h="mybot:v9"; a="$OPP"; else side=away; h="$OPP"; a="mybot:v9"; fi
  id="fin_$(printf '%03d' "$i")_${side}"
  # run_match.sh MANTÉM o replay (recordings/${id}.json); só remove o compose
  TIMER_MODE=rush ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1 || echo "  $id FALHOU" >&2
  echo "  $id"
}

echo "gerando $N replays vs $OPP (parallel $PARALLEL)..."
for i in $(seq 1 "$N"); do
  run_one "$i" &
  while [ "$(jobs -r | wc -l)" -ge "$PARALLEL" ]; do wait -n; done
done
wait
echo "pronto: $(ls recordings/fin_*.json 2>/dev/null | wc -l) replays em recordings/fin_*.json"
