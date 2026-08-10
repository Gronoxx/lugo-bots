#!/usr/bin/env bash
# Prepara o projeto numa máquina Linux (testado com EndeavourOS / Arch).
#
#   ./bench/setup_linux.sh
#
# No Linux o Docker roda nativo — sem a VM que no macOS limitava a 4 núcleos.
# Com i5-10400F (6 núcleos / 12 threads) e 15,5 GB, espera-se vazão bem maior
# e espaço para 2-3 partidas simultâneas.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

echo "=== 1. Dependências ==="
if ! command -v docker >/dev/null; then
    echo "Docker não encontrado. No Arch/EndeavourOS:"
    echo "  sudo pacman -S docker docker-compose"
    echo "  sudo systemctl enable --now docker"
    echo "  sudo usermod -aG docker \$USER   # e reinicie a sessão"
    exit 1
fi
docker info >/dev/null 2>&1 || {
    echo "Docker instalado mas o daemon não responde (ou faltam permissões)."
    echo "  sudo systemctl start docker"
    echo "  sudo usermod -aG docker \$USER && reinicie a sessão"
    exit 1
}
command -v docker-compose >/dev/null || command -v "docker compose" >/dev/null || {
    echo "AVISO: docker-compose não encontrado; os scripts usam 'docker-compose'."
    echo "  sudo pacman -S docker-compose"
}
python3 --version

echo
echo "=== 2. Ambiente Python ==="
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q grpcio protobuf lugo4py numpy grpcio-reflection
.venv/bin/python -c "import lugo4py; print('  lugo4py OK')"

echo
echo "=== 3. Imagens do servidor e do baseline ==="
docker pull -q lugobots/server:latest
docker pull -q lugobots/the-dummies-go:latest

echo
echo "=== 4. Construir o nosso bot e os rivais ==="
docker build -q -t mybot:v9 "$ROOT/bot" >/dev/null && echo "  mybot:v9 OK"
bash "$HERE/build_rivals.sh" 2>&1 | tail -5

echo
echo "=== 5. Verificações que não dependem de partida ==="
.venv/bin/python "$HERE/test_edge_cases.py"
.venv/bin/python "$HERE/latency.py" | tail -2

echo
echo "=== 6. Recursos disponíveis ==="
echo "  núcleos: $(nproc)"
echo "  memória: $(free -g | awk '/^Mem:/{print $2}') GB"
echo "  docker : $(docker info --format '{{.NCPU}} CPUs, {{.MemTotal}} bytes' 2>/dev/null)"

echo
echo "=== PRONTO ==="
echo "Teste uma partida e CRONOMETRE (no macOS levava ~5 min):"
echo "  time ./bench/run_match.sh mybot:v9 lugobots/the-dummies-go:latest teste"
echo
echo "Se o tempo cair bem, habilite partidas paralelas — é o maior multiplicador"
echo "para a evolução. Cada partida usa 23 containers leves e uma porta distinta."
