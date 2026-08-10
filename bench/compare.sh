#!/usr/bin/env bash
# Compara duas versões contra o mesmo adversário, alternando lados, em wait mode.
#
#   ./compare.sh <bot_a> <bot_b> <repeticoes> [adversario]
#   ./compare.sh mybot:v3 mybot:v8 8
#
# Cada repetição joga os dois lados, então N=8 dá 16 partidas por versão.
# Isso importa: o A/B anterior usou 8 por versão e tinha só 17% de poder para
# detectar +1 gol. Com desvio ~2,0, 16 por braço detecta ~+1,4 gol.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"

A="${1:-mybot:v3}"; B="${2:-mybot:v8}"; N="${3:-8}"
OPP="${4:-lugobots/the-dummies-go:latest}"
OUT="results/cmp_$(echo "${A}_${B}" | tr ':/' '__').csv"

mkdir -p results
echo "versao,lado,rep,gols_pro,gols_contra" > "$OUT"

for bot in "$A" "$B"; do
  tag=$(echo "$bot" | tr ':/' '__')
  for rep in $(seq 1 "$N"); do
    for side in home away; do
      id="cmp_${tag}_${side}_${rep}"
      if [ "$side" = home ]; then h="$bot"; a="$OPP"; else h="$OPP"; a="$bot"; fi
      if ! TIMER_MODE=wait ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1; then
        echo "$bot,$side,$rep,ERRO,ERRO" >> "$OUT"; continue
      fi
      sc=$(python3 match_done.py "recordings/${id}.json" 2>/dev/null)
      hg=$(echo "$sc" | awk '{print $1}'); ag=$(echo "$sc" | awk '{print $3}')
      if [ "$side" = home ]; then p="$hg"; c="$ag"; else p="$ag"; c="$hg"; fi
      echo "$bot,$side,$rep,$p,$c" >> "$OUT"
      echo "  $id: $p x $c"
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
    by[r["versao"]].append(int(r["gols_pro"]))
print(f"{'versao':<14}{'n':>3}{'gols medios':>13}{'desvio':>9}")
for k, v in by.items():
    sd = statistics.stdev(v) if len(v) > 1 else 0
    print(f"{k:<14}{len(v):>3}{statistics.mean(v):>13.2f}{sd:>9.2f}")
ks = list(by)
if len(ks) == 2:
    a, b = by[ks[0]], by[ks[1]]
    ma, mb = statistics.mean(a), statistics.mean(b)
    sa = statistics.stdev(a) if len(a) > 1 else 0
    sb = statistics.stdev(b) if len(b) > 1 else 0
    se = (sa**2/len(a) + sb**2/len(b))**0.5 or 1e-9
    d = mb - ma
    print(f"\ndiferenca {ks[1]} - {ks[0]}: {d:+.2f} gols (erro padrao {se:.2f})")
    if abs(d) > 1.96*se:
        print("CONCLUSIVO")
    else:
        # ser explícito sobre o que o teste conseguiria detectar, para não
        # confundir "sem efeito" com "sem poder para ver o efeito"
        print(f"NAO conclusivo — este teste só detectaria diferenças acima de "
              f"{1.96*se:.2f} gols")
PY
