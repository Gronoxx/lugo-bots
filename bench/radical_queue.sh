#!/usr/bin/env bash
# FILA RADICAL (20/08) — alvo declarado do usuário: SALDO +10 (o teto do
# knockout). Escada de agressividade sobre a v11 (v6 + def_camp + outlet_risk),
# que já mede 2,83 gols vs 1,33 da v6. Cada degrau ACUMULA o anterior.
#
# R1 3 acampados mais altos           R4 + pressão (3 chasers, counterpress)
# R2 + 2 meias acampados (forma 4-6)  R5 + fábrica de rebote e largura
# R3 + linha inteira alta (4-6 real)  R6 = R5 com portão de VOLUME (level-2)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/.."
N=${N:-6}; PAR=${PAR:-4}
mkdir -p results/screen bot/tmp

acc='{}'
run () {
  local name="$1"; local extra="$2"
  acc=$(python3 -c "
import json,sys
a=json.loads(sys.argv[1]); a.update(json.loads(sys.argv[2])); print(json.dumps(a))
" "$acc" "$extra")
  python3 -c "
import json,sys
b=json.load(open('bot/genome_v11_l3.json')); b.update(json.loads(sys.argv[1]))
print(json.dumps(b))
" "$acc" > "bot/tmp/r_$name.json"
  echo "=== $name : $acc"
  python3 bench/escada.py --genome "bot/tmp/r_$name.json" --tag "r_$name" \
      --n "$N" --parallel "$PAR" --mode ${MODE:-rush} --knockout 99 \
      > "results/screen/rad_$name.log" 2>&1
  tail -5 "results/screen/rad_$name.log"
}

run r1 '{"dc_count":3,"dc_floor":0.62}'
run r2 '{"dc_count":5,"dc_floor_mid":0.50,"aggression_support":1.2}'
run r3 '{"dc_count":6,"aggression_defend":0.0,"cover_mix":0.15,"shift_x":0.5}'
run r4 '{"n_chasers":3,"counterpress":"on","cp_extra":2,"pressure_radius":4000}'
run r5 '{"swarm_rebound":"on","sw_count":3,"rebound_crash":"on","far_post_run":"on","attack_width":"on","attack_width_shift":-0.2,"pass_w_advance":2.5}'
run r6 '{"shot_gate":"threshold","dangerous_shot_range":7500,"shot_min_gap":800}'
