#!/usr/bin/env bash
# Compara duas versões contra o mesmo adversário, em wait mode, alternando lados.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
OPP="lugobots/the-dummies-go:latest"; N=4
echo "versao,lado,rep,gols_pro,gols_contra" > results/ab_v3_v6.csv
for bot in mybot:v3 mybot:v6; do
  tag=$(echo "$bot" | tr ':' '_')
  for rep in $(seq 1 $N); do
    for side in home away; do
      id="ab_${tag}_${side}_${rep}"
      if [ "$side" = home ]; then h="$bot"; a="$OPP"; else h="$OPP"; a="$bot"; fi
      TIMER_MODE=wait ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1 || { echo "$bot,$side,$rep,ERRO,ERRO" >> results/ab_v3_v6.csv; continue; }
      sc=$(python3 match_done.py "recordings/${id}.json" 2>/dev/null)
      hg=$(echo "$sc"|awk '{print $1}'); ag=$(echo "$sc"|awk '{print $3}')
      if [ "$side" = home ]; then p="$hg"; c="$ag"; else p="$ag"; c="$hg"; fi
      echo "$bot,$side,$rep,$p,$c" >> results/ab_v3_v6.csv
      echo "  $id: $p x $c"
      rm -f "recordings/${id}.json"
    done
  done
done
echo; python3 - <<'PY'
import csv,statistics
rows=[r for r in csv.DictReader(open("results/ab_v3_v6.csv")) if r["gols_pro"]!="ERRO"]
from collections import defaultdict
by=defaultdict(list)
for r in rows: by[r["versao"]].append(int(r["gols_pro"]))
print(f"{'versao':<12}{'n':>3}{'gols medios':>13}{'desvio':>9}")
for k,v in sorted(by.items()):
    print(f"{k:<12}{len(v):>3}{statistics.mean(v):>13.2f}{(statistics.stdev(v) if len(v)>1 else 0):>9.2f}")
if len(by)==2:
    a,b=[by[k] for k in sorted(by)]
    ma,mb=statistics.mean(a),statistics.mean(b)
    sa,sb=statistics.stdev(a),statistics.stdev(b)
    se=(sa**2/len(a)+sb**2/len(b))**0.5
    print(f"\ndiferenca v6-v3: {mb-ma:+.2f} gols  (erro padrao {se:.2f})")
    print("conclusivo" if abs(mb-ma)>1.96*se else "NAO conclusivo com este n")
PY
