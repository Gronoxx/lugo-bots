"""
Bot principal.

Decisões derivadas da análise física (ver analysis/):
  - o chute máximo alcança 8000d; só é perigoso a <=6000d do gol
  - a bola é até 4x mais rápida que o jogador: passar > correr
  - o campo é esparso (raio livre médio ~1700d): manter forma cria linhas de passe
  - o goleiro cobre 53% do gol só se antecipar o lado; o pulo trava 3 turnos
"""

import math
import traceback
from abc import ABC
from typing import List

import lugo4py

import geometry as geo
import tactics as tac
import finishing as fin
from params import P
from geometry import (BALL_MAX_SPEED, DANGEROUS_SHOT_RANGE, GOAL_MAX_Y,
                      GOAL_MIN_Y, MAX_X, MAX_Y, PLAYER_SPEED, dist,
                      lane_clearance, lead_target, opponent_can_intercept,
                      point, speed_for_distance, turns_for_ball,
                      turns_for_player)

# Quantos jogadores perseguem a bola. O baseline manda 11; nós mandamos 2.
N_CHASERS = int(round(P["n_chasers"]))
# Margem de segurança para considerar uma linha de passe utilizável
PASS_MARGIN = P["pass_margin"]
# Abaixo disto, o alvo é indistinguível da posição atual e lugo4py lança
# "A vector cannot have zero length" — o que faz o jogador perder o turno.
MIN_MOVE_DIST = 12.0


def safe_move(inspector, me, target):
    """Ordem de movimento robusta a alvo coincidente com a posição atual.

    Dois problemas do lugo4py são contornados aqui:
      1. construir um vetor de comprimento zero levanta RuntimeError, o que
         (dentro do try/except das callbacks) deixaria o jogador parado sem
         nenhum sinal visível;
      2. `make_order_move_to_stop()` está quebrado na versão 1.0.5 — chama
         `me.get_velocity()`, método que não existe no objeto protobuf.
    Para parar, emitimos um movimento com velocidade 0 na direção de um ponto
    deslocado, o que é sempre um vetor válido.
    """
    if dist(me.position, target) < MIN_MOVE_DIST:
        nudge = point(me.position.x + 100, me.position.y)
        return inspector.make_order_move(nudge, 0)
    return inspector.make_order_move_max_speed(target)


