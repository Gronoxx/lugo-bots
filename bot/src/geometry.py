"""
Núcleo geométrico e de física do bot.

Tudo que decidimos depende de prever a bola com precisão. As constantes
vêm das specs oficiais; a física foi validada contra replays do servidor.
"""

import math

import lugo4py

MAX_X = lugo4py.max_x_coordinate          # 20000
MAX_Y = lugo4py.max_y_coordinate          # 10000
BALL_MAX_SPEED = lugo4py.BALL_MAX_SPEED   # 400
BALL_MIN_SPEED = lugo4py.BALL_MIN_SPEED   # 2
BALL_DECEL = lugo4py.BALL_DECELERATION    # 10
PLAYER_SPEED = lugo4py.player_max_speed   # 100
PLAYER_SIZE = lugo4py.PLAYER_SIZE         # 400
BALL_SIZE = lugo4py.BALL_SIZE             # 200
GOAL_MIN_Y = lugo4py.GOAL_MIN_Y           # 3500
GOAL_MAX_Y = lugo4py.GOAL_MAX_Y           # 6500

TOUCH_RADIUS = (PLAYER_SIZE + BALL_SIZE) / 2   # 300

# O goleiro é bem maior que um jogador de linha: GOALKEEPER_SIZE = PLAYER_SIZE*2.3
# = 920 (em lugo4py a constante é uma tupla, por causa de uma vírgula final — sinal
# de que ninguém no ecossistema Python jamais a usou). Meia-extensão efetiva:
GOALKEEPER_HALF_EXTENT = (920 + BALL_SIZE) / 2   # 560

# Alcance máximo de um chute (v0=400), com a integração trapezoidal: 8000d.
MAX_KICK_RANGE = 8000
# Distância a partir da origem abaixo da qual não faz sentido considerar
# intercepção: um adversário aí está ao lado do chutador, não na trajetória.
NO_BLOCK_NEAR_ORIGIN = 700.0
# Distância na qual a bola ainda chega ao alvo com >=200 d/f (chute perigoso).
# Além disso a bola chega lenta e o goleiro defende com folga.
DANGEROUS_SHOT_RANGE = 6000


def point(x, y):
    p = lugo4py.lugo.Point()
    p.x = int(max(0, min(MAX_X, x)))
    p.y = int(max(0, min(MAX_Y, y)))
    return p


def dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


# O servidor integra a posição da bola de forma trapezoidal: o avanço em um
# turno é (v + v_seguinte)/2 = v - BALL_DECEL/2. Validado contra replays reais:
# com esta correção o erro de previsão cai de 5.0d para 0.38d por turno
# (sim/validate.py).
HALF_DECEL = BALL_DECEL / 2


def ball_step(v: float) -> float:
    """Avanço da bola em um turno, dada a velocidade atual."""
    return max(0.0, v - HALF_DECEL)


def ball_range(v0: float) -> float:
    """Distância total que a bola percorre com velocidade inicial v0."""
    v0 = min(v0, BALL_MAX_SPEED)
    d = 0.0
    v = v0
    while v > BALL_MIN_SPEED:
        d += ball_step(v)
        v -= BALL_DECEL
    return d


def speed_for_distance(d: float) -> float:
    """Menor velocidade inicial para a bola percorrer d (limitada ao máximo)."""
    if d <= 0:
        return BALL_MIN_SPEED
    lo, hi = BALL_MIN_SPEED, BALL_MAX_SPEED
    if ball_range(BALL_MAX_SPEED) < d:
        return BALL_MAX_SPEED
    for _ in range(40):
        mid = (lo + hi) / 2
        if ball_range(mid) < d:
            lo = mid
        else:
            hi = mid
    return hi


def turns_for_ball(v0: float, d: float) -> float:
    """Turnos para a bola cobrir a distância d. inf se não alcança."""
    v0 = min(v0, BALL_MAX_SPEED)
    travelled = 0.0
    v = v0
    t = 0
    while v > BALL_MIN_SPEED:
        travelled += ball_step(v)
        v -= BALL_DECEL
        t += 1
        if travelled >= d:
            return t
    return math.inf


def turns_for_player(d: float) -> float:
    """Turnos para um jogador cobrir a distância d (já descontado o toque)."""
    return max(0.0, d - TOUCH_RADIUS) / PLAYER_SPEED


