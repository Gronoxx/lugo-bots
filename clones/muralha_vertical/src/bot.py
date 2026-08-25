"""Clone do bot 'BotAdversario2' (parede vertical), reproduzido do vídeo da competição.

Comportamento observado (partida BotAdversario2 vs BotAdversario3):
  - os 10 jogadores de linha formam UMA coluna vertical cobrindo toda a altura
    do campo, espaçados por número de camisa;
  - a coluna desliza em x, sempre do lado do próprio gol, recuando conforme a
    bola avança (linha a ~30% do próprio gol rumo à bola; quando a bola chega
    perto, o servidor os arqueia no limite da zona do gol de raio 1400);
  - o goleiro fica na linha do gol, acompanhando o y da bola;
  - NUNCA perseguem a bola nem atacam — a decisão é a mesma em todos os estados.
"""
import math
from abc import ABC
from typing import List

import lugo4py

MAX_X = lugo4py.max_x_coordinate     # 20000
MAX_Y = lugo4py.max_y_coordinate     # 10000
GOAL_MIN_Y = lugo4py.GOAL_MIN_Y      # 3500
GOAL_MAX_Y = lugo4py.GOAL_MAX_Y      # 6500
GOALKEEPER = 1
LINE_FRAC = 0.30                     # linha a 30% do próprio gol rumo à bola
MIN_MOVE_DIST = 12.0


def point(x, y):
    p = lugo4py.lugo.Point()
    p.x = int(max(0, min(MAX_X, x)))
    p.y = int(max(0, min(MAX_Y, y)))
    return p


class CloneBot(lugo4py.Bot, ABC):

    def _move(self, inspector, me, target):
        # lugo4py levanta erro em vetor de comprimento zero; contorna parando.
        if math.hypot(me.position.x - target.x, me.position.y - target.y) < MIN_MOVE_DIST:
            return inspector.make_order_move(point(me.position.x + 100, me.position.y), 0)
        return inspector.make_order_move_max_speed(target)

    def _formation(self, inspector) -> List[lugo4py.Order]:
        me = inspector.get_me()
        ball = inspector.get_ball()
        goal_x = self.mapper.get_defense_goal().get_center().x   # 0 (HOME) ou 20000 (AWAY)
        n = self.number
        if n == GOALKEEPER:
            y = max(GOAL_MIN_Y + 150, min(GOAL_MAX_Y - 150, ball.position.y))
            target = point(goal_x, y)
        else:
            x_line = goal_x + (ball.position.x - goal_x) * LINE_FRAC
            slot = n - 2                                         # 0..9
            # banda central ~2340..8030 (medida no vídeo do BotAdversario2): a coluna
            # NÃO cobre a altura cheia, concentra-se em frente à boca do gol.
            y = 2340.0 + slot / 9.0 * (8030.0 - 2340.0)
            target = point(x_line, y)
        return [self._move(inspector, me, target), inspector.make_order_catch()]

    # mesma decisão em TODOS os estados (é o que torna o BotAdversario2 tão simples)
    def on_holding(self, inspector) -> List[lugo4py.Order]:
        return self._formation(inspector)

    def on_supporting(self, inspector) -> List[lugo4py.Order]:
        return self._formation(inspector)

    def on_defending(self, inspector) -> List[lugo4py.Order]:
        return self._formation(inspector)

    def on_disputing(self, inspector) -> List[lugo4py.Order]:
        return self._formation(inspector)

    def as_goalkeeper(self, inspector, state) -> List[lugo4py.Order]:
        return self._formation(inspector)

    def getting_ready(self, snapshot):
        pass
