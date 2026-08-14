#!/usr/bin/env bash
# Portao de reprodutibilidade do Componente 1 ("quando passar"): prova que o
# mybot:qp (worktree quando-passar, genes de status DEFAULT-OFF) tem o caminho
# default byte-a-byte identico ao mybot:fa (base Fase A). wait mode = determinista.
set -uo pipefail
cd "$(dirname "$0")"

run() { TIMER_MODE=wait ./run_match.sh "$1" "$2" "$3" >/dev/null 2>&1; }

gate() {
  local opp="$1" tag="$2"
  run mybot:qp "$opp"        "gate_qp_${tag}_home" &
  run mybot:fa "$opp"        "gate_fa_${tag}_home" &
  run "$opp"   mybot:qp      "gate_qp_${tag}_away" &
  run "$opp"   mybot:fa      "gate_fa_${tag}_away" &
  wait
  for side in home away; do
    local a="recordings/gate_qp_${tag}_${side}.json"
    local b="recordings/gate_fa_${tag}_${side}.json"
    if [ ! -s "$a" ] || [ ! -s "$b" ]; then
      echo "ERRO: replay ausente ${tag} ${side} (a=$(test -s "$a" && echo ok || echo FALTA) b=$(test -s "$b" && echo ok || echo FALTA))"
    elif cmp -s "$a" "$b"; then
      echo "IDENTICO: ${tag} ${side}  (qp default == fa default)"
    else
      echo "DIVERGE!!: ${tag} ${side}  -> $(python3 match_done.py "$a") vs $(python3 match_done.py "$b")"
    fi
  done
}

gate "lugobots/the-dummies-go:latest" dummies
gate "lugobots/level-1:latest" level1
echo "PORTAO_FIM"
