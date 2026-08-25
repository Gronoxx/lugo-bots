#!/usr/bin/env bash
# Fila noturna P2→P3→P4 (screenings da barra nova; base = v3).
# Pares de 2 experimentos simultâneos (parallel 2 cada). Logs em results/screen/.
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
V3=$(cat ../bot/genome_submit.json)
mkdir -p ../results/screen

run2() {
  echo "[$(date +%H:%M)] par: $1 + $3"
  $PY ab_transition.py --tag "$1" --base "$V3" --test "$2" --opp "$5" \
      --reps 8 --parallel 2 > "../results/screen/$1.log" 2>&1 &
  local A=$!
  $PY ab_transition.py --tag "$3" --base "$V3" --test "$4" --opp "$6" \
      --reps 8 --parallel 2 > "../results/screen/$3.log" 2>&1 &
  local B=$!
  wait $A $B
  echo "[$(date +%H:%M)] par concluído: $1 + $3"
}

# P2: pacote kickoff vs sparring (reinícios densos: ~5-9/jogo) e vs level-1
run2 p2s '{"init_variant":"kick9","kickoff_play":"on"}' \
     p2l '{"init_variant":"kick9","kickoff_play":"on"}' \
     sparring lugobots/level-1:latest
# P3: segunda bola (level-1: ~10 chutes/jogo = denso) e largura+far_post
run2 p3sb '{"second_ball":"on"}' \
     p3w  '{"attack_width":"on","attack_width_shift":-0.2,"far_post_run":"on"}' \
     lugobots/level-1:latest lugobots/level-1:latest
# P4: contrapressão vs sparring (transições densas) e piso de profundidade
run2 p4cp '{"counterpress":"on"}' \
     p4dd '{"def_min_depth":1700}' \
     sparring sparring

echo "P234_QUEUE_CONCLUIDA $(date +%H:%M)"
