#!/usr/bin/env bash
# FILA v12 — ONDA 2. Alvo do usuario: MEDIANA 10, nao maximo 10.
# Base default = t3 (2-8 + linha maxima: 6,00 gols, 0,50 sofridos, mediana 5,5).
# Cada braco e' UM aumento de risco sobre a base (nao acumulativo).
#
# u1 maximos absolutos das faixas (linha e acampamento no teto do BOUNDS)
# u2 fabrica de rebote (enxame + crash + 2o poste + largura)
# u3 CASCATA: pacote de reinicio — com 6 gols/jogo sao 6 kickoffs deles para
#    predar; e assim que o BotAdversario1 faz 10x0 (3x0 nos primeiros 23 segundos)
# u4 pressao alta (contrapressao + 3 chasers) sobre a base radical
# u5 portao um pouco mais largo (hybrid_close_range 4500, gap 800)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/.."
BASE=${BASE:-bot/tmp/t_t3.json}
N=${N:-5}; PAR=${PAR:-6}; MODE=${MODE:-rush}
mkdir -p results/screen bot/tmp

run () {
  local name="$1"; local extra="$2"
  python3 -c "
import json,sys
b=json.load(open(sys.argv[1])); b.update(json.loads(sys.argv[2])); print(json.dumps(b))
" "$BASE" "$extra" > "bot/tmp/u_$name.json"
  echo "=== $name : $extra"
  python3 bench/escada.py --genome "bot/tmp/u_$name.json" --tag "u_$name" \
      --n "$N" --parallel "$PAR" --mode "$MODE" --knockout 99 \
      > "results/screen/w2_$name.log" 2>&1
  grep -E "^GOLS:|^SOFRIDOS:|^FINALIZ|^placares" "results/screen/w2_$name.log" || true
}

run u1 '{"aggression_defend":1.0,"shift_x":0.8,"dc_floor":0.85,"dc_floor_mid":0.75,"dc_floor_def":0.70}'
run u2 '{"swarm_rebound":"on","sw_count":3,"rebound_crash":"on","far_post_run":"on","attack_width":"on","attack_width_shift":-0.2,"pass_w_advance":2.5}'
run u3 '{"init_variant":"race","kickoff_play":"on","kickoff_blitz":"on","kickoff_race":"on","swarm_rebound":"on","sw_count":3}'
run u4 '{"counterpress":"on","cp_extra":2,"n_chasers":3,"pressure_radius":4000}'
run u5 '{"hybrid_close_range":4500,"shot_min_gap":800}'
