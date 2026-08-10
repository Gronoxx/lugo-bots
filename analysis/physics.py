"""
Modelo de física do Lugo, derivado das specs oficiais (lugo4py/src/specs.py).

Unidades: d (distância), f (frame/turn). 20 fps.
Este módulo é a base analítica do bot: tudo que decidimos (chutar, passar,
interceptar, posicionar) depende de prever o movimento da bola com precisão.
"""

import math

# ---- constantes oficiais ----
BASE_UNIT = 100
MAX_X = 200 * BASE_UNIT          # 20000
MAX_Y = 100 * BASE_UNIT          # 10000
GOAL_WIDTH = 30 * BASE_UNIT      # 3000
GOAL_MIN_Y = (MAX_Y - GOAL_WIDTH) / 2   # 3500
GOAL_MAX_Y = GOAL_MIN_Y + GOAL_WIDTH    # 6500
GOAL_ZONE_RANGE = 14 * BASE_UNIT        # 1400

PLAYER_SIZE = 4 * BASE_UNIT      # 400 (diâmetro)
PLAYER_MAX_SPEED = 100.0         # d/f
BALL_SIZE = 2 * BASE_UNIT        # 200
BALL_MAX_SPEED = 4.0 * BASE_UNIT # 400 d/f
BALL_MIN_SPEED = 2.0
BALL_DECELERATION = 10.0         # d/f²
BALL_TIME_IN_GOAL_ZONE = 40

GOALKEEPER_JUMP_DURATION = 3
GOALKEEPER_JUMP_SPEED = 2 * PLAYER_MAX_SPEED  # 200
GOALKEEPER_NUMBER = 1

SHOT_CLOCK_TIME = 300
GAME_TURNS = 1200
FPS = 20

# raio efetivo de contato bola-jogador
TOUCH_RADIUS = (PLAYER_SIZE + BALL_SIZE) / 2  # 300


def ball_travel(v0: float) -> tuple[float, int]:
    """Distância total percorrida e nº de turnos até a bola parar.

    A bola desacelera BALL_DECELERATION por turno e é considerada parada
    quando speed <= BALL_MIN_SPEED.
    """
    v0 = min(v0, BALL_MAX_SPEED)
    dist = 0.0
    v = v0
    turns = 0
    while v > BALL_MIN_SPEED:
        dist += v
        v -= BALL_DECELERATION
        turns += 1
    return dist, turns


def ball_position_after(v0: float, t: int) -> float:
    """Distância percorrida pela bola após t turnos com velocidade inicial v0."""
    v0 = min(v0, BALL_MAX_SPEED)
    dist = 0.0
    v = v0
    for _ in range(t):
        if v <= BALL_MIN_SPEED:
            break
        dist += v
        v -= BALL_DECELERATION
    return dist


def speed_to_reach(distance: float) -> float | None:
    """Menor velocidade inicial para a bola percorrer `distance`.

    Retorna None se a distância for inalcançável com um único chute.
    """
    lo, hi = BALL_MIN_SPEED, BALL_MAX_SPEED
    if ball_travel(BALL_MAX_SPEED)[0] < distance:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if ball_travel(mid)[0] < distance:
            lo = mid
        else:
            hi = mid
    return hi


def turns_for_ball(v0: float, distance: float) -> int | None:
    """Nº de turnos para a bola cobrir `distance` com velocidade inicial v0."""
    v0 = min(v0, BALL_MAX_SPEED)
    d = 0.0
    v = v0
    t = 0
    while v > BALL_MIN_SPEED:
        d += v
        v -= BALL_DECELERATION
        t += 1
        if d >= distance:
            return t
    return None


def kick_reduction(angle_deg: float) -> float:
    """Fator de redução da força do chute conforme o ângulo com a direção do jogador.

    100% a 0°, 50% a 180°.
    """
    return 0.5 + 0.5 * ((180 - angle_deg) / 180)


def self_pass_max_speed() -> float:
    """Maior v0 para o qual o próprio jogador reconquista a bola parada.

    O jogador corre a PLAYER_MAX_SPEED; alcança a bola quando percorre
    dist_bola - TOUCH_RADIUS. Chutar à frente e correr é mais rápido que
    conduzir, desde que a bola continue recuperável.
    """
    best = 0.0
    v = BALL_MIN_SPEED
    while v <= BALL_MAX_SPEED:
        dist, turns = ball_travel(v)
        # o jogador precisa chegar ao ponto de parada; tolera alguns turnos extras
        need = max(0.0, dist - TOUCH_RADIUS)
        if need / PLAYER_MAX_SPEED <= turns:
            best = v
        v += 1
    return best


def effective_advance_rate(v0: float) -> float:
    """Velocidade média de avanço usando 'chute-e-persegue' com velocidade v0.

    Compara-se com PLAYER_MAX_SPEED (=100), que é a taxa ao conduzir a bola.
    """
    dist, _ = ball_travel(v0)
    need = max(0.0, dist - TOUCH_RADIUS)
    turns_to_recover = math.ceil(need / PLAYER_MAX_SPEED)
    if turns_to_recover == 0:
        return 0.0
    return dist / turns_to_recover


def intercept_turns(player_pos, ball_pos, ball_dir, v0, player_speed=PLAYER_MAX_SPEED):
    """Menor nº de turnos em que o jogador alcança a bola em movimento.

    Retorna (turnos, ponto_de_encontro) ou None se não interceptável.
    """
    px, py = player_pos
    bx, by = ball_pos
    dx, dy = ball_dir
    n = math.hypot(dx, dy)
    if n == 0:
        return None
    dx, dy = dx / n, dy / n

    v = v0
    travelled = 0.0
    t = 0
    while v > BALL_MIN_SPEED and t < 200:
        travelled += v
        v -= BALL_DECELERATION
        t += 1
        tx, ty = bx + dx * travelled, by + dy * travelled
        tx = max(0, min(MAX_X, tx))
        ty = max(0, min(MAX_Y, ty))
        if math.hypot(tx - px, ty - py) - TOUCH_RADIUS <= player_speed * t:
            return t, (tx, ty)
    # bola parada: o jogador ainda pode chegar
    tx, ty = bx + dx * travelled, by + dy * travelled
    tx = max(0, min(MAX_X, tx))
    ty = max(0, min(MAX_Y, ty))
    d = math.hypot(tx - px, ty - py) - TOUCH_RADIUS
    return math.ceil(max(0.0, d) / player_speed), (tx, ty)
