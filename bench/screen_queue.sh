#!/usr/bin/env bash
# Fila de SCREENINGS rush vs sparring (pós 0-3 BotAdversario1). 2 experimentos
# simultâneos (parallel 2 cada => 4 partidas em voo), pares sequenciais.
# Logs em results/screen/<tag>.log. Cada experimento: 6 reps x 2 lados x 2
# braços = 24 partidas.
set -u
PY=<caminho local>
cd "$(dirname "$0")"
mkdir -p ../results/screen

V2='{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on","cover_mode":"on"}'

run2() {  # tag1 test1 tag2 test2
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

# C0 — sonda do goleiro (1 partida rush vs level-1; gene gk_probe NUNCA submeter)
TIMER_MODE=rush HOME_PARAMS="${V2%\}},\"gk_probe\":\"on\"}" \
  ./run_match.sh mybot:qp lugobots/level-1:latest gkprobe \
  > ../results/screen/gkprobe.log 2>&1 || echo "gkprobe FALHOU"

run2 a1  '{"carry_gate":"on"}' \
     a2  '{"pass_veto_mode":"turnwise"}'
run2 a31 '{"status_danger_turns":3.5,"status_attention_turns":6.0}' \
     a34 '{"zone_escape":"on","pass_min_score_defthird":-1500,"pass_min_dist_danger":450}'
run2 gko '{"gk_outlet":"on"}' \
     b1  '{"cover_states":"all"}'
run2 f1  '{"disputing_mode":"defend"}' \
     c1  '{"gk_collect":"on"}'
run2 c2  '{"gk_jump_mode":"strict"}' \
     c4  '{"gk_clear_mode":"safe","gk_clear_w_flank":0.5}'
run2 d2  '{"shot_min_gap":1000}' \
     c3  '{"gk_y_range":1350}'

echo "TODOS_SCREENINGS_CONCLUIDOS $(date +%H:%M)"
