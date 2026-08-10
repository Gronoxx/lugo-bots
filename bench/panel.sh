#!/usr/bin/env bash
# Mede um bot contra todo o painel de adversários, nos dois lados do campo,
# com repetições — e escreve os resultados em CSV.
#
#   ./panel.sh <imagem> <repeticoes> <arquivo_csv>
#
# O ruído é alto (mesmo bot fez 6x0 e 2x0), então repetições não são luxo:
# uma partida sozinha não distingue configurações.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BOT="${1:-mybot:v3}"
REPS="${2:-3}"
OUT="${3:-$HERE/results/panel_$(date +%Y%m%d_%H%M).csv}"

PANEL=(
    "lugobots/the-dummies-go:latest"
    "rival_p1:latest"
    "rival_p2:latest"
    "rival_p3:latest"
    "rival_p4:latest"
)

mkdir -p "$(dirname "$OUT")"
echo "bot,adversario,lado,rep,gols_pro,gols_contra" > "$OUT"

for opp in "${PANEL[@]}"; do
    short=$(echo "$opp" | sed 's|.*/||; s|:.*||')
    for rep in $(seq 1 "$REPS"); do
        for side in home away; do
            id="p_${short}_${side}_${rep}"
            if [ "$side" = "home" ]; then h="$BOT"; a="$opp"; else h="$opp"; a="$BOT"; fi

            if ! "$HERE/run_match.sh" "$h" "$a" "$id" >/dev/null 2>&1; then
                echo "$BOT,$short,$side,$rep,ERRO,ERRO" >> "$OUT"
                echo "  [$id] ERRO"
                continue
            fi
            score=$(python3 "$HERE/match_done.py" "$HERE/recordings/${id}.json" 2>/dev/null)
            hg=$(echo "$score" | awk '{print $1}')
            ag=$(echo "$score" | awk '{print $3}')
            if [ "$side" = "home" ]; then pro="$hg"; con="$ag"; else pro="$ag"; con="$hg"; fi
            echo "$BOT,$short,$side,$rep,$pro,$con" >> "$OUT"
            echo "  [$id] $pro x $con"
            rm -f "$HERE/recordings/${id}.json"      # 18 MB cada; não acumular
        done
    done
done

echo
echo "=== RESUMO ($OUT) ==="
python3 - "$OUT" <<'PY'
import csv, sys, statistics
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
by = defaultdict(list)
for r in rows:
    if r["gols_pro"] == "ERRO":
        continue
    by[r["adversario"]].append((int(r["gols_pro"]), int(r["gols_contra"])))
print(f"{'adversario':<18}{'n':>3}{'gols pró':>10}{'gols contra':>13}{'desvio pró':>12}{'V-E-D':>10}")
for opp, v in sorted(by.items()):
    gf = [a for a, _ in v]; ga = [b for _, b in v]
    w = sum(1 for a, b in v if a > b); d = sum(1 for a, b in v if a == b); l = len(v)-w-d
    sd = statistics.stdev(gf) if len(gf) > 1 else 0.0
    print(f"{opp:<18}{len(v):>3}{statistics.mean(gf):>10.1f}{statistics.mean(ga):>13.1f}"
          f"{sd:>12.2f}{f'{w}-{d}-{l}':>10}")
PY
