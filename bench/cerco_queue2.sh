#!/usr/bin/env bash
# FILA DO CERCO #2 — afinação, sobre o vencedor da fila #1.
# Uso: BASE=bot/tmp/g_v10qc.json N=6 PAR=6 bash bench/cerco_queue2.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
BASE=${BASE:?defina BASE=<genoma.json>}
N=${N:-6}; PAR=${PAR:-6}
mkdir -p results/screen bot/tmp

run () {
  local name="$1"; local extra="$2"
  python3 - "$BASE" "$extra" > "bot/tmp/g2_$name.json" <<'PY'
import json, sys
b = json.load(open(sys.argv[1])); b.update(json.loads(sys.argv[2]))
print(json.dumps(b))
PY
  echo "=== $name : $extra"
  python3 bench/escada.py --genome "bot/tmp/g2_$name.json" --tag "d_$name" \
      --n "$N" --parallel "$PAR" --mode wait --knockout 99 \
      > "results/screen/cerco2_$name.log" 2>&1
  tail -5 "results/screen/cerco2_$name.log"
}

run dc3    '{"dc_count":3}'
run dcf45  '{"dc_floor":0.45}'
run dcf62  '{"dc_floor":0.62}'
run hcr26  '{"hybrid_close_range":2600}'
run orisk1 '{"orisk_minopps":1}'
run orisk3 '{"orisk_minopps":3}'
run chase3 '{"n_chasers":3}'
run cpress '{"counterpress":"on"}'
run press6 '{"n_chasers":3,"pressure_radius":6000}'
