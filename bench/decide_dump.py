#!/usr/bin/env python3
"""Despeja a DECISAO real de _best_pass (a ordem de chute) para cada turno em
que o HOME segura a bola num replay. Funcao PURA do snapshot => determinista,
independente do (nao-)determinismo das partidas.

Uso p/ portao de INERCIA (off = v9), sob nao-determinismo do wait mode:
  PYTHONPATH=<base bot/src>:<base analysis> python bench/decide_dump.py R.json > base.txt
  PYTHONPATH=<qp   bot/src>:<qp   analysis> python bench/decide_dump.py R.json > qp.txt
  diff base.txt qp.txt   # vazio => _best_pass default e' byte-a-byte igual

Reconstroi o inspector/bot minimo que _best_pass exige. HOME ataca +X.
"""
import sys

import replay as R
import geometry as geo
import tactics as tac  # noqa: F401  (garante que my_bot importa igual)
from my_bot import MyBot


class D:
    def __init__(self, **k):
        self.__dict__.update(k)


def vel_of(d):
    v = d.get("velocity") or {}
    dr = v.get("direction") or {}
    return D(direction=D(x=dr.get("x", 0.0), y=dr.get("y", 0.0)),
             speed=v.get("speed", 0.0))


def player_obj(p):
    x, y = R.pt(p.get("position"))
    return D(number=p.get("number", 0), position=D(x=x, y=y), velocity=vel_of(p))


def ball_obj(gs):
    bx, by = R.ball_pos(gs)
    return D(position=D(x=bx, y=by), velocity=vel_of(R.ball(gs)))


class MockGoal:
    def get_center(self):
        return geo.point(20000, 5000)      # HOME ataca +X


class MockMapper:
    def get_attack_goal(self):
        return MockGoal()


class MockInspector:
    def __init__(self, me, home, away, ball, gk):
        self._me, self._home, self._away = me, home, away
        self._ball, self._gk = ball, gk

    def get_me(self):
        return self._me

    def get_my_team_players(self):
        return self._home

    def get_opponent_players(self):
        return self._away

    def get_ball(self):
        return self._ball

    def get_opponent_goalkeeper(self):
        return self._gk


def decide(gs, bot):
    hold = R.holder(gs)
    if not hold or hold[0] != "HOME":
        return None
    hnum = hold[1]
    home = [player_obj(p) for p in R.players(gs, "home")]
    away = [player_obj(p) for p in R.players(gs, "away")]
    me = next((p for p in home if p.number == hnum), None)
    if me is None:
        return None
    gk = next((p for p in away if p.number == 1), None)
    insp = MockInspector(me, home, away, ball_obj(gs), gk)
    bot.number = hnum
    return bot._best_pass(insp)


def main():
    path = sys.argv[1]
    _cfg, events = R.load(path)
    bot = MyBot.__new__(MyBot)
    bot.mapper = MockMapper()
    seen = set()
    for gs in R.snapshots(events):
        t = gs.get("turn", 0)
        if t in seen or gs.get("state") != "LISTENING":
            continue
        seen.add(t)
        try:
            order = decide(gs, bot)
        except Exception as e:
            print(f"{t} ERRO {type(e).__name__}: {e}")
            continue
        if order is None:
            print(f"{t} None")
        else:
            k = order.kick.velocity
            print(f"{t} {k.direction.x:.6f} {k.direction.y:.6f} {k.speed:.6f}")


if __name__ == "__main__":
    main()
