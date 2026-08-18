#!/usr/bin/env bash
# precisao_queue.sh — FORENSE DO 10x0 aplicada. Achados:
#  (a) os gols dos goleadores entram COLADOS AO POSTE (|y-5000| ~1500) e saem
#      de <=2900 (mediana 2400); nosso shot_post_margin=200 limita a mira a
#      1300 — o bot NUNCA mira onde os gols entram;
#  (b) 1/3 dos nossos chutes sai de 4500-6000 e converte 10,4%, enquanto na
#      faixa <=2600 convertemos 62-85% (tão bem quanto o BotAdversario6);
#  (c) cortar o chute longe SOZINHO já falhou (gate híbrido da v6): é preciso
#      dar ao portador o que fazer no lugar (penetrar pela quina/ângulo).
# base = v9 (v8 + mais corpos, gf 3,94 com ga 0,06).
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V9=$(cat ../bot/genome_v9_candidate.json)

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 20

# J1 — MIRA NO POSTE (correção mecânica isolada; teto de mira 1300 -> 1380)
$PY ab_transition.py --tag j1_mira --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V9" --test '{"shot_post_margin":120}' --mode rush \
  > ../results/screen/j1_mira.log 2>&1

# J2 — NÃO DOAR + PENETRAR: híbrido corta o chute de 4500-6000 E quina/ângulo
#      dão ao portador a alternativa (o par que a bisseção anterior separou).
$PY ab_transition.py --tag j2_penetra --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V9" --test '{"shot_gate":"hybrid","hybrid_close_range":3200,"quina_entry":"on","angle_seek":"on"}' \
  --mode rush > ../results/screen/j2_penetra.log 2>&1

# J3 — PACOTE PRECISÃO COMPLETO (mira + não-doar + penetrar)
$PY ab_transition.py --tag j3_precisao --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V9" --test '{"shot_post_margin":120,"shot_gate":"hybrid","hybrid_close_range":3200,"quina_entry":"on","angle_seek":"on"}' \
  --mode rush > ../results/screen/j3_precisao.log 2>&1

echo "precisao_queue: J1+J2+J3 concluídos $(date '+%H:%M:%S')"
