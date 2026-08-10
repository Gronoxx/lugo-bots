#!/usr/bin/env bash
# Constrói imagens Docker dos bots públicos de participantes, para servirem de
# painel de adversários reais.
#
# Por que não usar os Dockerfiles deles: usam `COPY ../requirements.txt`, que
# depende de um contexto de build fora do diretório, e nenhum deles espera o
# servidor aceitar conexões — sem isso parte do time não conecta e a partida é
# perdida por W.O. (o cliente lugo4py tem timeout fixo de 5s, sem retry).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RIVALS="$HERE/../rivals"
BUILD="$HERE/.rival_build"

RIVAL_LIST=(
    "Participante1_lugo-bot:rival_p1"
    "Participante2_BotParticipante2:rival_p2"
    "Participante3_bot:rival_p3"
    "Participante4_bot:rival_p4"
)

rm -rf "$BUILD"; mkdir -p "$BUILD"

# entrypoint comum: espera a porta do servidor antes de subir o bot
cat > "$BUILD/entrypoint.py" <<'PY'
import os, socket, time, subprocess, sys

addr = os.environ.get("BOT_GRPC_URL", "localhost:5000")
host, _, port = addr.partition(":")
port = int((port or "5000").split("?")[0])
deadline = time.time() + 120
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(1)
sys.exit(subprocess.call([sys.executable, "./src/main.py"]))
PY

cat > "$BUILD/requirements.txt" <<'REQ'
grpcio==1.51.1
grpcio-tools==1.51.1
lugo4py==1.0.5
protobuf==4.21.12
REQ

cat > "$BUILD/Dockerfile" <<'DOCKER'
FROM python:3.9-slim-bookworm
WORKDIR /usr/src/app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY entrypoint.py ./
COPY src ./src
CMD ["python", "./entrypoint.py"]
DOCKER

for entry in "${RIVAL_LIST[@]}"; do
    dir="${entry%%:*}"; tag="${entry##*:}"
    src="$RIVALS/$dir/src"
    if [ ! -d "$src" ]; then
        echo "PULANDO $dir (sem src/)"; continue
    fi
    rm -rf "$BUILD/src"; cp -R "$src" "$BUILD/src"
    if docker build -q -t "$tag:latest" "$BUILD" >/dev/null 2>&1; then
        echo "OK   $tag  <- $dir"
    else
        echo "FALHA $tag <- $dir"
        docker build -t "$tag:latest" "$BUILD" 2>&1 | tail -5
    fi
done

rm -rf "$BUILD"
echo
docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^rival_' | sort
