#!/usr/bin/env python3
"""
Mede o tempo de decisão do bot por turno.

A janela oficial (listening_duration) é 50ms. Se o bot estourar isso, o
servidor ignora suas ordens naquele turno — o jogador simplesmente para.
Este teste constrói um snapshot sintético realista e cronometra as
callbacks.
"""
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bot" / "src"))

import lugo4py
from lugo4py import Mapper
from lugo4py.protos import server_pb2

from my_bot import MyBot
from settings import MAPPER_COLS, MAPPER_ROWS, PLAYER_INITIAL_POSITIONS

MAX_X, MAX_Y = 20000, 10000


def make_snapshot(seed=0, holder_side=None, holder_num=10):
    rnd = random.Random(seed)
    snap = server_pb2.GameSnapshot()
    snap.turn = 100
    snap.state = server_pb2.GameSnapshot.State.LISTENING

    for side, team in ((server_pb2.Team.Side.HOME, snap.home_team),
                       (server_pb2.Team.Side.AWAY, snap.away_team)):
        team.side = side
        team.name = "HOME" if side == server_pb2.Team.Side.HOME else "AWAY"
        for n in range(1, 12):
            p = team.players.add()
            p.number = n
            p.team_side = side
            p.position.x = rnd.randint(500, MAX_X - 500)
            p.position.y = rnd.randint(500, MAX_Y - 500)
            p.velocity.direction.x = rnd.uniform(-1, 1)
            p.velocity.direction.y = rnd.uniform(-1, 1)
            p.velocity.speed = rnd.uniform(0, 100)
            p.init_position.x = p.position.x
            p.init_position.y = p.position.y

    snap.ball.position.x = rnd.randint(1000, MAX_X - 1000)
    snap.ball.position.y = rnd.randint(1000, MAX_Y - 1000)
    snap.ball.velocity.direction.x = rnd.uniform(-1, 1)
    snap.ball.velocity.direction.y = rnd.uniform(-1, 1)
    snap.ball.velocity.speed = rnd.uniform(0, 400)

    if holder_side is not None:
        team = snap.home_team if holder_side == server_pb2.Team.Side.HOME else snap.away_team
        src = [p for p in team.players if p.number == holder_num][0]
        snap.ball.holder.CopyFrom(src)
        snap.ball.position.CopyFrom(src.position)

    snap.shot_clock.team_side = server_pb2.Team.Side.HOME
    snap.shot_clock.remaining_turns = 200
    return snap


def bench(name, fn, snaps, *args):
    times = []
    for s in snaps:
        insp = lugo4py.GameSnapshotInspector(
            server_pb2.Team.Side.HOME, 10, s)
        t0 = time.perf_counter()
        fn(insp, *args)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    print(f"  {name:<16} média {statistics.mean(times):>6.2f}ms  "
          f"p50 {times[len(times)//2]:>6.2f}ms  "
          f"p95 {times[int(len(times)*0.95)]:>6.2f}ms  "
          f"máx {times[-1]:>6.2f}ms")
    return statistics.mean(times)


if __name__ == "__main__":
    N = 200
    mapper = Mapper(MAPPER_COLS, MAPPER_ROWS, server_pb2.Team.Side.HOME)
    pos = PLAYER_INITIAL_POSITIONS[10]
    bot = MyBot(server_pb2.Team.Side.HOME, 10,
                mapper.get_region(pos['Col'], pos['Row']).get_center(), mapper)

    gk_pos = PLAYER_INITIAL_POSITIONS[1]
    gk = MyBot(server_pb2.Team.Side.HOME, 1,
               mapper.get_region(gk_pos['Col'], gk_pos['Row']).get_center(), mapper)

    print(f"Latência por turno ({N} snapshots aleatórios) — orçamento: 50ms\n")

    loose = [make_snapshot(i) for i in range(N)]
    mine = [make_snapshot(i, server_pb2.Team.Side.HOME, 10) for i in range(N)]
    theirs = [make_snapshot(i, server_pb2.Team.Side.AWAY, 10) for i in range(N)]
    mate = [make_snapshot(i, server_pb2.Team.Side.HOME, 9) for i in range(N)]

    worst = 0
    worst = max(worst, bench("on_disputing", bot.on_disputing, loose))
    worst = max(worst, bench("on_holding", bot.on_holding, mine))
    worst = max(worst, bench("on_defending", bot.on_defending, theirs))
    worst = max(worst, bench("on_supporting", bot.on_supporting, mate))
    worst = max(worst, bench("as_goalkeeper", gk.as_goalkeeper, loose,
                             lugo4py.PLAYER_STATE.DISPUTING_THE_BALL))

    print(f"\n  pior média: {worst:.1f}ms de 50ms "
          f"({'OK' if worst < 25 else 'ATENÇÃO' if worst < 50 else 'ESTOURA'})")