class MyBot(lugo4py.Bot, ABC):

    # ---------------------------------------------------------------- posse
    def on_holding(self, inspector) -> List[lugo4py.Order]:
        try:
            me = inspector.get_me()
            goal = self.mapper.get_attack_goal()
            opponents = inspector.get_opponent_players()
            goal_center = goal.get_center()
            d_goal = dist(me.position, goal_center)

            # 1) finalizar, se estivermos em alcance perigoso e com ângulo
            if d_goal <= P["dangerous_shot_range"]:
                target = self._best_shot_target(inspector, goal)
                if target is not None:
                    return [geo.kick_to(inspector, me, inspector.get_ball(),
                                        target, BALL_MAX_SPEED)]

            # 2) passar, se houver companheiro melhor posicionado
            pass_order = self._best_pass(inspector)
            if pass_order is not None:
                return [pass_order]

            # 3) sem chute nem passe: em vez de conduzir para o meio (onde o
            #    goleiro já está), buscar o ângulo lateral que cria a chance.
            #    Medido nos replays: chutes com folga do goleiro >1800 convertem
            #    45% e saem de |y-5000| mediano 1756, mirando a trave; chutes de
            #    folga <1200 convertem 0% e saem de |y-5000| 1050, mirando o
            #    centro. A distância ao gol é a MESMA nos dois grupos (3013 vs
            #    3209) — o que separa é o ângulo, não a proximidade.
            if P["angle_seek"] == "on" and d_goal <= P["dangerous_shot_range"]:
                angle_target = self._angle_target(inspector, goal_center)
                if angle_target is not None:
                    return [safe_move(inspector, me, angle_target)]

            # 4) fora da zona: conduzir para o gol, desviando da pressão
            target = self._carry_target(inspector, goal_center, opponents)
            return [safe_move(inspector, me, target)]

        except Exception as e:
            print(f'on_holding: {e}')
            traceback.print_exc()
            return []

    # ------------------------------------------------------------ apoiando
    def on_supporting(self, inspector) -> List[lugo4py.Order]:
        try:
            me = inspector.get_me()
            ball = inspector.get_ball()
            holder = inspector.get_ball_holder()
            side = inspector.get_my_team_side()

            # posição de formação, deslocada para frente (estamos atacando)
            base = tac.formation_position(self.number, ball.position, side,
                                          aggression=P["aggression_support"])

            # se estou perto do portador, abrir linha de passe em vez de colar
            if holder is not None and dist(me.position, holder.position) < P["support_near_holder"]:
                base = self._support_offer(inspector, holder, base)

            return [safe_move(inspector, me, base)]

        except Exception as e:
            print(f'on_supporting: {e}')
            traceback.print_exc()
            return []

    # ----------------------------------------------------------- defendendo
    def on_defending(self, inspector) -> List[lugo4py.Order]:
        try:
            me = inspector.get_me()
            ball = inspector.get_ball()
            side = inspector.get_my_team_side()
            chasers = tac.chasers(inspector, N_CHASERS)

            if self.number in chasers:
                # pressiona o portador pelo lado do nosso gol (corta o avanço)
                r = geo.intercept_turn(me.position, ball)
                target = r[1] if r else ball.position
                return [safe_move(inspector, me, target),
                        inspector.make_order_catch()]

            # os demais recuam em formação, entre a bola e o nosso gol
            base = tac.formation_position(self.number, ball.position, side,
                                          aggression=P["aggression_defend"])
            cover = self._cover_position(inspector, base)
            return [safe_move(inspector, me, cover),
                    inspector.make_order_catch()]

        except Exception as e:
            print(f'on_defending: {e}')
            traceback.print_exc()
            return []

    # ---------------------------------------------------------- disputando
    def on_disputing(self, inspector) -> List[lugo4py.Order]:
        try:
            me = inspector.get_me()
            ball = inspector.get_ball()
            side = inspector.get_my_team_side()
            chasers = tac.chasers(inspector, N_CHASERS)

            if self.number in chasers:
                r = geo.intercept_turn(me.position, ball)
                target = r[1] if r else ball.position
                return [safe_move(inspector, me, target),
                        inspector.make_order_catch()]

            base = tac.formation_position(self.number, ball.position, side,
                                          aggression=0.0)
            return [safe_move(inspector, me, base),
                    inspector.make_order_catch()]

        except Exception as e:
            print(f'on_disputing: {e}')
            traceback.print_exc()
            return []

    # ------------------------------------------------------------- goleiro
    def as_goalkeeper(self, inspector, state) -> List[lugo4py.Order]:
        try:
            me = inspector.get_me()
            ball = inspector.get_ball()
            my_goal = self.mapper.get_defense_goal()
            goal_center = my_goal.get_center()

            # se estou com a bola, tocar para um companheiro livre
            if inspector.is_ball_holder(me):
                pass_order = self._goalkeeper_clearance(inspector)
                if pass_order is not None:
                    return [pass_order]

            # onde a bola cruza a linha do gol
            threat = self._goal_line_threat(inspector, goal_center)
            if threat is not None:
                cross_point, turns = threat
                d = dist(me.position, cross_point)
                # não dá para chegar andando: pular (trava 3 turnos, usar por último)
                if turns_for_player(d) > turns and turns <= P["gk_jump_max_turns"]:
                    return [inspector.make_order_jump(
                        cross_point, lugo4py.GOALKEEPER_JUMP_SPEED),
                        inspector.make_order_catch()]
                return [safe_move(inspector, me, cross_point),
                        inspector.make_order_catch()]

            # sem ameaça direta: cobrir o ângulo entre a bola e o gol
            guard = self._guard_position(inspector, goal_center)
            return [safe_move(inspector, me, guard),
                    inspector.make_order_catch()]

        except Exception as e:
            print(f'as_goalkeeper: {e}')
            traceback.print_exc()
            return []

    def getting_ready(self, snapshot):
        pass

    # ================================================================ ajuda

    def _best_shot_target(self, inspector, goal):
        """Melhor ponto do gol para finalizar, ou None se não há ângulo.

        Testa pontos ao longo da boca do gol e escolhe o que maximiza a
        distância ao goleiro adversário mantendo a linha livre.
        """
        me = inspector.get_me()
        opponents = list(inspector.get_opponent_players())
        gk = inspector.get_opponent_goalkeeper()
        goal_x = goal.get_center().x

        best = None
        best_score = -1.0
        # amostra a boca do gol, evitando as traves
        for i in range(9):
            frac = i / 8
            m = P["shot_post_margin"]
            y = GOAL_MIN_Y + m + frac * (GOAL_MAX_Y - GOAL_MIN_Y - 2 * m)
            target = point(goal_x, y)
            d = dist(me.position, target)
            if d > geo.MAX_KICK_RANGE:
                continue

            # bloqueado por um defensor no caminho?
            others = [o for o in opponents if gk is None or o.number != gk.number]
            if opponent_can_intercept(me.position, target, others, BALL_MAX_SPEED):
                continue

            t_ball = turns_for_ball(BALL_MAX_SPEED, d)
            if t_ball == math.inf:
                continue

            # Portão EMPÍRICO, não teórico.
            #
            # O modelo anterior assumia que o goleiro sempre pula a 200 d/turno
            # por 3 turnos e segue a 100 — pessimista demais. Medido: ele se move
            # a 100 d/turno (mediana) e raramente pula. Esse portão fechava em
            # ~99% dos turnos em zona, e as duas versões que o usaram pararam de
            # finalizar — a v8 caiu para 0,69 gols contra 3,31 da v3 (n=16 cada,
            # erro padrão 0,59: conclusivo).
            #
            # A regra abaixo vem dos RESULTADOS, não de um modelo. Folga lateral
            # do goleiro até o ponto de cruzamento, em 135 chutes medidos:
            #   < 1200  -> 0% de gol (58 chutes, nenhum gol)
            #   1200-1800 -> 29%
            #   > 1800  -> 45%
            # Chutar com folga pequena é desperdício; exigir folga demais faz o
            # bot nunca chutar. O limiar é um gene, para a evolução ajustá-lo.
            if P.get("shot_gate") == "xg" and fin.available():
                # modelo xG: mesmas features do treino (reta bola->alvo).
                # dist_line = d (alvo na linha do gol); ycross = target.y.
                ux, uy = target.x - me.position.x, target.y - me.position.y
                nrm = math.hypot(ux, uy) or 1.0
                ux, uy = ux / nrm, uy / nrm
                if gk is not None:
                    tp = ((gk.position.x - me.position.x) * ux
                          + (gk.position.y - me.position.y) * uy)
                    tp = max(0.0, min(tp, d))
                    cx, cy = me.position.x + ux * tp, me.position.y + uy * tp
                    gkd = math.hypot(gk.position.x - cx, gk.position.y - cy)
                else:
                    gkd = 3000.0
                v_arr = fin.arrival_speed(BALL_MAX_SPEED, d)
                p_goal = fin.xg(d, v_arr, gkd, abs(target.y - MAX_Y / 2))
                if p_goal is None or p_goal < P["shot_min_xg"]:
                    continue
                score = p_goal
            elif gk is not None:
                gap = abs(gk.position.y - target.y)
                if gap < P["shot_min_gap"]:
                    continue
                score = gap - P["shot_gk_penalty"] * d
            else:
                score = 1e6 - d

            if score > best_score:
                best_score, best = score, target
        return best

    def _best_pass(self, inspector):
        """Melhor passe disponível, ou None se conduzir for melhor.

        Pontua cada companheiro por ganho de avanço, segurança da linha e
        proximidade ao gol, e só passa se o ganho for relevante.
        """
        me = inspector.get_me()
        side = inspector.get_my_team_side()
        goal_center = self.mapper.get_attack_goal().get_center()
        opponents = list(inspector.get_opponent_players())
        mates = [p for p in inspector.get_my_team_players()
                 if p.number != self.number]

        my_gain = dist(me.position, goal_center)
        pressure = self._pressure_on(me.position, opponents)

        best = None
        best_score = 0.0
        for mate in mates:
            if mate.number == tac.GOALKEEPER:
                continue
            d = dist(me.position, mate.position)
            if d < P["pass_min_dist"] or d > geo.MAX_KICK_RANGE:
                continue

            speed = min(BALL_MAX_SPEED, speed_for_distance(d) * P["pass_speed_mult"])
            t_ball = turns_for_ball(speed, d)
            if t_ball == math.inf:
                continue
            target = lead_target(mate, t_ball)

            if opponent_can_intercept(me.position, target, opponents, speed):
                continue

            # ganho: aproxima do gol?
            mate_gain = dist(target, goal_center)
            advance = my_gain - mate_gain
            clearance = lane_clearance(me.position, target, opponents)
            mate_pressure = self._pressure_on(mate.position, opponents)

            score = (advance
                     + P["pass_w_clearance"] * clearance
                     - P["pass_w_mate_pressure"] * mate_pressure
                     + P["pass_w_pressure_bonus"] * pressure_bonus(pressure))
            if score > best_score:
                best_score, best = score, (target, speed)

        if best is None:
            return None
        target, speed = best
        return geo.kick_to(inspector, me, inspector.get_ball(), target, speed)

    def _angle_target(self, inspector, goal_center):
        """Para onde levar a bola quando estamos em zona mas sem ângulo.

        Escolhe o lado (acima/abaixo) que oferece maior folga do goleiro à trave
        correspondente, e mira uma posição lateral a ~`shot_lateral` do centro,
        mantendo a distância de finalização. É a alternativa a conduzir para o
        meio, onde o goleiro já está posicionado.
        """
        me = inspector.get_me()
        gk = inspector.get_opponent_goalkeeper()
        gk_y = gk.position.y if gk is not None else MAX_Y / 2
        opponents = list(inspector.get_opponent_players())

        lateral = P["shot_lateral"]
        best, best_score = None, -1e18
        for sign in (1, -1):
            post_y = GOAL_MAX_Y - 250 if sign > 0 else GOAL_MIN_Y + 250
            # folga que o goleiro teria contra um chute nessa trave
            gap = abs(gk_y - post_y)
            cand_y = MAX_Y / 2 + sign * lateral
            # manter a distância de finalização, só mudando o ângulo
            d_keep = min(dist(me.position, goal_center), P["dangerous_shot_range"])
            dy = cand_y - goal_center.y
            dx2 = max(0.0, d_keep ** 2 - dy ** 2)
            cand_x = goal_center.x + (-1 if goal_center.x > MAX_X / 2 else 1) * math.sqrt(dx2)
            cand = point(cand_x, cand_y)
            # não escolher um destino sob pressão nem longe demais
            press = self._pressure_on(cand, opponents)
            score = gap - 400.0 * press - 0.15 * dist(me.position, cand)
            if score > best_score:
                best_score, best = score, cand
        return best

    def _carry_target(self, inspector, goal_center, opponents):
        """Para onde conduzir a bola, desviando do adversário mais próximo."""
        me = inspector.get_me()
        # direção base: o gol
        dx = goal_center.x - me.position.x
        dy = goal_center.y - me.position.y
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n

        # repulsão dos adversários próximos
        rx = ry = 0.0
        for o in opponents:
            d = dist(me.position, o.position)
            R = P["carry_repulsion_radius"]
            if d < R and d > 0:
                w = (R - d) / R
                rx += (me.position.x - o.position.x) / d * w
                ry += (me.position.y - o.position.y) / d * w

        k = P["carry_repulsion_weight"]
        vx = dx + k * rx
        vy = dy + k * ry
        n2 = math.hypot(vx, vy) or 1.0
        step = P["carry_step"]
        return point(me.position.x + vx / n2 * step,
                     me.position.y + vy / n2 * step)

    def _support_offer(self, inspector, holder, fallback):
        """Posição de apoio que abre linha de passe para o portador."""
        me = inspector.get_me()
        opponents = list(inspector.get_opponent_players())
        goal_center = self.mapper.get_attack_goal().get_center()

        best, best_score = fallback, -1e18
        # testa posições ao redor da posição atual
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            for radius in (P["support_radius_a"], P["support_radius_b"]):
                cand = point(me.position.x + math.cos(a) * radius,
                             me.position.y + math.sin(a) * radius)
                clearance = lane_clearance(holder.position, cand, opponents)
                if clearance < PASS_MARGIN:
                    continue
                d_goal = dist(cand, goal_center)
                press = self._pressure_on(cand, opponents)
                score = -d_goal + P["support_w_clearance"] * clearance - P["support_w_pressure"] * press
                if score > best_score:
                    best_score, best = score, cand
        return best

    def _cover_position(self, inspector, base):
        """Posição defensiva: entre a bola e o nosso gol, perto do posto."""
        ball = inspector.get_ball()
        goal_center = self.mapper.get_defense_goal().get_center()
        # 30% do caminho da bola para o gol, misturado com a posição de formação
        cm = P["cover_mix"]
        mid_x = ball.position.x + (goal_center.x - ball.position.x) * cm
        mid_y = ball.position.y + (goal_center.y - ball.position.y) * cm
        return point(0.5 * base.x + 0.5 * mid_x,
                     0.5 * base.y + 0.5 * mid_y)

    def _goal_line_threat(self, inspector, goal_center):
        """Se a bola vai cruzar a linha do gol, retorna (ponto, turnos)."""
        ball = inspector.get_ball()
        if ball.velocity.speed <= 5:
            return None
        traj = geo.ball_trajectory(ball, max_turns=40)
        goal_x = goal_center.x
        prev = (ball.position.x, ball.position.y)
        for t, x, y in traj:
            # cruzou o plano do gol?
            crossed = (prev[0] - goal_x) * (x - goal_x) <= 0
            near = abs(x - goal_x) < P["gk_threat_near"]
            if (crossed or near) and GOAL_MIN_Y - 600 <= y <= GOAL_MAX_Y + 600:
                return point(goal_x, y), t
            prev = (x, y)
        return None

    def _guard_position(self, inspector, goal_center):
        """Posição de espera do goleiro: na bissetriz bola-gol, perto da linha."""
        ball = inspector.get_ball()
        dy = ball.position.y - goal_center.y
        # segue a bola em y, limitado à boca do gol
        y = goal_center.y + max(-1.0, min(1.0, dy / 3000.0)) * P["gk_y_range"]
        y = max(GOAL_MIN_Y + 150, min(GOAL_MAX_Y - 150, y))
        # sai um pouco da linha para fechar o ângulo quando a bola está longe
        # O servidor mantém o goleiro preso à linha (x observado ∈ {0, 20000}),
        # então pedir x deslocado só rouba velocidade do movimento em y — que é
        # o único eixo em que ele realmente defende.
        return point(goal_center.x, y)

    def _goalkeeper_clearance(self, inspector):
        """Goleiro com a bola: passar para o companheiro livre mais avançado."""
        me = inspector.get_me()
        opponents = list(inspector.get_opponent_players())
        goal_center = self.mapper.get_attack_goal().get_center()
        mates = [p for p in inspector.get_my_team_players()
                 if p.number != self.number]

        best, best_score = None, -1e18
        for mate in mates:
            d = dist(me.position, mate.position)
            if d < 600 or d > geo.MAX_KICK_RANGE:
                continue
            speed = min(BALL_MAX_SPEED, speed_for_distance(d) * P["gk_clearance_speed_mult"])
            t_ball = turns_for_ball(speed, d)
            if t_ball == math.inf:
                continue
            target = lead_target(mate, t_ball)
            if opponent_can_intercept(me.position, target, opponents, speed):
                continue
            score = -dist(target, goal_center) + 1.5 * lane_clearance(
                me.position, target, opponents)
            if score > best_score:
                best_score, best = score, (target, speed)

        if best is None:
            # ninguém livre: afastar a bola para a lateral avançada
            far_y = 500 if me.position.y > MAX_Y / 2 else MAX_Y - 500
            target = point(goal_center.x * 0.35 + me.position.x * 0.65, far_y)
            return geo.kick_to(inspector, me, inspector.get_ball(), target,
                               BALL_MAX_SPEED)
        target, speed = best
        return geo.kick_to(inspector, me, inspector.get_ball(), target, speed)

    @staticmethod
    def _pressure_on(pos, opponents) -> float:
        """Pressão adversária sobre uma posição (soma ponderada por proximidade)."""
        p = 0.0
        for o in opponents:
            d = dist(pos, o.position)
            R = P["pressure_radius"]
            if d < R:
                p += (R - d) / R
        return p


def pressure_bonus(pressure: float) -> float:
    """Sob pressão, passar vale mais do que conduzir."""
    return min(1.0, pressure / 2.0)