def ball_trajectory(ball, max_turns: int = 60):
    """Prevê a trajetória da bola, refletindo nas bordas do campo.

    A bola quica nas bordas com a mesma velocidade (regra oficial).
    Retorna lista de (turno, x, y).
    """
    vel = ball.velocity
    speed = vel.speed
    dx, dy = vel.direction.x, vel.direction.y
    n = math.hypot(dx, dy)
    if n == 0 or speed <= BALL_MIN_SPEED:
        return [(0, ball.position.x, ball.position.y)]
    dx, dy = dx / n, dy / n

    x, y = float(ball.position.x), float(ball.position.y)
    out = []
    for t in range(1, max_turns + 1):
        if speed <= BALL_MIN_SPEED:
            out.append((t, x, y))
            break
        adv = ball_step(speed)
        x += dx * adv
        y += dy * adv
        # Registra o ponto ANTES de refletir: se a bola cruzou a linha de fundo,
        # quem consome a trajetória (o goleiro) precisa ver x<=0 ou x>=MAX_X para
        # detectar a ameaça. Refletir antes de devolver fazia o teste de
        # cruzamento nunca disparar — o goleiro só reagia com a bola quase dentro.
        if x < 0 or x > MAX_X:
            out.append((t, x, max(0.0, min(MAX_Y, y))))
        # reflexão nas bordas
        if x < 0:
            x = -x
            dx = -dx
        elif x > MAX_X:
            x = 2 * MAX_X - x
            dx = -dx
        if y < 0:
            y = -y
            dy = -dy
        elif y > MAX_Y:
            y = 2 * MAX_Y - y
            dy = -dy
        speed -= BALL_DECEL
        out.append((t, x, y))
    return out


def intercept_turn(player_pos, ball, max_turns: int = 60):
    """Primeiro turno em que o jogador alcança a bola, e onde.

    Retorna (turno, Point) ou None se não alcançável no horizonte.
    """
    traj = ball_trajectory(ball, max_turns)
    for t, bx, by in traj:
        d = math.hypot(bx - player_pos.x, by - player_pos.y)
        if turns_for_player(d) <= t:
            return t, point(bx, by)
    if traj:
        t, bx, by = traj[-1]
        d = math.hypot(bx - player_pos.x, by - player_pos.y)
        return t + turns_for_player(d), point(bx, by)
    return None


def dist_point_to_segment(p, a, b) -> float:
    """Distância do ponto p ao segmento ab. Usada para checar linhas de passe."""
    ax, ay = a.x, a.y
    bx, by = b.x, b.y
    px, py = p.x, p.y
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return math.hypot(px - ax, py - ay)
    tt = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    cx, cy = ax + tt * vx, ay + tt * vy
    return math.hypot(px - cx, py - cy)


def lane_is_clear(origin, target, opponents, margin: float = 450) -> bool:
    """A linha origem->alvo está livre de adversários?

    `margin` é a folga: raio do jogador + tolerância para o movimento dele
    durante o voo da bola.
    """
    for opp in opponents:
        if dist_point_to_segment(opp.position, origin, target) < margin:
            return False
    return True


def lane_clearance(origin, target, opponents) -> float:
    """Menor distância de um adversário à linha origem->alvo (quanto maior, melhor)."""
    if not opponents:
        return 1e9
    return min(dist_point_to_segment(o.position, origin, target) for o in opponents)


def opponent_can_intercept(origin, target, opponents, kick_speed) -> bool:
    """Algum adversário chega à linha de passe antes da bola?

    Compara o tempo da bola até cada ponto da trajetória com o tempo que o
    adversário leva para alcançar aquele ponto.
    """
    total = math.hypot(target.x - origin.x, target.y - origin.y)
    if total == 0:
        return False
    steps = 8
    for i in range(1, steps + 1):
        frac = i / steps
        d_ball = total * frac
        # Pontos colados na origem não são interceptáveis: o marcador que está
        # AO LADO do portador não alcança uma bola que já passou por ele. Sem
        # este corte, `turns_for_player(255) == 0` fazia qualquer marcador
        # próximo bloquear TODO chute e TODO passe — medido nos replays, era a
        # causa de 38% dos bloqueios (detectados no 1º ponto de amostragem) e
        # mantinha o portão de finalização fechado em ~98% dos turnos em zona.
        if d_ball < NO_BLOCK_NEAR_ORIGIN:
            continue
        px = origin.x + (target.x - origin.x) * frac
        py = origin.y + (target.y - origin.y) * frac
        t_ball = turns_for_ball(kick_speed, d_ball)
        if t_ball == math.inf:
            return True
        for opp in opponents:
            d_opp = math.hypot(px - opp.position.x, py - opp.position.y)
            if turns_for_player(d_opp) <= t_ball:
                return True
    return False


