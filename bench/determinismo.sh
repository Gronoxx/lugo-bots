#!/usr/bin/env bash
# Roda o MESMO bot duas vezes com a MESMA configuração em wait mode e compara
# os replays byte a byte. Se forem idênticos, o servidor é determinístico nesse
# modo e podemos usar comparações pareadas — o ruído de medição desaparece.
set -uo pipefail
cd "$(dirname "$0")"
for i in 1 2; do
  TIMER_MODE=wait ./run_match.sh mybot:v7 lugobots/the-dummies-go:latest det_$i >/dev/null 2>&1
  echo "det_$i: $(python3 match_done.py recordings/det_$i.json)"
done
echo
if cmp -s recordings/det_1.json recordings/det_2.json; then
  echo "RESULTADO: replays IDENTICOS -> servidor determinístico em wait mode"
  echo "  => comparações pareadas eliminam o ruído; evolução fica barata"
else
  echo "RESULTADO: replays DIFERENTES -> há não-determinismo mesmo em wait"
  python3 - <<'PY'
import sys; sys.path.insert(0,'../analysis')
import replay, math
a=list(replay.snapshots(replay.load('recordings/det_1.json')[1]))
b=list(replay.snapshots(replay.load('recordings/det_2.json')[1]))
for t in range(1, min(len(a),len(b))):
    pa,pb=replay.ball_pos(a[t]),replay.ball_pos(b[t])
    d=math.hypot(pa[0]-pb[0],pa[1]-pb[1])
    if d>0.5:
        print(f"  primeira divergência da bola: snapshot {t}, {d:.1f}d")
        break
else: print("  bola idêntica em todos os snapshots comparados")
PY
fi
