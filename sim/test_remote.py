#!/usr/bin/env python3
"""
Valida o controlador determinístico: roda a MESMA partida duas vezes e compara.

Se os dois placares (e a trajetória) forem idênticos, temos treino
reprodutível — e a evolução passa a medir qualidade em vez de sorte.

Uso:
  docker run -d --name lugo_rem -p 5001:5000 lugobots/server:latest \
      play --dev-mode --timer-mode=remote --headless --quiet
  ../.venv/bin/python test_remote.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot" / "src"))

import lugo4py
from lugo4py import Mapper

from remote_match import run_match, HOME
from my_bot import MyBot
from settings import MAPPER_COLS, MAPPER_ROWS, PLAYER_INITIAL_POSITIONS

ADDRESS = "localhost:5001"
TURNS = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def build():
    """Cria um MyBot por (lado, número) e a formação inicial."""
    bots, formation = {}, {}
    for side in (lugo4py.TeamSide.HOME, lugo4py.TeamSide.AWAY):
        mapper = Mapper(MAPPER_COLS, MAPPER_ROWS, side)
        for number in range(1, 12):
            pos = PLAYER_INITIAL_POSITIONS[number]
            center = mapper.get_region(pos["Col"], pos["Row"]).get_center()
            bots[(side, number)] = MyBot(side, number, center, mapper)
            # a formação é POR LADO: o mapper espelha as coordenadas, e usar as
            # do HOME para o AWAY cai na metade adversária -> o servidor recusa
            # o registro com "invalid initial position"
            formation[(side, number)] = center
    return bots, formation


def make_policy(bots):
    def policy(side, number, inspector):
        bot = bots[(side, number)]
        me = inspector.get_me()
        ball = inspector.get_ball()
        holder = ball.holder if ball.HasField("holder") else None

        if number == 1:
            state = (lugo4py.PLAYER_STATE.DISPUTING_THE_BALL if holder is None
                     else lugo4py.PLAYER_STATE.DEFENDING)
            return bot.as_goalkeeper(inspector, state)
        if holder is None:
            return bot.on_disputing(inspector)
        if holder.team_side == side:
            return (bot.on_holding(inspector) if holder.number == number
                    else bot.on_supporting(inspector))
        return bot.on_defending(inspector)
    return policy


if __name__ == "__main__":
    resultados = []
    for rodada in (1, 2):
        bots, formation = build()
        h, a, t = run_match(ADDRESS, make_policy(bots), formation,
                            turns=TURNS, debug=(rodada == 1))
        print(f"rodada {rodada}: {h} x {a}  ({t} turnos)")
        resultados.append((h, a, t))

    print()
    if any(t == 0 for _, _, t in resultados):
        print("FALHA: a partida não avançou nenhum turno — não há o que comparar.")
        print("  (duas falhas idênticas NÃO são determinismo)")
        sys.exit(1)
    if resultados[0] == resultados[1]:
        print("DETERMINÍSTICO: as duas rodadas deram exatamente o mesmo resultado")
        print("  => comparações pareadas na evolução medem qualidade, não sorte")
    else:
        print("NÃO determinístico: as rodadas divergiram")
        print(f"  {resultados[0]} vs {resultados[1]}")
