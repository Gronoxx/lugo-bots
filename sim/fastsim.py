"""
Simulador rápido da física do Lugo, sem gRPC nem Docker.

Motivação: uma partida real (servidor + 22 containers) leva ~2 min. Para
otimizar pesos por evolução ou treinar por RL precisamos de milhares de
partidas. Este simulador roda a mesma física em processo, milhares de vezes
mais rápido.

IMPORTANTE: é uma reimplementação a partir das specs, não o servidor
oficial. `validate.py` compara suas previsões contra replays reais para
medir a divergência. Use-o para BUSCA (comparar variantes), e confirme os
finalistas no servidor de verdade.

Ordem de processamento por turno (conforme server.proto, estado PLAYING):
  - se a bola não está presa, a velocidade dela é processada primeiro
  - as ordens de cada jogador saem na sequência em que foram enviadas
  - o chute é processado imediatamente e SOMA à velocidade da bola
"""

import math

import numpy as np

MAX_X = 20000
MAX_Y = 10000
GOAL_WIDTH = 3000
GOAL_MIN_Y = (MAX_Y - GOAL_WIDTH) / 2      # 3500
GOAL_MAX_Y = GOAL_MIN_Y + GOAL_WIDTH       # 6500
GOAL_ZONE_RANGE = 1400

PLAYER_SIZE = 400
PLAYER_MAX_SPEED = 100.0
BALL_SIZE = 200
BALL_MAX_SPEED = 400.0
BALL_MIN_SPEED = 2.0
BALL_DECEL = 10.0
BALL_TIME_IN_GOAL_ZONE = 40
TOUCH_RADIUS = (PLAYER_SIZE + BALL_SIZE) / 2   # 300

GOALKEEPER_JUMP_SPEED = 200.0
GOALKEEPER_JUMP_DURATION = 3
SHOT_CLOCK_TIME = 300
GAME_TURNS = 6000          # valor real do servidor (a doc web diz 1200)

HOME, AWAY = 0, 1


class State:
    """Estado completo do jogo em um turno."""

    __slots__ = ("turn", "pos", "vel", "ball_pos", "ball_vel", "holder",
                 "score", "shot_clock_side", "shot_clock", "jump_left",
                 "turns_ball_in_goal_zone")

    def __init__(self):
        self.turn = 0
        # pos[side][number-1] = (x, y)
        self.pos = np.zeros((2, 11, 2), dtype=np.float64)
        self.vel = np.zeros((2, 11, 2), dtype=np.float64)
        self.ball_pos = np.array([MAX_X / 2, MAX_Y / 2], dtype=np.float64)
        self.ball_vel = np.zeros(2, dtype=np.float64)
        self.holder = None            # (side, idx) ou None
        self.score = [0, 0]
        self.shot_clock_side = HOME
        self.shot_clock = SHOT_CLOCK_TIME
        self.jump_left = np.zeros((2, 11), dtype=np.int32)
        self.turns_ball_in_goal_zone = 0

    def copy(self):
        s = State()
        s.turn = self.turn
        s.pos = self.pos.copy()
        s.vel = self.vel.copy()
        s.ball_pos = self.ball_pos.copy()
        s.ball_vel = self.ball_vel.copy()
        s.holder = self.holder
        s.score = list(self.score)
        s.shot_clock_side = self.shot_clock_side
        s.shot_clock = self.shot_clock
        s.jump_left = self.jump_left.copy()
        s.turns_ball_in_goal_zone = self.turns_ball_in_goal_zone
        return s


DEFAULT_FORMATION = np.array([
    [0.03, 0.50], [0.16, 0.20], [0.14, 0.40], [0.14, 0.60], [0.16, 0.80],
    [0.35, 0.30], [0.33, 0.50], [0.35, 0.70], [0.60, 0.25], [0.62, 0.50],
    [0.60, 0.75],
])


def initial_state(formation_home=None, formation_away=None) -> State:
    s = State()
    fh = DEFAULT_FORMATION if formation_home is None else formation_home
    fa = DEFAULT_FORMATION if formation_away is None else formation_away
    for i in range(11):
        s.pos[HOME, i] = [fh[i][0] * MAX_X, fh[i][1] * MAX_Y]
        s.pos[AWAY, i] = [(1 - fa[i][0]) * MAX_X, fa[i][1] * MAX_Y]
    s.ball_pos[:] = [MAX_X / 2, MAX_Y / 2]
    s.ball_vel[:] = 0
    s.holder = None
    return s


def _clip_speed(v, vmax):
    sp = math.hypot(v[0], v[1])
    if sp > vmax and sp > 0:
        v = v * (vmax / sp)
    return v


