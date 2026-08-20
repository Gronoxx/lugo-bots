#!/usr/bin/env bash
# SWEEP a partir do r3 (forma 4-6: 5,38 gols, 0,44 sofridos, 12,8 chances
# curtas por jogo vs level-1, 16V/0E/0D). NAO acumulativo: cada braco e
# r3 + UMA ideia, para nenhum braco herdar o dano de outro (o r4 da escada
# anterior piorou e teria contaminado r5/r6).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/.."
N=${N:-6}; PAR=${PAR:-6}; MODE=${MODE:-rush}
mkdir -p results/screen bot/tmp

run () {
  local name="$1"; local extra="$2"
  python3 -c "
import json,sys
b=json.load(open('bot/tmp/r_r3.json')); b.update(json.loads(sys.argv[1])); print(json.dumps(b))
" "$extra" > "bot/tmp/s_$name.json"
  echo "=== $name : $extra"
  python3 bench/escada.py --genome "bot/tmp/s_$name.json" --tag "s_$name" \
      --n "$N" --parallel "$PAR" --mode "$MODE" --knockout 99 \
      > "results/screen/sw_$name.log" 2>&1
  grep -E "^GOLS:|^SOFRIDOS:|^FINALIZ" "results/screen/sw_$name.log" || true
}

run s1 '{"swarm_rebound":"on","sw_count":3,"rebound_crash":"on","far_post_run":"on"}'
run s2 '{"aggression_defend":0.4,"cover_mix":0.0}'
run s3 '{"dc_floor":0.70,"dc_floor_mid":0.58,"shift_x":0.65}'
run s4 '{"pass_w_advance":2.5,"attack_width":"on","attack_width_shift":-0.2}'
run s5 '{"shot_gate":"threshold","dangerous_shot_range":7500,"shot_min_gap":800}'
