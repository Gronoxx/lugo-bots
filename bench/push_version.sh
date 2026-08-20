#!/usr/bin/env bash
# Publica um genoma como versão da plataforma.
# Uso: bash bench/push_version.sh <genoma.json> <tag>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE/.."
G="$1"; TAG="$2"
IMG="repo.lugobots.ai/killua-zoldyck:$TAG"
cp bot/genome_submit.json bot/.genome_submit.bak
python3 -c "import json;print(json.dumps(json.load(open('$G')),separators=(',',':')))" > bot/genome_submit.json
echo "genoma embarcado: $(cat bot/genome_submit.json)"
docker build -f bot/Dockerfile.submit -t "$IMG" bot >/dev/null
# conferência: o genoma DENTRO da imagem carrega todos os genes?
docker run --rm --entrypoint python "$IMG" -c "
import json, os, sys
sys.path.insert(0,'/usr/src/app/src')
os.environ['BOT_PARAMS_FILE']='/usr/src/app/genome_submit.json'
import params
g=json.load(open('/usr/src/app/genome_submit.json'))
bad=[k for k,v in g.items() if str(params.P.get(k))!=str(v) and not (isinstance(params.P.get(k),float) and abs(params.P[k]-float(v))<1e-9)]
print('genes na imagem:', len(g), '| divergentes:', bad)
sys.exit(1 if bad else 0)
"
docker push "$IMG" | tail -2
docker inspect "$IMG" --format 'digest local: {{index .RepoDigests 0}}' 2>/dev/null || true
mv bot/.genome_submit.bak bot/genome_submit.json
echo "genome_submit.json restaurado"
