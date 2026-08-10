#!/usr/bin/env python3
"""
Diz se um replay já contém o fim da partida.

Existe porque o servidor NÃO encerra o container ao terminar a partida:
o replay ganha o evento `game_over`, mas `docker inspect` segue reportando
`Running=true`. Detectar o fim pelo container faz cada partida pendurar até o
timeout (~20 min em vez de ~3).

Lê apenas as últimas linhas do arquivo — o replay tem ~18 MB e é consultado em
laço, então decodificá-lo inteiro a cada consulta seria caro.

  python3 match_done.py <replay.json>   # sai 0 se terminou, 1 se não

Imprime o placar quando terminou.
"""
import base64
import gzip
import json
import sys
from pathlib import Path

TAIL_BYTES = 200_000   # o bastante para conter as últimas dezenas de eventos


def tail_lines(path: Path, n_bytes=TAIL_BYTES):
    size = path.stat().st_size
    with path.open("rb") as f:
        f.seek(max(0, size - n_bytes))
        chunk = f.read()
    # a primeira linha pode estar cortada ao meio
    return chunk.split(b"\n")[1:] if size > n_bytes else chunk.split(b"\n")


def main(path_str: str) -> int:
    path = Path(path_str)
    if not path.exists() or path.stat().st_size == 0:
        return 1

    score = None
    done = False
    for raw in tail_lines(path):
        if not raw.strip():
            continue
        try:
            ev = json.loads(gzip.decompress(base64.b64decode(raw)).decode())
        except Exception:
            continue          # linha truncada — normal ao ler o fim do arquivo
        if "game_over" in ev:
            done = True
        gs = ev.get("game_snapshot")
        if gs:
            h = (gs.get("home_team") or {}).get("score", 0)
            a = (gs.get("away_team") or {}).get("score", 0)
            score = (h, a)

    if done:
        if score:
            print(f"{score[0]} x {score[1]}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
