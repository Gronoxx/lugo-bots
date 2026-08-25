#!/usr/bin/env bash
# CONFIRMAÇÕES em WAIT (modo do campeonato) do genoma v3 — rodar ANTES de fixar
# defaults/submeter. ~4-5h de máquina. Logs em results/screen/confirm_*.log.
# Aceite: v3 não pior que v2 no self-play (saldo ≥ −0,15, não significativo) e
# sofridos vs sparring menores/iguais; level-1 saldo mantido.
set -u
PY=${PY:-$HOME/lugo-bots/.venv/bin/python}
cd "$(dirname "$0")"
mkdir -p ../results/screen

V2='{"pass_endpoint_race":"on","pass_exec_speed":"on","pass_touch_lead":"on","pass_status_mode":"on","cover_mode":"on"}'
V3GENES='{"gk_outlet":"on","gk_jump_mode":"strict"}'

echo "[1/3] v3 vs sparring em WAIT (16/braço = 64 partidas, ~3h)"
$PY ab_transition.py --tag cfw_spar --test "$V3GENES" --opp sparring \
    --reps 8 --parallel 3 --mode wait > ../results/screen/confirm_sparring.log 2>&1

echo "[2/3] self-play v3 vs v2 em rush ampliado (20 reps = 40 partidas, ~1h)"
$PY ab_selfplay.py --base "$V2" --test "$V3GENES" --tag cfsp --reps 20 \
    --parallel 3 > ../results/screen/confirm_selfplay.log 2>&1

echo "[3/3] sanidade vs rival_p1 (2x2 partidas)"
$PY ab_transition.py --tag cfr --test "$V3GENES" --opp rival_p1:latest \
    --reps 2 --parallel 2 > ../results/screen/confirm_rival_p1.log 2>&1

echo "CONFIRMACOES_CONCLUIDAS — ler results/screen/confirm_*.log"
