#!/usr/bin/env python3
"""
Testa as callbacks do bot em situações-limite.

Motivação: o template envolve cada callback em try/except. Uma exceção não
derruba o bot — ela o deixa PARADO naquele turno, silenciosamente. Dois bugs
assim já apareceram (`is_ball_holder` sem argumento, vetor de comprimento
zero). Este teste falha alto em vez de deixar passar.

  ../.venv/bin/python test_edge_cases.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot" / "src"))

import lugo4py
from lugo4py import Mapper
from lugo4py.protos import server_pb2

from latency import make_snapshot
from my_bot import MyBot
from settings import MAPPER_COLS, MAPPER_ROWS, PLAYER_INITIAL_POSITIONS

MAX_X, MAX_Y = 20000, 10000
HOME = server_pb2.Team.Side.HOME


def bot_for(number):
    mapper = Mapper(MAPPER_COLS, MAPPER_ROWS, HOME)
    pos = PLAYER_INITIAL_POSITIONS[number]
    return MyBot(HOME, number,
                 mapper.get_region(pos['Col'], pos['Row']).get_center(), mapper)


def place(snap, side, number, x, y):
    team = snap.home_team if side == HOME else snap.away_team
    for p in team.players:
        if p.number == number:
            p.position.x, p.position.y = int(x), int(y)
            return p


CASES = {}


def case(name):
    def deco(fn):
        CASES[name] = fn
        return fn
    return deco


@case("bola exatamente sobre o jogador")
def _(snap):
    p = place(snap, HOME, 10, 5000, 5000)
    snap.ball.position.x, snap.ball.position.y = 5000, 5000
    snap.ball.velocity.speed = 0
    snap.ball.velocity.direction.x = 0
    snap.ball.velocity.direction.y = 0


@case("todos empilhados no mesmo ponto")
def _(snap):
    for n in range(1, 12):
        place(snap, HOME, n, 10000, 5000)
        place(snap, server_pb2.Team.Side.AWAY, n, 10000, 5000)
    snap.ball.position.x, snap.ball.position.y = 10000, 5000


@case("bola no canto do campo")
def _(snap):
    snap.ball.position.x, snap.ball.position.y = 0, 0
    snap.ball.velocity.speed = 400


@case("bola parada com direção nula")
def _(snap):
    snap.ball.velocity.speed = 0
    snap.ball.velocity.direction.x = 0
    snap.ball.velocity.direction.y = 0


@case("jogador na posição do alvo de formação")
def _(snap):
    # posição de formação do 10 com a bola no centro
    place(snap, HOME, 10, 12400, 5000)
    snap.ball.position.x, snap.ball.position.y = 10000, 5000


@case("bola na linha do gol próprio")
def _(snap):
    snap.ball.position.x, snap.ball.position.y = 100, 5000
    snap.ball.velocity.speed = 390
    snap.ball.velocity.direction.x = -1
    snap.ball.velocity.direction.y = 0


@case("sem adversários visíveis")
def _(snap):
    del snap.away_team.players[:]


def run():
    failures = []
    checked = 0
    for name, setup in CASES.items():
        for holder in (None, "mine", "theirs", "mate"):
            snap = make_snapshot(7)
            setup(snap)
            if holder == "mine":
                src = [p for p in snap.home_team.players if p.number == 10][0]
                snap.ball.holder.CopyFrom(src)
                snap.ball.position.CopyFrom(src.position)
            elif holder == "theirs":
                src = [p for p in snap.away_team.players if p.number == 5] or None
                if src:
                    snap.ball.holder.CopyFrom(src[0])
            elif holder == "mate":
                src = [p for p in snap.home_team.players if p.number == 9][0]
                snap.ball.holder.CopyFrom(src)

            for number, method, args in (
                    (10, "on_disputing", ()),
                    (10, "on_holding", ()),
                    (10, "on_defending", ()),
                    (10, "on_supporting", ()),
                    (1, "as_goalkeeper",
                     (lugo4py.PLAYER_STATE.DISPUTING_THE_BALL,)),
            ):
                bot = bot_for(number)
                insp = lugo4py.GameSnapshotInspector(HOME, number, snap)
                checked += 1
                try:
                    orders = getattr(bot, method)(insp, *args)
                except Exception as e:
                    failures.append(f"{name} [{holder}] {method}: EXCEÇÃO {e}")
                    continue
                if not orders:
                    failures.append(
                        f"{name} [{holder}] {method}: NENHUMA ORDEM "
                        f"(jogador ficaria parado)")

    print(f"{checked} combinações testadas")
    if failures:
        print(f"\n{len(failures)} FALHAS:")
        for f in failures[:25]:
            print(f"  - {f}")
        return 1
    print("todas as callbacks produzem ordens em todos os casos-limite")
    return 0


if __name__ == "__main__":
    sys.exit(run())