# ---- interceptação sensível à velocidade (gene use_velocity) --------------
# opponent_can_intercept (acima) é o PIOR CASO estático correto: sem inércia no
# Lugo, o oponente alcança qualquer ponto a PLAYER_SPEED*t da posição ATUAL.
# Por isso a velocidade NÃO pode tornar o veto mais frouxo — só pode ACRESCENTAR
# ameaça. use_velocity="on" refina em três eixos, todos conservadores:
#   1. min(d_agora, d_extrapolada): se a corrida comprometida do oponente o leva
#      para MAIS PERTO de um ponto da linha, usamos essa distância menor.
#   2. dwell: bola que chega fraca permanece na zona de contato -> concede turnos
#      extras ao oponente (t_ball efetivo maior).
#   3. amostragem densa (~TOUCH_RADIUS) em vez de 8 pontos: não pula zagueiro
#      entre amostras (falso-seguro do usuário).
INTERCEPT_LEAD_TURNS = 6.0
INTERCEPT_DWELL_CAP = 4.0
INTERCEPT_SAMPLE_SPACING = 300.0
INTERCEPT_MAX_STEPS = 32
INTERCEPT_RISK_CAP = 6.0
UNREACHABLE_RISK = -999.0


def _lead_pos(entity, turns: float):
    """Posição prevista de `entity` após `turns` (velocidade atual, limitada a
    PLAYER_SPEED), presa ao campo (o servidor prende jogadores à borda)."""
    v = entity.velocity
    n = math.hypot(v.direction.x, v.direction.y)
    if n == 0 or v.speed <= 0 or turns <= 0:
        return float(entity.position.x), float(entity.position.y)
    dx, dy = v.direction.x / n, v.direction.y / n
    travel = min(v.speed, PLAYER_SPEED) * turns
    x = entity.position.x + dx * travel
    y = entity.position.y + dy * travel
    return max(0.0, min(MAX_X, x)), max(0.0, min(MAX_Y, y))


def _arrival_speed_at(v0: float, d: float) -> float:
    """Velocidade de chegada da bola após percorrer d (forma fechada; 0 se não
    chega). Consistente com finishing.arrival_speed."""
    s2 = min(v0, BALL_MAX_SPEED) ** 2 - 20.0 * d
    return math.sqrt(s2) if s2 > 0.0 else 0.0


def _dwell_turns(v_arr: float) -> float:
    """Turnos extras que uma bola a v_arr concede ao oponente por permanecer na
    zona de contato, ACIMA do que concede uma bola no máximo."""
    ref = TOUCH_RADIUS / max(ball_step(BALL_MAX_SPEED), 1.0)
    here = TOUCH_RADIUS / max(ball_step(v_arr), 1.0)
    return max(0.0, min(INTERCEPT_DWELL_CAP, here - ref))


def _intercept_scan(origin, target, opponents, kick_speed, use_velocity: bool):
    """MENOR folga temporal (turns_for_player(d_opp) - t_ball_eff) sobre pontos e
    oponentes. <=0 => interceptável. UNREACHABLE_RISK se a bola não alcança.

    use_velocity=False: 8 amostras, d_opp estático, sem dwell -> min_slack<=0
    é EXATAMENTE equivalente a opponent_can_intercept (mesmo NO_BLOCK_NEAR_ORIGIN,
    mesmo <=, mesmo t_ball==inf)."""
    dx, dy = (target.x - origin.x), (target.y - origin.y)
    total = math.hypot(dx, dy)
    if total == 0:
        return math.inf
    if use_velocity:
        steps = max(8, min(INTERCEPT_MAX_STEPS,
                           int(math.ceil(total / INTERCEPT_SAMPLE_SPACING))))
    else:
        steps = 8

    min_slack = math.inf
    for i in range(1, steps + 1):
        frac = i / steps
        d_ball = total * frac
        if d_ball < NO_BLOCK_NEAR_ORIGIN:
            continue
        px = origin.x + dx * frac
        py = origin.y + dy * frac
        t_ball = turns_for_ball(kick_speed, d_ball)
        if t_ball == math.inf:
            return UNREACHABLE_RISK
        if use_velocity:
            t_ball_eff = t_ball + _dwell_turns(_arrival_speed_at(kick_speed, d_ball))
            lead = min(float(t_ball), INTERCEPT_LEAD_TURNS)
        else:
            t_ball_eff = t_ball
            lead = 0.0
        for opp in opponents:
            d_opp = math.hypot(px - opp.position.x, py - opp.position.y)
            if lead > 0.0:
                lx, ly = _lead_pos(opp, lead)
                d_lead = math.hypot(px - lx, py - ly)
                if d_lead < d_opp:          # velocidade SÓ pode aproximar a ameaça
                    d_opp = d_lead
            slack = turns_for_player(d_opp) - t_ball_eff
            if slack < min_slack:
                min_slack = slack
    return min_slack


