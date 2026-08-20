"""
Táticas: formação dinâmica e atribuição de papéis.

Diagnóstico do baseline (validado em replay): os dummies mandam todos os 11
jogadores atrás da bola. A bola passa 75% do tempo no meio-campo e o jogo
acaba 0x0. Um time que mantém forma e manda só quem chega primeiro na bola
tem vantagem estrutural.
"""

import math

import lugo4py

from params import P

from geometry import MAX_X, MAX_Y, point, turns_for_player, intercept_turn, dist

GOALKEEPER = 1

# Papéis por número da camisa
DEFENDERS = (2, 3, 4, 5)
MIDFIELDERS = (6, 7, 8)
FORWARDS = (9, 10, 11)

# v11/CERCO (def_camp): ordem de prioridade dos ACAMPADOS PERMANENTES — os que
# NÃO recuam quando o adversário nos cerca. Medido no 0×0 vs level-3: com o
# `_cover_position` puxando todo mundo (0,5*formação + 0,5*30%-rumo-ao-gol), os
# 10 de linha ficavam em x<6000 e não havia PARA QUEM sair — 137 passes a 94,5%
# de acerto sem sair do nosso campo. O BotAdversario1 faz 10×0 no mesmo level-3 com 3
# zagueiros fixos e 7 corpos altos.
DEF_CAMPERS = (10, 9, 11)

# Formação base em coordenadas normalizadas (0 = nosso gol, 1 = gol adversário).
# (x_frac, y_frac). y_frac 0 = borda inferior, 1 = borda superior.
BASE_FORMATION = {
    1:  (0.03, 0.50),   # goleiro
    2:  (0.16, 0.20),   # lateral
    3:  (0.14, 0.40),   # zagueiro
    4:  (0.14, 0.60),   # zagueiro
    5:  (0.16, 0.80),   # lateral
    6:  (0.35, 0.30),   # volante
    7:  (0.33, 0.50),   # meio central
    8:  (0.35, 0.70),   # volante
    9:  (0.60, 0.25),   # ponta
    10: (0.62, 0.50),   # centroavante
    11: (0.60, 0.75),   # ponta
}

# Quanto a formação inteira desliza conforme a bola avança/recua
SHIFT_X = P["shift_x"]      # peso da posição x da bola
SHIFT_Y = P["shift_y"]      # peso da posição y da bola (compactação lateral)


def mirror_x(x_frac: float, side) -> float:
    """Converte fração de avanço para coordenada absoluta conforme o lado."""
    if side == lugo4py.TeamSide.HOME:
        return x_frac * MAX_X
    return (1.0 - x_frac) * MAX_X


def ball_advance_frac(ball_pos, side) -> float:
    """Quão avançada está a bola no nosso sentido de ataque (0..1)."""
    if side == lugo4py.TeamSide.HOME:
        return ball_pos.x / MAX_X
    return 1.0 - ball_pos.x / MAX_X


def formation_position(number: int, ball_pos, side, aggression: float = 0.0,
                       attacking: bool = False, camping: bool = False):
    """Posição que este jogador deve ocupar, dada a posição da bola.

    A formação desliza com a bola: avança quando atacamos, recua quando
    defendemos, e comprime lateralmente na direção da bola.
    `aggression` (0..1) empurra a linha inteira para frente.

    P3 (attack_width): com `attacking=True` + gene ligado, os ATACANTES trocam
    a compressão lateral fixa (SHIFT_Y rumo à bola) por `attack_width_shift`
    (0 = manter a largura da base; negativo = abrir para o lado OPOSTO à
    bola — estica a defesa e o goleiro deles). Default (gene off ou
    attacking=False) = comportamento byte-idêntico ao histórico.
    """
    bx, by = BASE_FORMATION.get(number, (0.4, 0.5))
    adv = ball_advance_frac(ball_pos, side)

    # deslocamento longitudinal: a linha acompanha a bola
    x_frac = bx + SHIFT_X * (adv - 0.5) + 0.10 * aggression
    x_frac = max(0.02, min(0.92, x_frac))

    # v11/FORENSE (high_camp): PISO DE ACAMPAMENTO. Medido com a bola nossa:
    # temos 1,0 corpo (mediana ZERO) no terço de ataque, contra os 8-9 que o
    # BotAdversario2 mantém — porque a formação é centrada na BOLA e o coeficiente de
    # agressividade só desloca 0,10 da largura do campo. Com o gene, ATACANTES
    # (e opcionalmente meias) têm um piso de avanço INDEPENDENTE de onde a
    # bola está: é o "2-8" do BotAdversario2. Só age quando `attacking` (temos a
    # bola no ataque). off = byte-idêntico.
    if camping and P.get("high_camp") == "on":
        if number in FORWARDS:
            x_frac = max(x_frac, P["hc_floor_fwd"])
        elif number in MIDFIELDERS:
            x_frac = max(x_frac, P["hc_floor_mid"])
        x_frac = min(0.92, x_frac)

    # deslocamento lateral: comprime na direção da bola sem abandonar o lado
    y_shift = SHIFT_Y
    if attacking and number in FORWARDS and P.get("attack_width") == "on":
        y_shift = P["attack_width_shift"]
    ball_y_frac = ball_pos.y / MAX_Y
    y_frac = by + y_shift * (ball_y_frac - 0.5)
    y_frac = max(0.06, min(0.94, y_frac))

    return point(mirror_x(x_frac, side), y_frac * MAX_Y)


