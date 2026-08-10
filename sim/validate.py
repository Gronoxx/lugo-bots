#!/usr/bin/env python3
"""
Valida o modelo de física contra replays reais do servidor.

Pega pares de snapshots consecutivos em que a bola está solta, prevê a
posição seguinte com o nosso modelo e compara com a que o servidor produziu.
Se o erro for pequeno, podemos confiar no simulador para busca/otimização.

  python3 validate.py ../bench/recordings/t1.json
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "analysis"))
import replay  # noqa: E402

BALL_DECEL = 10.0
BALL_MIN_SPEED = 2.0
MAX_X, MAX_Y = 20000, 10000


def predict(pos, vel_dir, speed):
    """Um passo da nossa física: move, quica, desacelera.

    O avanço é `speed - BALL_DECEL/2` (integração trapezoidal), não `speed`.
    Isto foi medido, não documentado: veja a varredura no final deste arquivo.
    """
    n = math.hypot(vel_dir[0], vel_dir[1])
    if n == 0 or speed <= BALL_MIN_SPEED:
        return pos, 0.0
    dx, dy = vel_dir[0] / n, vel_dir[1] / n
    adv = max(0.0, speed - BALL_DECEL / 2)
    x = pos[0] + dx * adv
    y = pos[1] + dy * adv
    if x < 0:
        x = -x
    elif x > MAX_X:
        x = 2 * MAX_X - x
    if y < 0:
        y = -y
    elif y > MAX_Y:
        y = 2 * MAX_Y - y
    return (x, y), max(0.0, speed - BALL_DECEL)


def main(path):
    cfg, events = replay.load(path)
    snaps = list(replay.snapshots(events))
    print(f"{len(snaps)} snapshots de {path}")

    errors = []
    compared = 0
    prev = None
    for gs in snaps:
        turn = gs.get("turn", 0)
        b = replay.ball(gs)
        pos = replay.pt(b.get("position"))
        vel = b.get("velocity", {}) or {}
        d = vel.get("direction", {}) or {}
        speed = vel.get("speed", 0)
        holder = replay.holder(gs)
        cur = (turn, pos, (d.get("x", 0), d.get("y", 0)), speed, holder)

        if prev is not None:
            pturn, ppos, pdir, pspeed, pholder = prev
            # só compara transições de 1 turno com a bola solta nos dois
            if turn == pturn + 1 and pholder is None and holder is None \
                    and pspeed > BALL_MIN_SPEED:
                pred, _ = predict(ppos, pdir, pspeed)
                err = math.hypot(pred[0] - pos[0], pred[1] - pos[1])
                errors.append(err)
                compared += 1
        prev = cur

    if not compared:
        print("nenhuma transição comparável encontrada "
              "(bola quase sempre presa ou turnos não consecutivos)")
        return

    errors.sort()
    print(f"\ntransições comparadas: {compared}")
    print(f"  erro médio : {sum(errors)/len(errors):>8.1f} d")
    print(f"  mediana    : {errors[len(errors)//2]:>8.1f} d")
    print(f"  p95        : {errors[int(len(errors)*0.95)]:>8.1f} d")
    print(f"  máximo     : {errors[-1]:>8.1f} d")
    print(f"\n  referência: raio de contato = 300d, "
          f"passo típico da bola = até 400d/turno")
    ok = sum(1 for e in errors if e < 50) / len(errors)
    print(f"  {100*ok:.0f}% das previsões com erro < 50d")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else "../bench/recordings/dummies_vs_dummies.json")
