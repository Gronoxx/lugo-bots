"""Políticas para o simulador rápido.

`dummy_policy` replica o comportamento do bot oficial de referência
(the-dummies): todo mundo corre para a bola e chuta ao gol quando perto.
É o adversário-base para medir progresso.
"""

import math

import numpy as np

from fastsim import (BALL_MAX_SPEED, GOAL_MAX_Y, GOAL_MIN_Y, HOME, MAX_X,
                     MAX_Y, PLAYER_MAX_SPEED, TOUCH_RADIUS)


def attack_goal(side):
    return np.array([MAX_X if side == HOME else 0.0, MAX_Y / 2])


def defense_goal(side):
    return np.array([0.0 if side == HOME else MAX_X, MAX_Y / 2])


def _toward(frm, to, speed):
    d = to - frm
    n = math.hypot(d[0], d[1])
    if n < 1e-9:
        return (0.0, 0.0)
    return tuple(d / n * speed)


def dummy_policy(s, side):
    """Todos correm para a bola; quem tem a bola vai/chuta ao gol.

    É o baseline oficial. Rende 0x0 contra si mesmo, com a bola presa no
    meio-campo — o que confirma a fraqueza de mandar 11 jogadores à bola.
    """
    goal = attack_goal(side)
    orders = []
    for i in range(11):
        p = s.pos[side, i]
        if s.holder == (side, i):
            if math.hypot(*(goal - p)) < 6000:
                orders.append({"kick": _toward(p, goal, BALL_MAX_SPEED)})
            else:
                orders.append({"move": _toward(p, goal, PLAYER_MAX_SPEED)})
        else:
            orders.append({"move": _toward(p, s.ball_pos, PLAYER_MAX_SPEED),
                           "catch": True})
    return orders


BASE_FORMATION = np.array([
    [0.03, 0.50], [0.16, 0.20], [0.14, 0.40], [0.14, 0.60], [0.16, 0.80],
    [0.35, 0.30], [0.33, 0.50], [0.35, 0.70], [0.60, 0.25], [0.62, 0.50],
    [0.60, 0.75],
])


def make_shaped_policy(params=None):
    """Política com formação e papéis — a versão simulada do nosso bot.

    `params` permite otimizar os pesos por evolução:
      n_chasers, shift_x, shift_y, shoot_range, pass_gain
    """
    p = {
        "n_chasers": 2,
        "shift_x": 0.30,
        "shift_y": 0.35,
        "shoot_range": 6100.0,
        "aggression": 0.0,
    }
    if params:
        p.update(params)

    def policy(s, side):
        goal = attack_goal(side)
        orders = [None] * 11

        # quem chega primeiro na bola
        d_ball = np.hypot(s.pos[side, :, 0] - s.ball_pos[0],
                          s.pos[side, :, 1] - s.ball_pos[1])
        order_idx = np.argsort(d_ball)
        chasers = set(int(i) for i in order_idx if i != 0)
        chasers = set(list(chasers)[:int(p["n_chasers"])])

        # avanço da bola no nosso sentido de ataque
        adv = s.ball_pos[0] / MAX_X
        if side != HOME:
            adv = 1.0 - adv
        ball_y_frac = s.ball_pos[1] / MAX_Y

        for i in range(11):
            pos = s.pos[side, i]

            if s.holder == (side, i):
                if math.hypot(*(goal - pos)) < p["shoot_range"]:
                    # mira no canto mais distante do goleiro adversário
                    gk = s.pos[1 - side, 0]
                    y = GOAL_MIN_Y + 300 if gk[1] > MAX_Y / 2 else GOAL_MAX_Y - 300
                    target = np.array([goal[0], y])
                    orders[i] = {"kick": _toward(pos, target, BALL_MAX_SPEED)}
                else:
                    orders[i] = {"move": _toward(pos, goal, PLAYER_MAX_SPEED)}
                continue

            if i == 0:
                # goleiro: acompanha a bola em y, fica na linha
                gy = min(max(s.ball_pos[1], GOAL_MIN_Y + 150), GOAL_MAX_Y - 150)
                gx = defense_goal(side)[0]
                gx = gx + (300 if side == HOME else -300)
                orders[i] = {"move": _toward(pos, np.array([gx, gy]),
                                             PLAYER_MAX_SPEED), "catch": True}
                continue

            if i in chasers:
                orders[i] = {"move": _toward(pos, s.ball_pos, PLAYER_MAX_SPEED),
                             "catch": True}
                continue

            # formação deslizante
            bx, by = BASE_FORMATION[i]
            x_frac = bx + p["shift_x"] * (adv - 0.5) + 0.10 * p["aggression"]
            x_frac = min(max(x_frac, 0.02), 0.92)
            y_frac = by + p["shift_y"] * (ball_y_frac - 0.5)
            y_frac = min(max(y_frac, 0.06), 0.94)
            tx = x_frac * MAX_X if side == HOME else (1 - x_frac) * MAX_X
            target = np.array([tx, y_frac * MAX_Y])
            orders[i] = {"move": _toward(pos, target, PLAYER_MAX_SPEED),
                         "catch": True}
        return orders

    return policy
