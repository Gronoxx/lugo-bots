#!/usr/bin/env bash
# Varre um parâmetro do bot sobre vários valores, sem reconstruir a imagem.
#
#   ./sweep.sh <imagem> <parametro> <valores...>
#   ./sweep.sh mybot:v9 shot_min_gap 900 1300 1700 2100
#
# Usa BOT_PARAMS (JSON no ambiente), lido por bot/src/params.py. Uma imagem
# serve qualquer genoma — é o mesmo mecanismo que a evolução vai usar.
#
# Cada valor joga N repetições nos dois lados. Com desvio ~2,1 gols, 3 reps
# (6 partidas) distinguem diferenças acima de ~2,4 gols; 5 reps (10 partidas),
# acima de ~1,8. Escolha N conforme o tempo disponível.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"

BOT="$1"; PARAM="$2"; shift 2
VALUES=("$@")
N="${REPS:-3}"
OPP="${OPP:-lugobots/the-dummies-go:latest}"
OUT="results/sweep_${PARAM}.csv"

mkdir -p results
echo "parametro,valor,lado,rep,gols_pro,gols_contra" > "$OUT"

for val in "${VALUES[@]}"; do
  for rep in $(seq 1 "$N"); do
    for side in home away; do
      id="sw_${PARAM}_${val}_${side}_${rep}"
      if [ "$side" = home ]; then
        h="$BOT"; a="$OPP"; export HOME_PARAMS="{\"$PARAM\":$val}"; unset AWAY_PARAMS
      else
        h="$OPP"; a="$BOT"; export AWAY_PARAMS="{\"$PARAM\":$val}"; unset HOME_PARAMS
      fi
      if ! TIMER_MODE=wait ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1; then
        echo "$PARAM,$val,$side,$rep,ERRO,ERRO" >> "$OUT"; continue
      fi
      sc=$(python3 match_done.py "recordings/${id}.json" 2>/dev/null)
      hg=$(echo "$sc" | awk '{print $1}'); ag=$(echo "$sc" | awk '{print $3}')
      if [ "$side" = home ]; then p="$hg"; c="$ag"; else p="$ag"; c="$hg"; fi
      echo "$PARAM,$val,$side,$rep,$p,$c" >> "$OUT"
      echo "  $PARAM=$val [$side #$rep]: $p x $c"
      rm -f "recordings/${id}.json"
    done
  done
done

echo
python3 - "$OUT" <<'PY'
import csv, sys, statistics
from collections import defaultdict
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["gols_pro"] != "ERRO"]
by = defaultdict(list)
for r in rows:
    by[float(r["valor"])].append(int(r["gols_pro"]))
print(f"{'valor':>10}{'n':>4}{'gols':>9}{'desvio':>9}{'erro padrao':>13}")
best = None
for v in sorted(by):
    g = by[v]
    sd = statistics.stdev(g) if len(g) > 1 else 0
    se = sd / (len(g) ** 0.5) if g else 0
    print(f"{v:>10.0f}{len(g):>4}{statistics.mean(g):>9.2f}{sd:>9.2f}{se:>13.2f}")
    if best is None or statistics.mean(g) > best[1]:
        best = (v, statistics.mean(g), se)
if best:
    print(f"\nmelhor: {best[0]:.0f} com {best[1]:.2f} gols (erro padrao {best[2]:.2f})")
    print("ATENÇÃO: com poucas repetições a diferença entre valores vizinhos")
    print("pode ser ruído. Confirme o vencedor com mais partidas antes de fixar.")
PY
