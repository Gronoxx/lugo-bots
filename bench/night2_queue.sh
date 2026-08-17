#!/usr/bin/env bash
# Noite 2 (janela autônoma): sonda sym → solos gk_track + camper_shadow
# (anatomia dos gols do BotAdversario1 v3) → sym-kickoff vs sparring + duelo
# sb_dist 2600×3200 sobre a v4 vs level-1. Máx 2 partidas simultâneas.
set -u
PY=<caminho local>
cd "$(dirname "$0")"
V3=$(cat ../bot/genome_submit.json)
V4=$(cat ../bot/genome_v4_candidate.json)
mkdir -p ../results/screen

echo "[$(date +%H:%M)] sonda init_variant=sym (1 partida)"
SYMG=$($PY -c "import json;g=json.loads('$V3');g['init_variant']='sym';print(json.dumps(g,separators=(',',':')))")
TIMER_MODE=rush HOME_PARAMS="$SYMG" ./run_match.sh mybot:qp lugobots/level-1:latest probe_sym \
  > ../results/screen/probe_sym.log 2>&1 && echo "sonda sym: completou" || echo "sonda sym FALHOU"

par() {  # tag1 test1 opp1 tag2 test2 opp2  (base = V3 salvo 5º arg "V4")
  echo "[$(date +%H:%M)] par: $1 + $4"
  $PY ab_transition.py --tag "$1" --base "$V3" --test "$2" --opp "$3" \
      --reps 8 --parallel 1 > "../results/screen/$1.log" 2>&1 &
  local A=$!
  local BASE2="$V3"; [ "${7:-}" = "V4" ] && BASE2="$V4"
  $PY ab_transition.py --tag "$4" --base "$BASE2" --test "$5" --opp "$6" \
      --reps 8 --parallel 1 > "../results/screen/$4.log" 2>&1 &
  local B=$!
  wait $A $B
  echo "[$(date +%H:%M)] par concluído: $1 + $4"
}

par gktrk '{"gk_guard_mode":"track"}' sparring \
    cshad '{"camper_shadow":"on"}'    sparring
par syms  '{"init_variant":"sym","kickoff_play":"on"}' sparring \
    sbduel '{"sb_dist":3200}' lugobots/level-1:latest V4

echo "NOITE2_CONCLUIDA $(date +%H:%M)"
