"""
Roda o my_bot EXATO como uma política do fastsim: `policy(state, side) -> 11 dicts`.

Constrói um GameSnapshot a partir do State (snapshot.py), cria um
GameSnapshotInspector real por jogador, replica o dispatch de estado do servidor
(igual a sim/test_remote.py:45-62), chama a callback certa e converte as Orders
(orders.py). Assim o my_bot decide dentro do simulador, sem gRPC/Docker.

Uso:
    from heuristic_policy import make_heuristic_policy
    import fastsim as fs
    pol = make_heuristic_policy()
    fs.play(pol, pol, turns=6000)
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for _p in (_REPO / "sim", _REPO / "bot" / "src", Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import lugo4py
from lugo4py import Mapper

import fastsim as fs
from my_bot import MyBot
from settings import MAPPER_COLS, MAPPER_ROWS, PLAYER_INITIAL_POSITIONS

from snapshot import state_to_snapshot
from orders import orders_to_dict

_SIDES = (fs.HOME, fs.AWAY)   # 0, 1


def _build_bots(bot_factory):
    """Um bot por (lado, número) + as posições iniciais por lado (mapper espelha
    para o AWAY, exatamente como sim/test_remote.py:29-42)."""
    bots = {}
    init_positions = [[None] * 11, [None] * 11]   # [side][idx] -> (x, y)
    for side in _SIDES:
        mapper = Mapper(MAPPER_COLS, MAPPER_ROWS, side)
        for number in range(1, 12):
            pos = PLAYER_INITIAL_POSITIONS[number]
            center = mapper.get_region(pos["Col"], pos["Row"]).get_center()
            bots[(side, number)] = bot_factory(side, number, center, mapper)
            init_positions[side][number - 1] = (center.x, center.y)
    return bots, init_positions


def make_heuristic_policy(bot_factory=MyBot):
    """Retorna `policy(state, side) -> lista de 11 dicts` que roda o my_bot."""
    bots, init_positions = _build_bots(bot_factory)

    def policy(state, side):
        snap = state_to_snapshot(state, init_positions)
        orders = [None] * 11
        for number in range(1, 12):
            insp = lugo4py.GameSnapshotInspector(side, number, snap)
            bot = bots[(side, number)]
            ball = insp.get_ball()
            holder = ball.holder if ball.HasField("holder") else None

            if number == 1:
                st = (lugo4py.PLAYER_STATE.DISPUTING_THE_BALL if holder is None
                      else lugo4py.PLAYER_STATE.DEFENDING)
                out = bot.as_goalkeeper(insp, st)
            elif holder is None:
                out = bot.on_disputing(insp)
            elif holder.team_side == side:
                out = (bot.on_holding(insp) if holder.number == number
                       else bot.on_supporting(insp))
            else:
                out = bot.on_defending(insp)

            orders[number - 1] = orders_to_dict(out)
        return orders

    return policy
