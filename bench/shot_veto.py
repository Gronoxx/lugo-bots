#!/usr/bin/env python3
"""POR QUE O BOT NÃO CHUTA — autópsia do portão de finalização.

Para cada turno em que NÓS seguramos a bola dentro do alcance de chute,
re-executa `_best_shot_target` e classifica o motivo de NÃO haver chute:
  LINHA BLOQUEADA  : todos os 9 alvos têm a linha interceptável (defensor no meio)
  FOLGA INSUFICIENTE: linha livre, mas o goleiro cobre (gap < shot_min_gap)
  FORA DE ALCANCE  : d > MAX_KICK_RANGE
  AUTORIZADO       : houve alvo válido (o bot chutaria)

Uso: BOT_PARAMS='<genoma>' PYTHONPATH=bot/src:analysis python bench/shot_veto.py <replays...>
"""
import glob
import math
import sys

import lugo4py
import replay as R
import geometry as geo
import tactics as tac  # noqa: F401
from my_bot import MyBot
from params import P


class D:
    def __init__(self, **k):
        self.__dict__.update(k)


def vel_of(d):
    v = d.get("velocity") or {}
    dr = v.get("direction") or {}
    return D(direction=D(x=dr.get("x", 0.0), y=dr.get("y", 0.0)),
             speed=v.get("speed", 0.0))


def pobj(p):
    x, y = R.pt(p.get("position"))
    return D(number=p.get("number", 0), position=D(x=x, y=y), velocity=vel_of(p))


class Goal:
    def get_center(self):
        return geo.point(20000, 5000)


class Mapper:
    def get_attack_goal(self):
        return Goal()

    def get_defense_goal(self):
        class G:
            def get_center(self):
                return geo.point(0, 5000)
        return G()


class Snap:
    def __init__(self, turn):
        self.turn = turn
        self.turns_ball_in_goal_zone = 0


class Insp:
    def __init__(self, me, home, away, ball, gk, turn):
        self._me, self._h, self._a, self._b, self._gk = me, home, away, ball, gk
        self._t = turn

    def get_me(self): return self._me
    def get_my_team_players(self): return self._h
    def get_opponent_players(self): return self._a
    def get_ball(self): return self._b
    def get_opponent_goalkeeper(self): return self._gk
    def get_my_team_side(self): return lugo4py.TeamSide.HOME
    def get_snapshot(self): return Snap(self._t)
    def get_turn(self): return self._t
    def get_my_team(self): return D(score=0)
    def get_opponent_team(self): return D(score=0)


def motivo(bot, insp, me, gk, opponents, goal_x=20000.0):
    """Reproduz a triagem de _best_shot_target e devolve o motivo."""
    from geometry import (GOAL_MAX_Y, GOAL_MIN_Y, BALL_MAX_SPEED, dist, point,
                          can_be_intercepted, turns_for_ball)
    n_alcance = n_bloq = n_folga = 0
    for i in range(9):
        frac = i / 8
        m = P["shot_post_margin"]
        y = GOAL_MIN_Y + m + frac * (GOAL_MAX_Y - GOAL_MIN_Y - 2 * m)
        target = point(goal_x, y)
        d = dist(me.position, target)
        if d > geo.MAX_KICK_RANGE:
            n_alcance += 1
            continue
        others = [o for o in opponents if gk is None or o.number != gk.number]
        if can_be_intercepted(me.position, target, others, BALL_MAX_SPEED, False):
            n_bloq += 1
            continue
        if turns_for_ball(BALL_MAX_SPEED, d) == math.inf:
            n_alcance += 1
            continue
        if gk is not None:
            gap = abs(gk.position.y - target.y)
            if gap < P["shot_min_gap"]:
                n_folga += 1
                continue
        return "AUTORIZADO", (n_bloq, n_folga, n_alcance)
    if n_bloq >= max(n_folga, n_alcance):
        return "LINHA BLOQUEADA", (n_bloq, n_folga, n_alcance)
    if n_folga >= n_alcance:
        return "FOLGA INSUFICIENTE", (n_bloq, n_folga, n_alcance)
    return "FORA DE ALCANCE", (n_bloq, n_folga, n_alcance)


def main():
    files = []
    for pat in sys.argv[1:]:
        files += sorted(glob.glob(pat))
    bot = MyBot.__new__(MyBot)
    bot.mapper = Mapper()
    from collections import Counter
    tot = Counter()
    for path in files:
        _cfg, events = R.load(path)
        seen = set()
        for gs in R.snapshots(events):
            t = gs.get("turn", 0)
            if t in seen or gs.get("state") != "LISTENING":
                continue
            seen.add(t)
            hold = R.holder(gs)
            if not hold or hold[0] != "HOME":
                continue
            home = [pobj(p) for p in R.players(gs, "home")]
            away = [pobj(p) for p in R.players(gs, "away")]
            me = next((p for p in home if p.number == hold[1]), None)
            if me is None or me.number == 1:
                continue
            gc = geo.point(20000, 5000)
            from geometry import dist
            if dist(me.position, gc) > P["dangerous_shot_range"]:
                tot["fora do gate de distancia"] += 1
                continue
            gk = next((p for p in away if p.number == 1), None)
            bx, by = R.ball_pos(gs)
            ball = D(position=D(x=bx, y=by), velocity=vel_of(R.ball(gs)))
            insp = Insp(me, home, away, ball, gk, t)
            bot.number = me.number
            try:
                r, _ = motivo(bot, insp, me, gk, away)
            except Exception as e:
                r = f"erro {type(e).__name__}"
            tot[r] += 1
    n = sum(tot.values())
    print(f"{len(files)} replays | {n} turnos com a bola nossa (jogador de linha)")
    for k, v in tot.most_common():
        print(f"  {k:26s} {v:6d}  ({100.0*v/max(1,n):5.1f}%)")


if __name__ == "__main__":
    main()
