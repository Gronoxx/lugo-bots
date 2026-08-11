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
#
# Paralelismo: até PARALLEL partidas ao mesmo tempo (padrão 3). Cada partida roda
# no seu próprio subshell, então HOME_PARAMS/AWAY_PARAMS (o gene em teste) ficam
# ISOLADOS por partida mesmo em paralelo — não vazam entre valores concorrentes.
# Requer gen_compose.py sem portas publicadas (default).
#   REPS=4 PARALLEL=3 OPP=lugobots/level-1:latest ./sweep.sh mybot:v9 shot_min_gap 500 900 1300 1700
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"

BOT="$1"; PARAM="$2"; shift 2
VALUES=("$@")
N="${REPS:-3}"
OPP="${OPP:-lugobots/the-dummies-go:latest}"
# adversário no nome do arquivo: varredura vs level-1 é experimento diferente de
# vs the-dummies — não devem colidir/sobrescrever (o sweep_${PARAM}.csv antigo,
# versionado, era vs the-dummies).
OPPTAG=$(printf '%s' "$OPP" | sed 's|.*/||; s|:.*||')   # lugobots/level-1:latest -> level-1
OUT="results/sweep_${PARAM}_${OPPTAG}.csv"

mkdir -p results
echo "parametro,valor,lado,rep,gols_pro,gols_contra" > "$OUT"

PARALLEL="${PARALLEL:-3}"
PARTDIR="results/.sweep_parts_$$"
mkdir -p "$PARTDIR"

# Roda UMA partida com o gene fixado em $val e grava o resultado num arquivo
# próprio. O `export HOME_PARAMS/AWAY_PARAMS` fica DENTRO da função: como ela é
# chamada em background (subshell), cada partida tem seu próprio env — valores
# concorrentes não se misturam. É o docker-compose de run_match.sh que resolve
# ${HOME_PARAMS} do ambiente, então o isolamento por subshell é o que importa.
run_one() {
  local val="$1" side="$2" rep="$3"
  local id h a sc hg ag p c
  id="sw_${PARAM}_${val}_${side}_${rep}"
  if [ "$side" = home ]; then
    h="$BOT"; a="$OPP"; export HOME_PARAMS="{\"$PARAM\":$val}"; unset AWAY_PARAMS
  else
    h="$OPP"; a="$BOT"; export AWAY_PARAMS="{\"$PARAM\":$val}"; unset HOME_PARAMS
  fi
  if ! TIMER_MODE=wait ./run_match.sh "$h" "$a" "$id" >/dev/null 2>&1; then
    echo "$PARAM,$val,$side,$rep,ERRO,ERRO" > "$PARTDIR/$id"; return
  fi
  sc=$(python3 match_done.py "recordings/${id}.json" 2>/dev/null)
  hg=$(echo "$sc" | awk '{print $1}'); ag=$(echo "$sc" | awk '{print $3}')
  if [ "$side" = home ]; then p="$hg"; c="$ag"; else p="$ag"; c="$hg"; fi
  echo "$PARAM,$val,$side,$rep,${p:-ERRO},${c:-ERRO}" > "$PARTDIR/$id"
  echo "  $PARAM=$val [$side #$rep]: ${p:-?} x ${c:-?}"
  rm -f "recordings/${id}.json"
}

# Semáforo: no máximo PARALLEL partidas ao mesmo tempo.
for val in "${VALUES[@]}"; do
  for rep in $(seq 1 "$N"); do
    for side in home away; do
      run_one "$val" "$side" "$rep" &
      while [ "$(jobs -r | wc -l)" -ge "$PARALLEL" ]; do wait -n; done
    done
  done
done
wait

# coleta os resultados (um arquivo por partida) no CSV
cat "$PARTDIR"/* >> "$OUT" 2>/dev/null
rm -rf "$PARTDIR"

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