def can_be_intercepted(origin, target, opponents, kick_speed,
                       use_velocity: bool = False) -> bool:
    """use_velocity=False -> DELEGA a opponent_can_intercept (v9 exato).
    use_velocity=True -> versão conservadora (só adiciona bloqueios)."""
    if not use_velocity:
        return opponent_can_intercept(origin, target, opponents, kick_speed)
    return _intercept_scan(origin, target, opponents, kick_speed, True) <= 0.0


def intercept_risk(origin, target, opponents, kick_speed,
                   use_velocity: bool = False) -> float:
    """Folga temporal (turnos) do oponente mais perigoso: >0 seguro, <=0
    interceptável, UNREACHABLE_RISK se a bola não alcança. Contínuo, para o score
    (maior = linha mais segura). Com use_velocity=False, r<=0 <=> veto da v9."""
    r = _intercept_scan(origin, target, opponents, kick_speed, use_velocity)
    return 30.0 if r == math.inf else r


def lead_target(receiver, turns_ahead: float):
    """Onde o companheiro estará em `turns_ahead` turnos (passe com liderança)."""
    v = receiver.velocity
    n = math.hypot(v.direction.x, v.direction.y)
    if n == 0 or v.speed <= 0:
        return point(receiver.position.x, receiver.position.y)
    dx, dy = v.direction.x / n, v.direction.y / n
    travel = min(v.speed, PLAYER_SPEED) * turns_ahead
    return point(receiver.position.x + dx * travel,
                 receiver.position.y + dy * travel)


# ---------------------------------------------------------------- chute exato
#
# `inspector.make_order_kick` da lugo4py erra a mira: ela subtrai
# `ball.velocity.direction` do vetor até o alvo, mas `geo.normalize` escala para
# magnitude 100 — enquanto a bola pode andar a 400 — e o vetor até o alvo tem
# magnitude igual à distância (milhares). A correção fica errada por um fator que
# depende da distância e da velocidade. Como está na biblioteca, todo bot Python
# da competição tem esse defeito.
#
# Física real do servidor (server.proto, message Kick):
#   1. o chute enviado sofre redução por ângulo com a direção do jogador:
#        fator = 0.5 + 0.5*((180 - ang)/180)      (100% a 0°, 50% a 180°)
#   2. o resultado é SOMADO à velocidade atual da bola
#   3. o total é limitado a BALL_MAX_SPEED
#
# Para a bola sair na direção desejada resolvemos ao contrário. Como o fator é
# escalar, ele não muda a direção do chute — então não é preciso iterar:
#   necessário = velocidade_desejada - velocidade_atual_da_bola
#   enviado    = necessário / fator(ângulo entre jogador e `necessário`)

def _unit(vx, vy):
    n = math.hypot(vx, vy)
    return (0.0, 0.0) if n == 0 else (vx / n, vy / n)


def _apply_server_kick(cvx, cvy, kx, ky, s, pvx, pvy):
    """Física do chute no servidor: reduz por ângulo, soma à bola, limita ao máximo."""
    factor = 1.0
    if (pvx, pvy) != (0.0, 0.0):
        cos = max(-1.0, min(1.0, pvx * kx + pvy * ky))
        ang = math.degrees(math.acos(cos))
        factor = 0.5 + 0.5 * ((180.0 - ang) / 180.0)
    rx, ry = cvx + kx * s * factor, cvy + ky * s * factor
    n = math.hypot(rx, ry)
    if n > BALL_MAX_SPEED:
        rx, ry = rx / n * BALL_MAX_SPEED, ry / n * BALL_MAX_SPEED
        n = BALL_MAX_SPEED
    return rx, ry, n


