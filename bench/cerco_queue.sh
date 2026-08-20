#!/usr/bin/env bash
# FILA DO CERCO (20/08) — as duas hipóteses da forense do 0×0 vs level-3.
#
# Régua: level-1 LOCAL, que é o proxy calibrado do level-3 da plataforma
# (medido hoje: campo_adv 37,6% local vs 37,7% no 0×0 oficial; v6 local
# 1,17 gols / 3,5 fin vs 3 gols / 7 fin vs L3 — mesmo regime, escala ~2x).
#
# H1 (qualidade): o que separou a v6 (3×0 no L3) da v10 (0×0) foi o PORTÃO de
#     chute. hybrid nega o chute longo estéril; threshold doa ao GK de elite
#     (v4: 44 chutes, 43 defesas, 1 gol; BotAdversario5: 23 chutes, 0 gols).
#     => v10q = a máquina de volume da v10 COM o portão da v6.
# H2 (cerco): sem acampados nem saída longa a bola recuperada volta a
#     circular atrás (137 passes a 94,5% e 8 finalizações no 0×0).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."
N=${N:-6}
PAR=${PAR:-8}
mkdir -p results/screen bot/tmp

run () {  # nome  base-genoma  json-extra
  local name="$1"; local basef="$2"; local extra="$3"
  python3 - "$basef" "$extra" > "bot/tmp/g_$name.json" <<'PY'
import json, sys
base = json.load(open(sys.argv[1]))
base.update(json.loads(sys.argv[2]))
print(json.dumps(base))
PY
  echo "=== $name : $(cat bot/tmp/g_$name.json)"
  python3 bench/escada.py --genome "bot/tmp/g_$name.json" --tag "c_$name" \
      --n "$N" --parallel "$PAR" --mode wait --knockout 99 \
      > "results/screen/cerco_$name.log" 2>&1
  tail -5 "results/screen/cerco_$name.log"
}

QUAL='{"shot_gate":"hybrid","gk_reach_speed":100,"dangerous_shot_range":6000,"shot_min_gap":1300}'
CERCO='{"def_camp":"on","outlet_risk":"on"}'

run base   bot/genome_v6.json  '{}'
run camp   bot/genome_v6.json  '{"def_camp":"on"}'
run outlet bot/genome_v6.json  '{"outlet_risk":"on"}'
run ambos  bot/genome_v6.json  "$CERCO"
run v10q   bot/genome_v10_candidate.json "$QUAL"
run v10qc  bot/genome_v10_candidate.json "$(python3 -c "
import json;a=json.loads('$QUAL');a.update(json.loads('$CERCO'));print(json.dumps(a))")"
