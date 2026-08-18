#!/usr/bin/env bash
# goleada_queue.sh — MAXIMIZAR GOLS contra DEFESA FORTE (level-2/level-3 no
# oficial). Proxy local: BotAdversario2clone (muralha vertical). base = v8.
# Régua do metamorfo: o cerco do BotAdversario2 fez 51 finalizações de ~12 posses
# porque cada defesa do GK caía onde ele tinha 2-3 corpos.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V6=$(cat ../bot/genome_v6.json)
V8=$(cat ../bot/genome_v8_candidate.json)
V8X=$($PY -c "
import json
v6=json.load(open('../bot/genome_v6.json')); v8=json.load(open('../bot/genome_v8_candidate.json'))
print(json.dumps({k:v for k,v in v8.items() if v6.get(k)!=v}))")

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 30

# H0 — o ganho do v8 sobrevive contra MURALHA? (a pergunta do level-3)
$PY ab_transition.py --tag h0_v8wall --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V6" --test "$V8X" --mode rush > ../results/screen/h0_v8wall.log 2>&1

# H1 — MAIS CORPOS na área (o cerco): 3 no arco + 2º poste + largura
$PY ab_transition.py --tag h1_corpos --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V8" --test '{"sw_count":3,"far_post_run":"on","attack_width":"on","attack_width_shift":-0.2}' \
  --mode rush > ../results/screen/h1_corpos.log 2>&1

# H2 — apoio ATIVO (sustentar o cerco em vez de perder a bola conduzindo)
$PY ab_transition.py --tag h2_offer --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V8" --test '{"support_mode":"offer"}' --mode rush \
  > ../results/screen/h2_offer.log 2>&1

echo "goleada_queue: H0+H1+H2 concluídos $(date '+%H:%M:%S')"
