#!/usr/bin/env bash
# camp_queue.sh — O "2-8": medir o acampamento alto, que é a maior diferença
# estrutural encontrada (temos 1,0 corpo no terço de ataque; BotAdversario2 tem 8-9).
set -u
cd "$(dirname "$0")"
PY=~/lugo-bots/.venv/bin/python
gen() { $PY -c "
import json,sys; g=json.load(open('../bot/genome_v10_candidate.json'))
g.update(json.loads(sys.argv[1])); print(json.dumps(g))" "$1"; }

while docker ps --filter name=lugo_ --format '{{.Names}}' | grep -q .; do sleep 60; done
sleep 20

# C1 — acampamento sozinho
$PY escada.py --genome <(gen '{"high_camp":"on"}') --n 8 --tag camp1 --alvo 10 \
  --knockout 99 --mode rush > ../results/screen/escada_camp1.log 2>&1

# C2 — acampamento + risco no passe ao atirador (os dois achados juntos)
$PY escada.py --genome <(gen '{"high_camp":"on","risk_pass_shooter":"on","pass_w_shooter":2000}') \
  --n 8 --tag camp2 --alvo 10 --knockout 99 --mode rush \
  > ../results/screen/escada_camp2.log 2>&1

# C3 — acampamento AGRESSIVO (atacantes a 0.80 = x16000, meias a 0.65)
$PY escada.py --genome <(gen '{"high_camp":"on","hc_floor_fwd":0.80,"hc_floor_mid":0.65,"risk_pass_shooter":"on","pass_w_shooter":2000}') \
  --n 8 --tag camp3 --alvo 10 --knockout 99 --mode rush \
  > ../results/screen/escada_camp3.log 2>&1

echo "camp_queue: C1+C2+C3 concluídos $(date '+%H:%M:%S')"
