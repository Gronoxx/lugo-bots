#!/usr/bin/env bash
# Estágio 3 da janela autônoma: confirmação em WAIT (modo do campeonato) do
# compósito vencedor + sweeps finos + painel de robustez (maximin).
# Uso: ./stage3_queue.sh '<genes-extra-do-composito-JSON>'
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
V3=$(cat ../bot/genome_submit.json)
COMP="${1:?passar genes do compósito}"
mkdir -p ../results/screen

echo "[$(date +%H:%M)] WAIT: compósito vs level-1 (8+8)"
$PY ab_transition.py --tag cw --base "$V3" --test "$COMP" \
    --opp lugobots/level-1:latest --reps 4 --parallel 2 --mode wait \
    > ../results/screen/comp_wait.log 2>&1
echo "[$(date +%H:%M)] par concluído: wait level-1"

echo "[$(date +%H:%M)] sweeps: finish_sure_slack e sb_dist"
merge() { $PY -c "import json,sys; a=json.loads(sys.argv[1]); a.update(json.loads(sys.argv[2])); print(json.dumps(a,separators=(',',':')))" "$1" "$2"; }
S1=$(merge "$COMP" '{"finish_sure_slack":200}')
S2=$(merge "$COMP" '{"sb_dist":3200}')
$PY ab_transition.py --tag sw1 --base "$V3" --test "$S1" \
    --opp lugobots/level-1:latest --reps 6 --parallel 1 > ../results/screen/sweep_fslack.log 2>&1 &
A=$!
$PY ab_transition.py --tag sw2 --base "$V3" --test "$S2" \
    --opp lugobots/level-1:latest --reps 6 --parallel 1 > ../results/screen/sweep_sbdist.log 2>&1 &
B=$!
wait $A $B
echo "[$(date +%H:%M)] par concluído: sweeps"

echo "[$(date +%H:%M)] painel de robustez (rivais, 2 jogos cada, compósito)"
for opp in rival_p1:latest rival_p3:latest; do
  for side in home away; do
    mid="panel_$(echo $opp | tr -cd 'a-z')_$side"
    if [ "$side" = home ]; then
      TIMER_MODE=rush HOME_PARAMS=$(merge "$V3" "$COMP") ./run_match.sh mybot:qp "$opp" "$mid" >/dev/null 2>&1
    else
      TIMER_MODE=rush AWAY_PARAMS=$(merge "$V3" "$COMP") ./run_match.sh "$opp" mybot:qp "$mid" >/dev/null 2>&1
    fi
  done
done
echo "[$(date +%H:%M)] par concluído: painel rivais"
echo "STAGE3_CONCLUIDA $(date +%H:%M)"
