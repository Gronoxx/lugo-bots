#!/usr/bin/env bash
# margem2_queue.sh — SWEEP DE MARGEM #2: recuperar as posses que a v7.4 perde
# conduzindo no MEIO (condução tomada 240→334 vs v6 no C3, +39%).
# Hipótese: com corpos comprometidos à frente (swarm no arco, blitz no
# reinício, cpw marcando linhas), sobra menos gente OFERECENDO linha de passe
# no meio — o portador conduz sozinho e é desarmado.
# base = v7.4; adversário = BotAdversario2clone (muralha).
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V74=$(cat ../bot/genome_v74_candidate.json)

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 30

# M4 — apoio ATIVO: recebedores sobem oferecendo linha segura (gene existente,
#      nunca testado com a estrutura nova)
$PY ab_transition.py --tag m4_offer --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V74" --test '{"support_mode":"offer"}' --mode rush \
  > ../results/screen/margem_m4_offer.log 2>&1

# M5 — menos corpos estacionados no arco (1 em vez de 2): testa se o swarm é
#      quem drena a rede de passes do meio
$PY ab_transition.py --tag m5_sw1 --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V74" --test '{"sw_count":1}' --mode rush \
  > ../results/screen/margem_m5_sw1.log 2>&1

# M6 — largura no ataque (deslocar o GK; anatomia do BotAdversario10 62%)
$PY ab_transition.py --tag m6_width --reps 8 --parallel 2 --opp BotAdversario2clone:latest \
  --base "$V74" --test '{"attack_width":"on","attack_width_shift":-0.2}' --mode rush \
  > ../results/screen/margem_m6_width.log 2>&1

echo "margem2_queue: M4+M5+M6 concluídos $(date '+%H:%M:%S')"
