#!/usr/bin/env bash
# v7_queue.sh — SCREENING individual dos genes do metamorfo, base = v6.
# Máx 2 partidas simultâneas (teto de memória 15G). Cada bloco = 32 jogos
# rush ≈ 48min; fila completa ≈ 4h. Logs em results/screen/v7s*.log.
#
# Elegibilidade (regra do programa tático): a métrica DENSA do mecanismo tem
# que se mover na direção prevista; ga não pode subir; cpw/shield têm morte
# pré-declarada (gols PRÓ não podem cair).
set -u
cd "$(dirname "$0")"
mkdir -p ../results/screen
V6=$(cat ../bot/genome_v6.json)
PY=~/lugo-bots/.venv/bin/python

# S1 — swarm_rebound solo vs sparring-BotAdversario1.
#      Métrica: our_shots_on_goal_pg (7→12+), sb_won/reshot60, ga estável.
$PY ab_transition.py --tag v7s1_swarm --reps 8 --parallel 2 --opp sparring \
  --base "$V6" --test '{"swarm_rebound":"on"}' --mode rush \
  > ../results/screen/v7s1_swarm.log 2>&1

# S2 — pacote-kickoff (race init + playbook + blitz + ring) vs sparring
#      (init v3 espelho d=1581: com race 1500 a corrida vira NOSSA em todo
#      reinício — o A/B mede exatamente isso: ko_won_pct, ko_gf200, blitz).
$PY ab_transition.py --tag v7s2_kick --reps 8 --parallel 2 --opp sparring \
  --base "$V6" \
  --test '{"init_variant":"race","kickoff_play":"on","kickoff_blitz":"on","kickoff_race":"on"}' \
  --mode rush > ../results/screen/v7s2_kick.log 2>&1

# S3 — pacote-BotAdversario1 de saída/transição (opd + cpw) vs sparring-BotAdversario1.
#      Métrica: def_start_turnover_pct e interceptados/posse ↓; MORTE se
#      gols PRÓ caírem (lei da passividade, cpw é revisita de rejeitado).
$PY ab_transition.py --tag v7s3_adv1 --reps 8 --parallel 2 --opp sparring \
  --base "$V6" \
  --test '{"outlet_press_detect":"on","counter_press_window":"on"}' \
  --mode rush > ../results/screen/v7s3_adv1.log 2>&1

# S4 — kickoff_shield solo vs sparring. MORTE se gols PRÓ caírem;
#      métrica-alvo: ko_ga200/ga_fast ↓.
$PY ab_transition.py --tag v7s4_shield --reps 8 --parallel 2 --opp sparring \
  --base "$V6" --test '{"kickoff_shield":"on"}' --mode rush \
  > ../results/screen/v7s4_shield.log 2>&1

# S5 — quina_entry solo vs level-1 (conversão/good_chance; L1 deixa entrar).
$PY ab_transition.py --tag v7s5_quina --reps 8 --parallel 2 \
  --opp lugobots/level-1:latest --base "$V6" \
  --test '{"quina_entry":"on"}' --mode rush \
  > ../results/screen/v7s5_quina.log 2>&1

echo "v7_queue: screenings S1-S5 concluídos $(date '+%H:%M:%S')"
