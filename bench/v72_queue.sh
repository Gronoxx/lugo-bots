#!/usr/bin/env bash
# v72_queue.sh — TRAVAS da v7.2-candidata (v6 + pacote-kickoff + pacote-BotAdversario1
# + quina + ot_press + pacote-cenas [+ swarm se aprovado no S1c]).
# base = v6; test = extras (diff v72−v6, computado do genoma canônico).
# C1 selfplay (anti-desastre) -> C2 sparring rush -> C3 wait vs L1 (decisivo).
# ~3h15. Tags LOWERCASE (docker compose rejeita maiúscula no project name).
set -u
cd "$(dirname "$0")"
V6=$(cat ../bot/genome_v6.json)
EXTRA=$(~/lugo-bots/.venv/bin/python - <<'EOF'
import json
v6 = json.load(open('../bot/genome_v6.json'))
v72 = json.load(open('../bot/genome_v72_candidate.json'))
print(json.dumps({k: v for k, v in v72.items() if v6.get(k) != v}))
EOF
)
PY=~/lugo-bots/.venv/bin/python
echo "EXTRAS v7.2: $EXTRA"

# C1 — selfplay: trava ANTI-DESASTRE apenas (régua ruim p/ gene ofensivo)
$PY ab_selfplay.py --reps 16 --parallel 2 --tag v72c1 \
  --base "$V6" --test "$EXTRA" > ../results/screen/v72_c1_selfplay.log 2>&1

# C2 — sparring-BotAdversario1 rush (good_chance, ga, kickoff/rebote agora no painel)
$PY ab_transition.py --tag v72c2_spar --reps 8 --parallel 2 --opp sparring \
  --base "$V6" --test "$EXTRA" --mode rush \
  > ../results/screen/v72_c2_spar.log 2>&1

# C3 — wait vs level-1 (timer do campeonato; o teste decisivo do gf/fin)
$PY ab_transition.py --tag v72c3_l1w --reps 8 --parallel 2 \
  --opp lugobots/level-1:latest --base "$V6" --test "$EXTRA" --mode wait \
  > ../results/screen/v72_c3_l1w.log 2>&1

echo "v72_queue: C1+C2+C3 concluídos $(date '+%H:%M:%S')"