def step(s: State, orders_home, orders_away) -> State:
    """Avança um turno.

    orders_* é uma lista de 11 dicts, cada um podendo conter:
      {"move": (vx, vy)}          velocidade desejada (será limitada)
      {"kick": (vx, vy)}          só tem efeito se o jogador tem a bola
      {"catch": True}             tenta pegar a bola se estiver tocando
      {"jump": (vx, vy)}          só goleiro (idx 0)
    """
    s = s.copy()
    s.turn += 1

    # 1) se a bola está solta, sua velocidade é processada primeiro
    if s.holder is None:
        scored = _move_ball(s)
        if scored is not None:
            s.score[scored] += 1
            _reset_positions(s)
            return s

    # 2) ordens dos jogadores, HOME primeiro (mesma ordem do servidor)
    for side, orders in ((HOME, orders_home), (AWAY, orders_away)):
        for i, o in enumerate(orders):
            if o is None:
                continue
            _apply_move(s, side, i, o)
            if o.get("catch"):
                _try_catch(s, side, i)
            k = o.get("kick")
            if k is not None and s.holder == (side, i):
                scored = _apply_kick(s, side, i, k)
                if scored is not None:
                    s.score[scored] += 1
                    _reset_positions(s)
                    return s

    # 3) a bola presa acompanha quem a segura
    if s.holder is not None:
        side, i = s.holder
        s.ball_pos[:] = s.pos[side, i]
        s.ball_vel[:] = s.vel[side, i]

    # 4) gol?
    goal = _check_goal(s)
    if goal is not None:
        s.score[goal] += 1
        _reset_positions(s)
        return s

    # 5) shot clock
    _update_shot_clock(s)

    # 6) bola parada na área do gol é recolocada no centro
    _update_goal_zone(s)

    return s


def _move_ball(s: State):
    """Move a bola um turno. Retorna o lado que marcou, ou None.

    A checagem de gol acontece ANTES da reflexão: se a bola cruza a linha de
    fundo dentro da boca do gol, é gol; caso contrário, quica.
    """
    sp = math.hypot(s.ball_vel[0], s.ball_vel[1])
    if sp <= BALL_MIN_SPEED:
        s.ball_vel[:] = 0
        return None
    # o servidor integra de forma trapezoidal: avanço = v - BALL_DECEL/2
    # (validado em sim/validate.py: erro cai de 5.0d para 0.38d por turno)
    adv_scale = max(0.0, sp - BALL_DECEL / 2) / sp
    s.ball_pos += s.ball_vel * adv_scale

    # cruzou a linha de fundo dentro da boca do gol?
    if s.ball_pos[0] <= 0 and GOAL_MIN_Y <= s.ball_pos[1] <= GOAL_MAX_Y:
        return AWAY
    if s.ball_pos[0] >= MAX_X and GOAL_MIN_Y <= s.ball_pos[1] <= GOAL_MAX_Y:
        return HOME

    # quica nas bordas com a mesma velocidade
    if s.ball_pos[0] < 0:
        s.ball_pos[0] = -s.ball_pos[0]
        s.ball_vel[0] = -s.ball_vel[0]
    elif s.ball_pos[0] > MAX_X:
        s.ball_pos[0] = 2 * MAX_X - s.ball_pos[0]
        s.ball_vel[0] = -s.ball_vel[0]
    if s.ball_pos[1] < 0:
        s.ball_pos[1] = -s.ball_pos[1]
        s.ball_vel[1] = -s.ball_vel[1]
    elif s.ball_pos[1] > MAX_Y:
        s.ball_pos[1] = 2 * MAX_Y - s.ball_pos[1]
        s.ball_vel[1] = -s.ball_vel[1]
    # desaceleração
    new_sp = max(0.0, sp - BALL_DECEL)
    if new_sp <= BALL_MIN_SPEED:
        s.ball_vel[:] = 0
    else:
        s.ball_vel *= (new_sp / sp)
    return None


def _apply_move(s: State, side, i, o):
    if s.jump_left[side, i] > 0:
        s.jump_left[side, i] -= 1
        vmax = GOALKEEPER_JUMP_SPEED
    else:
        j = o.get("jump")
        if j is not None and i == 0:
            s.vel[side, i] = _clip_speed(np.array(j, dtype=np.float64),
                                         GOALKEEPER_JUMP_SPEED)
            s.jump_left[side, i] = GOALKEEPER_JUMP_DURATION - 1
            _advance_player(s, side, i)
            return
        m = o.get("move")
        if m is not None:
            s.vel[side, i] = _clip_speed(np.array(m, dtype=np.float64),
                                         PLAYER_MAX_SPEED)
        vmax = PLAYER_MAX_SPEED
    s.vel[side, i] = _clip_speed(s.vel[side, i], vmax)
    _advance_player(s, side, i)


