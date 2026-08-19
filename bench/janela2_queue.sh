#!/usr/bin/env bash
# janela2_queue.sh — EXPLORAR O VAZIO. O level-1 persegue em bando: onde a
# bola está há multidão, e o resto do campo está VAZIO. O lane_seek falhou
# porque o portador caminha até a janela e o bando o acompanha (autorizado
# 4,4%->3,6%). A bola é 4x mais rápida que o jogador => a janela tem que ser
# alcançada por PASSE, e o vazio fica do lado OPOSTO à bola.
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
V10=$(cat ../bot/genome_v10_candidate.json)

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 20

# M4 — TROCA DE FLANCO + passe-para-atirador: tirar a bola do bando e achar
#      quem está livre do outro lado, com linha limpa.
$PY ab_transition.py --tag m4_switch --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V10" --test '{"pass_w_shooter":2000,"pass_w_switch":2.0}' --mode rush \
  > ../results/screen/m4_switch.log 2>&1

# M5 — LARGURA MÁXIMA no ataque: espalhar os atacantes para que exista sempre
#      alguém fora do bando (o "2-8" do BotAdversario2 depende disso).
$PY ab_transition.py --tag m5_largura --reps 8 --parallel 2 --opp lugobots/level-1:latest \
  --base "$V10" --test '{"pass_w_shooter":2000,"attack_width_shift":-0.35,"support_channel_width":3000,"support_n_forward":3}' \
  --mode rush > ../results/screen/m5_largura.log 2>&1

echo "janela2_queue: M4+M5 concluídos $(date '+%H:%M:%S')"
