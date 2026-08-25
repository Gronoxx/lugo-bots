#!/usr/bin/env bash
# Onda 2 de screenings: COMBOS interligados (lição da onda 1: genes de escape
# só fazem sentido juntos) + retestes de redesigns. Sparring agora com press
# de 4 (fidelidade ao BotAdversario1). Logs em results/screen/<tag>.log.
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
mkdir -p ../results/screen

run2() {
  echo "[$(date +%H:%M)] par: $1 + $3"
  $PY ab_transition.py --tag "$1" --test "$2" --opp sparring --reps 6 --parallel 2 \
      > "../results/screen/$1.log" 2>&1 &
  local P1=$!
  $PY ab_transition.py --tag "$3" --test "$4" --opp sparring --reps 6 --parallel 2 \
      > "../results/screen/$3.log" 2>&1 &
  local P2=$!
  wait $P1 $P2
  echo "[$(date +%H:%M)] par concluído: $1 + $3"
}

# combo de ESCAPE interligado (A2 filtra + gko/A4 criam válvulas + zona aceita)
run2 w2combo '{"pass_veto_mode":"turnwise","gk_outlet":"on","def_outlet":"on","zone_escape":"on","pass_min_score_defthird":-600,"pass_min_dist_danger":450}' \
     w2pdef  '{"cover_states":"all","disputing_mode":"defend","gk_jump_mode":"strict","gk_collect":"on","gk_clear_mode":"safe"}'
# rebote ofensivo (gate + crashers JUNTOS) e carry_gate v2 (redesenho)
run2 w2reb   '{"shot_min_gap":1000,"rebound_crash":"on"}' \
     w2carry '{"carry_gate":"on"}'

echo "ONDA2_CONCLUIDA $(date +%H:%M)"