def _advance_player(s: State, side, i):
    s.pos[side, i] += s.vel[side, i]
    s.pos[side, i, 0] = min(max(s.pos[side, i, 0], 0), MAX_X)
    s.pos[side, i, 1] = min(max(s.pos[side, i, 1], 0), MAX_Y)
    # zona do gol adversário é proibida para jogadores de linha
    if i != 0:
        goal_x = MAX_X if side == HOME else 0
        d = math.hypot(s.pos[side, i, 0] - goal_x,
                       s.pos[side, i, 1] - MAX_Y / 2)
        if d < GOAL_ZONE_RANGE:
            scale = GOAL_ZONE_RANGE / max(d, 1e-6)
            s.pos[side, i, 0] = goal_x + (s.pos[side, i, 0] - goal_x) * scale
            s.pos[side, i, 1] = MAX_Y / 2 + (s.pos[side, i, 1] - MAX_Y / 2) * scale


def _try_catch(s: State, side, i):
    if s.holder is not None:
        return
    d = math.hypot(s.ball_pos[0] - s.pos[side, i, 0],
                   s.ball_pos[1] - s.pos[side, i, 1])
    if d <= TOUCH_RADIUS:
        prev = s.holder
        s.holder = (side, i)
        if prev is None or prev[0] != side:
            s.shot_clock_side = side
            s.shot_clock = SHOT_CLOCK_TIME


def _apply_kick(s: State, side, i, k):
    kv = np.array(k, dtype=np.float64)
    # redução conforme o ângulo com a direção do jogador
    pv = s.vel[side, i]
    psp = math.hypot(pv[0], pv[1])
    ksp = math.hypot(kv[0], kv[1])
    if psp > 1e-9 and ksp > 1e-9:
        cos = float(np.dot(pv, kv) / (psp * ksp))
        cos = max(-1.0, min(1.0, cos))
        ang = math.degrees(math.acos(cos))
        factor = 0.5 + 0.5 * ((180 - ang) / 180)
        kv = kv * factor
    # o chute SOMA à velocidade atual da bola
    s.ball_vel = _clip_speed(s.ball_vel + kv, BALL_MAX_SPEED)
    s.holder = None
    # "The ball kick is processed immediately after the order (the ball
    # position is updated as its new velocity after the kick)" — sem isto a
    # bola fica parada sob o chutador e o time processado depois consegue
    # capturá-la no mesmo turno, o que enviesa o jogo para o AWAY.
    return _move_ball(s)


def _check_goal(s: State):
    """Retorna o lado que marcou, ou None."""
    x, y = s.ball_pos
    if GOAL_MIN_Y <= y <= GOAL_MAX_Y:
        if x <= 0:
            return AWAY      # bola no gol da esquerda (defendido por HOME)
        if x >= MAX_X:
            return HOME
    return None


def _reset_positions(s: State):
    st = initial_state()
    s.pos[:] = st.pos
    s.vel[:] = 0
    s.ball_pos[:] = st.ball_pos
    s.ball_vel[:] = 0
    s.holder = None
    s.shot_clock = SHOT_CLOCK_TIME
    s.jump_left[:] = 0


def _update_shot_clock(s: State):
    if s.holder is None:
        return
    side = s.holder[0]
    if side != s.shot_clock_side:
        s.shot_clock_side = side
        s.shot_clock = SHOT_CLOCK_TIME
        return
    s.shot_clock -= 1
    if s.shot_clock <= 0:
        # posse passa ao goleiro do time de defesa
        other = 1 - side
        s.holder = (other, 0)
        s.ball_pos[:] = s.pos[other, 0]
        s.ball_vel[:] = 0
        s.shot_clock_side = other
        s.shot_clock = SHOT_CLOCK_TIME


def _update_goal_zone(s: State):
    if s.holder is not None:
        s.turns_ball_in_goal_zone = 0
        return
    x, y = s.ball_pos
    in_zone = (math.hypot(x, y - MAX_Y / 2) < GOAL_ZONE_RANGE or
               math.hypot(x - MAX_X, y - MAX_Y / 2) < GOAL_ZONE_RANGE)
    if in_zone:
        s.turns_ball_in_goal_zone += 1
        if s.turns_ball_in_goal_zone >= BALL_TIME_IN_GOAL_ZONE:
            direction = np.array([MAX_X / 2 - x, MAX_Y / 2 - y])
            n = math.hypot(direction[0], direction[1]) or 1.0
            s.ball_vel = direction / n * BALL_MAX_SPEED
            s.turns_ball_in_goal_zone = 0
    else:
        s.turns_ball_in_goal_zone = 0


def play(policy_home, policy_away, turns=GAME_TURNS, state=None, on_turn=None):
    """Roda uma partida completa entre duas políticas.

    Uma política é uma função (state, side) -> lista de 11 ordens.
    """
    s = state if state is not None else initial_state()
    for _ in range(turns):
        oh = policy_home(s, HOME)
        oa = policy_away(s, AWAY)
        s = step(s, oh, oa)
        if on_turn is not None:
            on_turn(s)
    return s