def kick_to(inspector, me, ball, target, desired_speed=BALL_MAX_SPEED):
    """Ordem de chute que faz a bola seguir para `target` de fato.

    Substitui `inspector.make_order_kick`. Nem sempre existe um chute que produza
    exatamente a velocidade desejada — a soma com a velocidade atual da bola pode
    exigir mais que o teto de 400, e aí o corte estraga a mira. Por isso buscamos
    o chute ALCANÇÁVEL que minimiza o erro angular, e só depois o de velocidade.

    Custo: ~288 avaliações triviais, muito abaixo do orçamento de 50 ms por turno
    (o bot inteiro gasta ~0,5 ms).
    """
    tx, ty = target.x - ball.position.x, target.y - ball.position.y
    ux, uy = _unit(tx, ty)
    if (ux, uy) == (0.0, 0.0):
        ux, uy = 1.0, 0.0
    desired_speed = min(desired_speed, BALL_MAX_SPEED)

    bv = ball.velocity
    bux, buy = _unit(bv.direction.x, bv.direction.y)
    cvx, cvy = bux * bv.speed, buy * bv.speed
    pvx, pvy = _unit(me.velocity.direction.x, me.velocity.direction.y)

    best = (ux, uy, desired_speed)
    best_cost = float("inf")
    for i in range(72):                       # direções de 5 em 5 graus
        a = math.radians(i * 5)
        kx, ky = math.cos(a), math.sin(a)
        for frac in (0.25, 0.5, 0.75, 1.0):   # intensidades
            s = BALL_MAX_SPEED * frac
            rx, ry, rn = _apply_server_kick(cvx, cvy, kx, ky, s, pvx, pvy)
            if rn < 1e-6:
                continue
            cos = max(-1.0, min(1.0, (rx * ux + ry * uy) / rn))
            ang_err = math.degrees(math.acos(cos))
            speed_err = abs(rn - desired_speed) / BALL_MAX_SPEED
            cost = ang_err + 8.0 * speed_err  # ângulo domina; velocidade desempata
            if cost < best_cost:
                best_cost, best = cost, (kx, ky, s)

    kx, ky, s = best
    order = lugo4py.server_pb2.Order()
    order.kick.velocity.direction.x = kx * 100.0
    order.kick.velocity.direction.y = ky * 100.0
    order.kick.velocity.speed = s
    return order


def achievable_shot_speed(inspector, me, ball, target) -> float:
    """Velocidade de saída rumo a `target` do MELHOR chute alcançável (mesma
    busca de kick_to com desired=BALL_MAX_SPEED), projetada na direção do alvo.
    Captura o chute que sai fraco porque o jogador se move de lado ou a bola traz
    velocidade adversa (_apply_server_kick). Alimenta o piso shot_arrival_min."""
    tx, ty = target.x - ball.position.x, target.y - ball.position.y
    ux, uy = _unit(tx, ty)
    if (ux, uy) == (0.0, 0.0):
        return 0.0
    bv = ball.velocity
    bux, buy = _unit(bv.direction.x, bv.direction.y)
    cvx, cvy = bux * bv.speed, buy * bv.speed
    pvx, pvy = _unit(me.velocity.direction.x, me.velocity.direction.y)
    best_proj = 0.0
    best_cost = float("inf")
    for i in range(72):
        a = math.radians(i * 5)
        kx, ky = math.cos(a), math.sin(a)
        for frac in (0.25, 0.5, 0.75, 1.0):
            s = BALL_MAX_SPEED * frac
            rx, ry, rn = _apply_server_kick(cvx, cvy, kx, ky, s, pvx, pvy)
            if rn < 1e-6:
                continue
            cos = max(-1.0, min(1.0, (rx * ux + ry * uy) / rn))
            ang_err = math.degrees(math.acos(cos))
            speed_err = abs(rn - BALL_MAX_SPEED) / BALL_MAX_SPEED
            cost = ang_err + 8.0 * speed_err
            if cost < best_cost:
                best_cost = cost
                best_proj = max(0.0, rx * ux + ry * uy)
    return best_proj
