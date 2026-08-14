#!/usr/bin/env python3
"""Testes unitarios dos primitivos do planejador (Componente 2 do "quando passar").
Deterministicos (funcoes puras) -> imunes ao nao-determinismo das partidas.

Uso: PYTHONPATH=bot/src .venv/bin/python bench/test_planner.py
"""
import math
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "bot", "src"))
import planner as PL      # noqa: E402
import geometry as geo    # noqa: E402
import params as PR       # noqa: E402

NS = types.SimpleNamespace
_fail = [0]


def check(cond, msg):
    print(("  OK  " if cond else "  FALHOU  ") + msg)
    if not cond:
        _fail[0] += 1


def pl(num, x, y, vx=0.0, vy=0.0, sp=0.0):
    return NS(number=num, position=NS(x=x, y=y),
              velocity=NS(direction=NS(x=vx, y=vy), speed=sp))


def ball(x, y, vx=0.0, vy=0.0, sp=0.0):
    return NS(position=NS(x=x, y=y),
              velocity=NS(direction=NS(x=vx, y=vy), speed=sp))


GOAL = NS(x=20000, y=5000)


def test_exec_speed():
    print("exec_speed_toward:")
    check(abs(PL.exec_speed_toward(0, 0, 1, 0) - 400) < 1e-6,
          "bola assentada (c=0) => BALL_MAX (400)")
    check(abs(PL.exec_speed_toward(-100, 0, 1, 0) - 300) < 1e-6,
          "bola adversa 100 => 300 (first-touch reduz)")
    check(abs(PL.exec_speed_toward(100, 0, 1, 0) - 400) < 1e-6,
          "bola alinhada 100 => capa em 400")
    check(0 < PL.exec_speed_toward(0, -200, 1, 0) < 400,
          "bola perpendicular => reduz mas >0")


def test_leg_slack():
    print("leg_slack (theta=0 concorda em SINAL com can_be_intercepted):")
    me = NS(x=10000, y=5000)
    tgt = NS(x=13000, y=5000)
    clear = [pl(5, 3000, 1000)]                 # adversario longe da linha
    block = [pl(5, 11500, 5000)]                # adversario EM CIMA da linha
    sc = PL.leg_slack(me.x, me.y, tgt.x, tgt.y, clear, 300, 0.0, False)
    sb = PL.leg_slack(me.x, me.y, tgt.x, tgt.y, block, 300, 0.0, False)
    check(sc > 0 and not geo.can_be_intercepted(me, tgt, clear, 300, False),
          f"linha livre: slack>0 ({sc:.1f}) e veto=False")
    check(sb <= 0 and geo.can_be_intercepted(me, tgt, block, 300, False),
          f"linha bloqueada: slack<=0 ({sb:.1f}) e veto=True")
    print("leg_slack (horizonte theta INFLA o disco do defensor):")
    s0 = PL.leg_slack(me.x, me.y, tgt.x, tgt.y, [pl(5, 3000, 4000)], 300, 0.0, False)
    s5 = PL.leg_slack(me.x, me.y, tgt.x, tgt.y, [pl(5, 3000, 4000)], 300, 5.0, False)
    check(s5 < s0, f"theta maior reduz a folga (s0={s0:.1f} > s5={s5:.1f})")


def test_plan_pass():
    print("plan_pass (cenarios):")
    PR.P.update({"pass_lookahead": "depth2", "pass_control": "on"})
    me = pl(6, 8000, 5000)
    gk = pl(1, 20000, 5000)
    opps = [gk, pl(5, 3000, 5000)]
    res = PL.plan_pass(me, ball(8000, 5000), [pl(9, 13000, 5000), pl(1, 20000, 5000)],
                       opps, GOAL, gk, False)
    check(res is not None and res[0].x > me.position.x,
          "companheiro livre a frente => passa para frente")
    # muro de adversarios na unica linha
    wall = [gk] + [pl(n, 10500, 5000 - 400 + 200 * i)
                   for i, n in enumerate([2, 3, 4, 5, 6])]
    res2 = PL.plan_pass(me, ball(8000, 5000), [pl(9, 13000, 5000)], wall, GOAL, gk, False)
    check(res2 is None, "muro na linha => None (conduz)")
    # nosso goleiro (num 1) nunca e' receptor
    res3 = PL.plan_pass(me, ball(8000, 5000), [pl(1, 5000, 5000)], [gk], GOAL, gk, False)
    check(res3 is None, "so o nosso GK disponivel => nao passa p/ o GK")


def main():
    test_exec_speed()
    test_leg_slack()
    test_plan_pass()
    print(f"\n{'TODOS OK' if _fail[0] == 0 else str(_fail[0]) + ' FALHA(S)'}")
    sys.exit(1 if _fail[0] else 0)


if __name__ == "__main__":
    main()