def time_to_ball(player, ball) -> float:
    """Turnos estimados até este jogador alcançar a bola."""
    r = intercept_turn(player.position, ball)
    if r is None:
        return math.inf
    return r[0]


def rank_by_ball_arrival(players, ball):
    """Ordena jogadores pelo tempo de chegada à bola."""
    return sorted(players, key=lambda p: time_to_ball(p, ball))


def chasers(inspector, n: int = 2):
    """Quais dos nossos jogadores devem ir à bola.

    Só os `n` que chegam primeiro. O goleiro nunca sai (tratado à parte).
    Esta é a diferença central para o baseline, que manda todos.
    """
    ball = inspector.get_ball()
    mates = [p for p in inspector.get_my_team_players()
             if p.number != GOALKEEPER]
    ranked = rank_by_ball_arrival(mates, ball)
    return [p.number for p in ranked[:n]]


def we_are_closest(inspector) -> bool:
    """Nosso time chega antes na bola que o adversário?"""
    ball = inspector.get_ball()
    mine = [p for p in inspector.get_my_team_players() if p.number != GOALKEEPER]
    theirs = [p for p in inspector.get_opponent_players() if p.number != GOALKEEPER]
    if not mine or not theirs:
        return True
    best_mine = min(time_to_ball(p, ball) for p in mine)
    best_theirs = min(time_to_ball(p, ball) for p in theirs)
    return best_mine <= best_theirs


def adaptive_chasers(inspector, base_n, margin_turns):
    """Nº de chasers adaptativo (item 5): quando ganhamos a bola com folga clara
    (best_theirs - best_mine >= margin_turns), usa 1 a menos — libera um corpo
    para o apoio/ataque; senão base_n. Determinístico: todos os jogadores
    concordam (calculam do mesmo estado compartilhado, sem histórico)."""
    ball = inspector.get_ball()
    mine = [p for p in inspector.get_my_team_players() if p.number != GOALKEEPER]
    theirs = [p for p in inspector.get_opponent_players() if p.number != GOALKEEPER]
    ranked = rank_by_ball_arrival(mine, ball)
    n = base_n
    if mine and theirs:
        best_mine = min(time_to_ball(p, ball) for p in mine)
        best_theirs = min(time_to_ball(p, ball) for p in theirs)
        if best_theirs - best_mine >= margin_turns:
            n = max(1, base_n - 1)
    return [p.number for p in ranked[:n]]


def marking_target(inspector, number: int):
    """Adversário que este jogador deve marcar (defesa por interceptação).

    Marcamos os adversários mais perigosos — os mais próximos do nosso gol —
    posicionando-nos entre eles e o gol, não em cima deles.
    """
    opponents = [p for p in inspector.get_opponent_players()
                 if p.number != GOALKEEPER]
    if not opponents:
        return None
    mates = sorted([p.number for p in inspector.get_my_team_players()
                    if p.number != GOALKEEPER])
    if number not in mates:
        return None
    idx = mates.index(number)
    ball = inspector.get_ball()
    # os mais próximos da bola são os mais perigosos
    ranked = sorted(opponents, key=lambda o: dist(o.position, ball.position))
    if idx < len(ranked):
        return ranked[idx]
    return None
