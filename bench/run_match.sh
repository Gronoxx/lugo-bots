#!/usr/bin/env bash
# Roda uma partida entre duas imagens e devolve o replay.
#
#   ./run_match.sh <imagem_home> <imagem_away> <id_da_partida>
#
# Usa timer-mode=rush: o servidor processa assim que todos os bots enviam
# suas ordens, então uma partida de 6000 turnos leva ~1-2 min em vez de 5.
set -euo pipefail

HOME_BOT="${1:-mybot:v1}"
AWAY_BOT="${2:-lugobots/the-dummies-go:latest}"
MATCH_ID="${3:-match_$(date +%s)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="$HERE/dc_${MATCH_ID}.yml"

cd "$HERE"
mkdir -p recordings
# o servidor faz panic (nil pointer no LocalFileWriter) se o arquivo de
# gravação já existir — sempre partir de um caminho limpo
rm -f "recordings/${MATCH_ID}.json"

# PADRÃO = wait. Medido: com config idêntica, `rush` deu 6 e 2 gols (desvio
# 2,83) e `wait` deu 4, 6 e 5 (desvio 1,00). Em `rush` o servidor avança assim
# que as ordens chegam, e sob contenção de 22 processos em 4 núcleos a ordem de
# chegada varia — é ruído do nosso laboratório, não do jogo. `wait` dá 50 ms a
# todos, reproduz o que os composes dos rivais usam, e apesar de a partida
# demorar mais, exige tão menos repetições que sai MAIS BARATO no total.
# KNOCKOUT_DIFF (escada de goleada): eleva o teto de saldo do knockout do
# servidor (default 10 = regra de misericórdia oficial). Sem a variável, o
# comportamento é o oficial.
python3 gen_compose.py --home "$HOME_BOT" --away "$AWAY_BOT" \
    --timer-mode "${TIMER_MODE:-wait}" \
    ${KNOCKOUT_DIFF:+--knockout-diff "$KNOCKOUT_DIFF"} \
    --headless --quiet --match-id "$MATCH_ID" --out "$COMPOSE" >/dev/null

docker-compose -p "lugo_$MATCH_ID" -f "$COMPOSE" up -d >/dev/null 2>&1

SERVER=$(docker-compose -p "lugo_$MATCH_ID" -f "$COMPOSE" ps -q server)
if [ -z "$SERVER" ]; then
    echo "ERRO: servidor não subiu para $MATCH_ID" >&2
    docker-compose -p "lugo_$MATCH_ID" -f "$COMPOSE" down >/dev/null 2>&1 || true
    exit 1
fi

# O fim da partida é detectado pelo evento `game_over` NO REPLAY, não pelo
# estado do container: o servidor termina a partida mas mantém o processo vivo,
# então esperar o container sair custava ~20 min por partida em vez de ~3.
REPLAY="$HERE/recordings/${MATCH_ID}.json"
WAITED=0
until python3 "$HERE/match_done.py" "$REPLAY" >/dev/null 2>&1; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [ "$WAITED" -gt 900 ]; then
        echo "ERRO: timeout esperando $MATCH_ID" >&2
        docker-compose -p "lugo_$MATCH_ID" -f "$COMPOSE" down >/dev/null 2>&1 || true
        exit 1
    fi
done

docker-compose -p "lugo_$MATCH_ID" -f "$COMPOSE" down >/dev/null 2>&1 || true
rm -f "$COMPOSE"
echo "$HERE/recordings/${MATCH_ID}.json"
