"""
Converte as `lugo4py.Order` (protobuf) que as callbacks do my_bot retornam nos
dicts que `fastsim.step` consome.

Order tem um oneof {move|kick|catch|jump}; a velocity vem como direction
(magnitude ~100) + speed. O vetor real é `direction/|direction| * speed`.
fastsim quer (vx, vy) Cartesiano. Um jogador pode devolver 1-2 ordens
(ex.: [move, catch]) — juntamos num único dict.
"""
import math


def _vec(velocity):
    """direction(mag ~100)+speed -> (vx, vy) Cartesiano."""
    dx, dy, sp = velocity.direction.x, velocity.direction.y, velocity.speed
    n = math.hypot(dx, dy)
    if n == 0.0 or sp == 0.0:
        return (0.0, 0.0)
    return (dx / n * sp, dy / n * sp)


def orders_to_dict(order_list):
    """Junta a lista de Orders de UM jogador num dict do fastsim (ou None)."""
    d = {}
    for order in order_list or ():
        wo = order.WhichOneof("action")
        if wo == "move":
            d["move"] = _vec(order.move.velocity)
        elif wo == "kick":
            d["kick"] = _vec(order.kick.velocity)
        elif wo == "jump":
            d["jump"] = _vec(order.jump.velocity)
        elif wo == "catch":
            d["catch"] = True
    return d or None
