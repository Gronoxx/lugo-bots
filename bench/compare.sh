#!/usr/bin/env bash
# Compara duas versões contra o mesmo adversário, alternando lados, em wait mode.
#
#   ./compare.sh <bot_a> <bot_b> <repeticoes> [adversario]
#   ./compare.sh mybot:v3 mybot:v8 8
#
# Cada repetição joga os dois lados, então N=8 dá 16 partidas por versão.
# Isso importa: o A/B anterior usou 8 por versão e tinha só 17% de poder para
# detectar +1 gol. Com desvio ~2,0, 16 por braço detecta ~+1,4 gol.
#
# Paralelismo: roda até PARALLEL partidas ao mesmo tempo (padrão 3). Em wait
# mode isso não distorce o resultado — cada partida tem seu servidor e janela de
# 50ms/turno, e a decisão gasta ~1,3ms, então sobra folga mesmo com contenção.
# Exige gen_compose.py sem portas publicadas (default), senão colidem no host.
#   PARALLEL=3 ./compare.sh mybot:v3 mybot:v9 6 lugobots/level-1:latest
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"

A="${1:-mybot:v3}"; B="${2:-mybot:v8}"; N="${3:-8}"
OPP="${4:-lugobots/the-dummies-go:latest}"
OUT="results/cmp_$(echo "${A}_${B}" | tr ':/' '__').csv"

mkdir -p results
echo "versao,lado,rep,gols_pro,gols_contra" > "$OUT"

PARALLEL="${PARALLEL:-3}"
PARTDIR="results/.parts_$$"
mkdir -p "$PARTDIR"

# Roda UMA partida e grava o resultado num arquivo próprio (evita escrita
# concorrente no CSV). Cada partida tem id/porta/rede/replay únicos, então N
# delas rodam em paralelo sem colidir. Chamada em background pelo semáforo.
run_one() {
  local bot="$1" side="$2" rep="$3"
  local tag id h a sc hg ag p c
  tag=$(echo "$bot" | tr ':/' '__')
  id="cmp_${tag}_${side}_${rep}"
  if [ "$side" = home ]; then h="$bot"; a="$OPP"; else h="$OPP"; a="$bot"; fi
  if ! TIMER_MODE=wait ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1; then
    echo "$bot,$side,$rep,ERRO,ERRO" > "$PARTDIR/$id"; return
  fi
  sc=$(python3 match_done.py "recordings/${id}.json" 2>/dev/null)
  hg=$(echo "$sc" | awk '{print $1}'); ag=$(echo "$sc" | awk '{print $3}')
  if [ "$side" = home ]; then p="$hg"; c="$ag"; else p="$ag"; c="$hg"; fi
  echo "$bot,$side,$rep,${p:-ERRO},${c:-ERRO}" > "$PARTDIR/$id"
  echo "  $id: ${p:-?} x ${c:-?}"
  rm -f "recordings/${id}.json"
}

# Se A e B são o mesmo bot, mede uma vez só (N reps × 2 lados = 2N partidas);
# senão mede os dois para o diff. Isso casa com a contagem esperada e evita
# reusar o mesmo id/porta/replay em paralelo (colisão).
if [ "$A" = "$B" ]; then bots=("$A"); else bots=("$A" "$B"); fi

# Semáforo: no máximo PARALLEL partidas ao mesmo tempo. `wait -n` libera um slot
# assim que qualquer uma termina, então o pool fica sempre cheio.
for bot in "${bots[@]}"; do
  for rep in $(seq 1 "$N"); do
    for side in home away; do
      run_one "$bot" "$side" "$rep" &
      while [ "$(jobs -r | wc -l)" -ge "$PARALLEL" ]; do wait -n; done
    done
  done
done
wait

# coleta os resultados (um arquivo por partida) no CSV, em ordem estável de id
cat "$PARTDIR"/* >> "$OUT" 2>/dev/null
rm -rf "$PARTDIR"

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
