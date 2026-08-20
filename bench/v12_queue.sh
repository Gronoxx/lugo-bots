#!/usr/bin/env bash
# FILA v12 — RADICAL. Alvo do usuario: saldo +10 (teto do knockout).
# Base = r3 (forma 4-6: 5,38 gols, 0,44 sofridos, 16V/0E/0D vs level-1).
#
# t1  "2-8" LITERAL: 8 acampados, sobram 2 zagueiros + goleiro (BotAdversario2 faz
#     12x2 e 10x0 nos oficiais com esse desenho; ele ACEITA tomar gol).
# t2  linha inteira no maximo: agressividade, sem recuo rumo ao gol, deslize
#     maximo com a bola.
# t3  t1 + t2 (o extremo do desenho).
# t4  t3 + fabrica de rebote e largura.
# t5  t4 com portao de VOLUME — a variante para o level-2 (GK dele salva 35-47%).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/.."
N=${N:-6}; PAR=${PAR:-6}; MODE=${MODE:-rush}
mkdir -p results/screen bot/tmp

MAXLINE='{"aggression_defend":0.6,"cover_mix":0.0,"shift_x":0.7,"aggression_support":1.5}'
DOISOITO='{"dc_count":8,"dc_floor_def":0.40,"dc_floor":0.70,"dc_floor_mid":0.58}'
SWARM='{"swarm_rebound":"on","sw_count":3,"rebound_crash":"on","far_post_run":"on","attack_width":"on","attack_width_shift":-0.2,"pass_w_advance":2.5}'
VOLUME='{"shot_gate":"threshold","dangerous_shot_range":7500,"shot_min_gap":800}'

run () {
  local name="$1"; shift
  python3 -c "
import json,sys
b=json.load(open('bot/tmp/r_r3.json'))
for a in sys.argv[1:]: b.update(json.loads(a))
print(json.dumps(b))
" "$@" > "bot/tmp/t_$name.json"
  echo "=== $name : $(cat bot/tmp/t_$name.json)"
  python3 bench/escada.py --genome "bot/tmp/t_$name.json" --tag "t_$name" \
      --n "$N" --parallel "$PAR" --mode "$MODE" --knockout 99 \
      > "results/screen/v12_$name.log" 2>&1
  grep -E "^GOLS:|^SOFRIDOS:|^FINALIZ|^placares" "results/screen/v12_$name.log" || true
}

run t1 "$DOISOITO"
run t3 "$DOISOITO" "$MAXLINE"
run t4 "$DOISOITO" "$MAXLINE" "$SWARM"
run t5 "$DOISOITO" "$MAXLINE" "$SWARM" "$VOLUME"
