#!/usr/bin/env bash
# v7_queue_b.sh — retomada da fila v7 (S1 já completou; interrompida no S2)
# + S1b: swarm vs level-1 (a régua do mecanismo-alvo: GK que rebate muito;
# vs sparring-BotAdversario1 o cerco não pagou — fin 7,88→7,31, sb_won 19→18%).
set -u
cd "$(dirname "$0")"
mkdir -p ../results/screen
V6=$(cat ../bot/genome_v6.json)
PY=~/lugo-bots/.venv/bin/python

# S2 — pacote-kickoff vs sparring (corrida disputada: race 1500 vs v3 1581)
$PY ab_transition.py --tag v7s2_kick --reps 8 --parallel 2 --opp sparring \
  --base "$V6" \
  --test '{"init_variant":"race","kickoff_play":"on","kickoff_blitz":"on","kickoff_race":"on"}' \
  --mode rush > ../results/screen/v7s2_kick.log 2>&1

# S1b — swarm_rebound vs level-1 (mecanismo no contexto-alvo)
$PY ab_transition.py --tag v7s1b_swarmL1 --reps 8 --parallel 2 \
  --opp lugobots/level-1:latest --base "$V6" \
  --test '{"swarm_rebound":"on"}' --mode rush \
  > ../results/screen/v7s1b_swarmL1.log 2>&1

# S3 — opd + cpw vs sparring-BotAdversario1 (morte: gols PRÓ não podem cair)
$PY ab_transition.py --tag v7s3_adv1 --reps 8 --parallel 2 --opp sparring \
  --base "$V6" \
  --test '{"outlet_press_detect":"on","counter_press_window":"on"}' \
  --mode rush > ../results/screen/v7s3_adv1.log 2>&1

# S4 — kickoff_shield solo vs sparring (morte: gols PRÓ não podem cair)
$PY ab_transition.py --tag v7s4_shield --reps 8 --parallel 2 --opp sparring \
  --base "$V6" --test '{"kickoff_shield":"on"}' --mode rush \
  > ../results/screen/v7s4_shield.log 2>&1

# S5 — quina_entry solo vs level-1
$PY ab_transition.py --tag v7s5_quina --reps 8 --parallel 2 \
  --opp lugobots/level-1:latest --base "$V6" \
  --test '{"quina_entry":"on"}' --mode rush \
  > ../results/screen/v7s5_quina.log 2>&1

echo "v7_queue_b: S2, S1b, S3, S4, S5 concluídos $(date '+%H:%M:%S')"
