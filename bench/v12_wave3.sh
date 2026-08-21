#!/usr/bin/env bash
# FILA v12 — ONDA 3, a partir do u3 (cascata de reinicio: mediana 7,0,
# media 6,50, SOFRIDOS 0,12, 20,5 finalizacoes — o melhor saldo ate agora).
# Objetivo do usuario: mediana 10.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/.."
BASE=${BASE:-bot/tmp/u_u3.json}
N=${N:-4}; PAR=${PAR:-6}; MODE=${MODE:-rush}
mkdir -p results/screen bot/tmp

run () {
  local name="$1"; local extra="$2"
  python3 -c "
import json,sys
b=json.load(open(sys.argv[1])); b.update(json.loads(sys.argv[2])); print(json.dumps(b))
" "$BASE" "$extra" > "bot/tmp/v_$name.json"
  echo "=== $name : $extra"
  python3 bench/escada.py --genome "bot/tmp/v_$name.json" --tag "v_$name" \
      --n "$N" --parallel "$PAR" --mode "$MODE" --knockout 99 \
      > "results/screen/w3_$name.log" 2>&1
  grep -E "^GOLS:|^SOFRIDOS:|^FINALIZ|^placares" "results/screen/w3_$name.log" || true
}

# v1: a pressao do u4 (2o melhor em media) somada a cascata
run v1 '{"counterpress":"on","cp_extra":2,"n_chasers":3,"pressure_radius":4000}'
# v2: arco de rebote mais apertado + mira mais no poste (conversao)
run v2 '{"sw_radius":1700,"shot_post_margin":120,"srr_per_body":250}'
# v3: passo INTERMEDIARIO rumo aos maximos (o u1 estourou; aqui e' metade)
run v3 '{"aggression_defend":0.8,"dc_floor":0.78,"dc_floor_mid":0.66}'
