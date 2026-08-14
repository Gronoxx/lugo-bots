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
import planner
from params import P
from geometry import (BALL_MAX_SPEED, DANGEROUS_SHOT_RANGE, GOAL_MAX_Y,
                      GOAL_MIN_Y, MAX_X, MAX_Y, PLAYER_SPEED, dist,
                      lane_clearance, lead_target, opponent_can_intercept,
                      can_be_intercepted, intercept_risk,
                      point, speed_for_distance, turns_for_ball,
                      turns_for_player)

# Quantos jogadores perseguem a bola. O baseline manda 11; nós mandamos 2.
N_CHASERS = int(round(P["n_chasers"]))
# Margem de segurança para considerar uma linha de passe utilizável
PASS_MARGIN = P["pass_margin"]
# interceptação velocity-aware ligada? (gene use_velocity). Default off => v9.
USE_VELOCITY = (P.get("use_velocity") == "on")
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

            # 4) fora da zona: conduzir para o gol, desviando da pressão.
            #    carry_mode="touch": tocar a bola pro espaço à frente (self-pass)
            #    e correr atrás — explora "bola 4x o jogador" para progredir e
            #    passar por um marcador, SE o ponto for alcançável por mim antes
            #    dos adversários e a linha do toque estiver livre.
            if P.get("carry_mode") == "touch":
                touch = self._touch_target(inspector, goal_center, opponents)
                if touch is not None:
                    spd = speed_for_distance(dist(me.position, touch))
                    return [geo.kick_to(inspector, me, inspector.get_ball(),
                                        touch, spd)]
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

            # corrida ao 2º poste (far_post_run) tem prioridade quando ligada e a
            # jogada está madura. Default off.
            if P.get("far_post_run") == "on" and holder is not None:
                fp = self._far_post_target(inspector, holder, side)
                if fp is not None:
                    return [safe_move(inspector, me, fp)]

            if holder is None:
                return [safe_move(inspector, me, base)]

            # apoio ATIVO (support_mode="offer"): recebedores sobem oferecendo
            # linha de passe segura; default "v9" = oferta em anel (idêntico).
            if P.get("support_mode") == "offer":
                tgt = self._support_offer_run(inspector, holder, side, base)
                return [safe_move(inspector, me, tgt)]

            # v9 (default): se perto do portador, abrir linha de passe em vez de colar
            if dist(me.position, holder.position) < P["support_near_holder"]:
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
            chasers = (tac.adaptive_chasers(inspector, N_CHASERS, P["chase_margin"])
                       if P.get("chase_mode") == "adaptive"
                       else tac.chasers(inspector, N_CHASERS))

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
            chasers = (tac.adaptive_chasers(inspector, N_CHASERS, P["chase_margin"])
                       if P.get("chase_mode") == "adaptive"
                       else tac.chasers(inspector, N_CHASERS))

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

            # bloqueado por um defensor? velocity-aware se ligado;
            # USE_VELOCITY=False => opponent_can_intercept exato = v9.
            others = [o for o in opponents if gk is None or o.number != gk.number]
            if can_be_intercepted(me.position, target, others, BALL_MAX_SPEED,
                                  USE_VELOCITY):
                continue

            t_ball = turns_for_ball(BALL_MAX_SPEED, d)
            if t_ball == math.inf:
                continue

            # PISO DE POTÊNCIA DE CHEGADA (Problema 2): rejeita chute cuja
            # velocidade REAL de saída chega fraca ao alvo. shot_arrival_min=0
            # => inerte (=v9). 200 <=> alcance efetivo 6000.
            if P["shot_arrival_min"] > 0.0:
                v0_eff = geo.achievable_shot_speed(inspector, me,
                                                   inspector.get_ball(), target)
                if fin.arrival_speed(v0_eff, d) < P["shot_arrival_min"]:
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
            if P.get("shot_gate") == "slack" and gk is not None:
                # gate TEMPORAL calibrado: folga do alvo ao goleiro MENOS o quanto
                # ele cobre em t turnos (560 + gk_reach_speed·t). gk_reach_speed=75
                # calibrado (AUC 0.87 vs gol; slack>0 converte 43%, <=0 converte 0%).
                t_ball = turns_for_ball(BALL_MAX_SPEED, d)
                if t_ball == math.inf:
                    continue
                slack = abs(target.y - gk.position.y) - (560.0 + P["gk_reach_speed"] * t_ball)
                if slack <= P["shot_min_slack"]:
                    continue
                score = slack
            elif P.get("shot_gate") == "xg" and fin.available():
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
        """Melhor passe, ou None. POSSE OBJETIVA (Problema 1): retém a bola com
        passe seguro (linha executável + não interceptável), preferindo avanço;
        sob pressão aceita lateral/trás LIMITADO (pass_retain_backmax). Penaliza
        super-marcação acima de um limiar e premia a folga de interceptação.
        Nunca despeja no goleiro. DEFAULT = v9 com todos os genes desligados."""
        me = inspector.get_me()
        goal_center = self.mapper.get_attack_goal().get_center()
        opponents = list(inspector.get_opponent_players())
        mates = [p for p in inspector.get_my_team_players()
                 if p.number != self.number]

        # Componente 3: agressividade por estado de jogo (0.0 se game_state_mode off).
        game_aggr = self._game_aggr(inspector)

        # Componente 2: planejador NAO-GULOSO. So e' acionado quando o portador
        # esta MARCADO (adversario de linha a <= plan_trigger_turns): jogador LIVRE
        # dribla (medido vs oponente fraco: trocar drible dominante por passes
        # fragmenta a jogada e reduz gols). Achando cadeia segura de valor >
        # segurar, decide o passe imediato (MPC: so a 1a perna). off = v9.
        if P.get("pass_lookahead") != "off":
            gk_o = inspector.get_opponent_goalkeeper()
            if planner._nearest_opp_turns(me.position.x, me.position.y,
                                          opponents, gk_o) <= P["plan_trigger_turns"]:
                plan = planner.plan_pass(me, inspector.get_ball(), mates, opponents,
                                         goal_center, gk_o, USE_VELOCITY, game_aggr)
                if plan is not None:
                    tgt, spd = plan
                    return geo.kick_to(inspector, me, inspector.get_ball(), tgt, spd)

        my_gain = dist(me.position, goal_center)
        pressure = self._pressure_on(me.position, opponents)

        # Componente 1 ("quando passar"): status do portador (livre/atencao/
        # perigo) pela banda de turnos ate o adversario mais proximo. off => v9.
        status_on = P.get("pass_status_mode") == "on"
        holder_state = "livre"
        opp_gk = None
        if status_on:
            opp_gk = inspector.get_opponent_goalkeeper()
            holder_state, _ = self._player_status(me.position, opponents,
                                                  opp_gk, goal_center)

        under_pressure = False
        if P.get("pass_retain") == "on":
            t_press = min((turns_for_player(dist(me.position, o.position))
                           for o in opponents), default=math.inf)
            under_pressure = (pressure >= P["pass_retain_pressure"]
                              or t_press <= P["pass_retain_turns"])
        # atencao/perigo tambem ligam a retencao (escape antes do desarme): o
        # passe de escape leva chute+voo, entao esperar so "perigo" pode ser tarde.
        if status_on and holder_state in ("atencao", "perigo"):
            under_pressure = True

        best = None
        best_score = P["pass_min_score"]        # v9: 0.0
        if status_on:                            # barra de aceite por estado
            best_score = {"livre": P["pass_min_score_free"],
                          "atencao": P["pass_min_score_attention"],
                          "perigo": P["pass_min_score_danger"]}[holder_state]
        if P.get("game_state_mode") == "on":     # Comp 3: perseguir baixa a barra
            best_score -= game_aggr * P["game_aggr_scale"]
        retain = None
        retain_score = -1e18

        for mate in mates:
            if mate.number == tac.GOALKEEPER:
                continue
            d = dist(me.position, mate.position)
            if d < P["pass_min_dist"] or d > geo.MAX_KICK_RANGE:
                continue

            speed = min(BALL_MAX_SPEED, speed_for_distance(d) * P["pass_speed_mult"])
            # a bola COMPLETA o passe ao TOCAR o receptor (spec: "the player must
            # be touching the ball to catch it"), i.e. após percorrer
            # d - TOUCH_RADIUS (raio jogador 200 + raio bola 100 = 300), não até o
            # centro. pass_touch_lead="on" usa a distância de CONTATO no tempo de
            # chegada, para o lead não projetar o receptor à frente demais. off = v9.
            d_reach = d
            if P.get("pass_touch_lead") == "on":
                d_reach = max(1.0, d - geo.TOUCH_RADIUS)
            t_ball = turns_for_ball(speed, d_reach)
            if t_ball == math.inf:
                continue
            target = lead_target(mate, t_ball)

            # Fase A — reforço cirúrgico #1: segurança com a velocidade REALMENTE
            # executada. kick_to pode entregar menos que a planejada (redução por
            # ângulo + soma à velocidade atual da bola); checar o veto com a
            # planejada subestima o tempo que o adversário tem. off = v9.
            kick_speed = speed
            if P.get("pass_exec_speed") == "on":
                v_exec = geo.achievable_shot_speed(inspector, me,
                                                   inspector.get_ball(), target)
                kick_speed = min(speed, v_exec)
                if turns_for_ball(kick_speed, d) == math.inf:
                    continue      # a bola executada nem alcança o alvo

            # Fase A — reforço cirúrgico #2 (C3): corrida no destino. A linha pode
            # estar limpa em trânsito e a recepção ser disputada. Descarta se um
            # adversário chega ao ponto de recepção antes do receptor (+margem).
            # Mesmo padrão de _touch_target. off = v9.
            if P.get("pass_endpoint_race") == "on":
                t_recv = turns_for_player(dist(mate.position, target))
                if any(turns_for_player(dist(o.position, target))
                       <= t_recv + P["pass_endpoint_margin"] for o in opponents):
                    continue

            # veto de interceptação (velocity-aware se ligado). Uma varredura só:
            # quando pass_w_intercept>0 reusa intercept_risk p/ veto E score.
            r = None
            if P["pass_w_intercept"] > 0.0:
                r = intercept_risk(me.position, target, opponents, kick_speed, USE_VELOCITY)
                if r <= 0.0:
                    continue
            elif can_be_intercepted(me.position, target, opponents, kick_speed, USE_VELOCITY):
                continue

            mate_gain = dist(target, goal_center)
            advance = my_gain - mate_gain
            clearance = lane_clearance(me.position, target, opponents)
            mate_pressure = self._pressure_on(mate.position, opponents)

            # bônus de segurança da linha (posse objetiva). Gate por backmax:
            # NÃO premia passe que recua demais (revisor B) — não vira spam p/ trás.
            safety = 0.0
            if r is not None and advance > -P["pass_retain_backmax"]:
                safety = P["pass_w_intercept"] * PLAYER_SPEED * min(r, geo.INTERCEPT_RISK_CAP)

            # bônus de TROCA (switch): passar ao flanco OPOSTO, em espaço (v9).
            switch = 0.0
            if P["pass_w_switch"] > 0 and advance > -1000 \
                    and (target.y - MAX_Y / 2) * (me.position.y - MAX_Y / 2) < 0 \
                    and my_gain < 0.6 * MAX_X:
                lateral_gain = abs(target.y - MAX_Y / 2) - abs(me.position.y - MAX_Y / 2)
                near = min((dist(target, o.position) for o in opponents), default=1e9)
                switch = (P["pass_w_switch"] * max(0.0, lateral_gain)
                          * min(near, 1700.0) / 1700.0)

            # bonus/penalidade pelo STATUS do receptor (Componente 1): preferir
            # terminar em companheiro LIVRE, evitar receptor em PERIGO. 0 = v9.
            recv_bonus = 0.0
            if status_on and P["pass_w_recv_free"] > 0.0:
                recv_state, _ = self._player_status(target, opponents,
                                                    opp_gk, goal_center)
                if recv_state == "livre":
                    recv_bonus = P["pass_w_recv_free"]
                elif recv_state == "perigo":
                    recv_bonus = -P["pass_w_recv_free"]

            score = (advance
                     + P["pass_w_clearance"] * clearance
                     - P["pass_w_mate_pressure"] * mate_pressure
                     + P["pass_w_pressure_bonus"] * pressure_bonus(pressure)
                     + switch
                     - P["pass_w_overmark"] * max(0.0, mate_pressure
                                                  - P["pass_mark_threshold"])
                     + safety
                     + recv_bonus)

            # candidato de RETENÇÃO: passe seguro que perde menos avanço, recuo
            # LIMITADO por pass_retain_backmax. Habilitado por pass_retain="on" OU
            # (Componente 1) portador em atencao/perigo (escape seguro).
            retain_enabled = (P.get("pass_retain") == "on"
                              or (status_on and holder_state in ("atencao", "perigo")))
            if retain_enabled and advance > -P["pass_retain_backmax"]:
                rscore = (clearance
                          + P["pass_retain_advance_w"] * advance
                          - P["pass_w_mate_pressure"] * mate_pressure)
                if rscore > retain_score:
                    retain_score, retain = rscore, (target, speed)

            # recuo grande só passa sob pressão (floor=20000 => nunca corta = v9)
            if advance < -P["pass_backward_floor"] and not under_pressure:
                continue

            if score > best_score:
                best_score, best = score, (target, speed)

        if best is None and under_pressure and retain is not None:
            best = retain
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

    def _touch_target(self, inspector, goal_center, opponents):
        """Ponto à frente para TOCAR a bola (self-pass) e correr atrás: espaço
        livre num cone rumo ao gol, a `carry_step`, alcançável por mim antes de
        qualquer adversário e com a linha do toque livre. None se nada seguro."""
        me = inspector.get_me()
        mx, my = me.position.x, me.position.y
        base = math.atan2(goal_center.y - my, goal_center.x - mx)
        step = P["carry_step"]
        my_turns = turns_for_player(step)
        opp_list = list(opponents)
        best, best_score = None, -1e18
        for deg in range(-40, 41, 10):
            a = base + math.radians(deg)
            cand = point(mx + math.cos(a) * step, my + math.sin(a) * step)
            # eu chego ao ponto antes de qualquer adversário?
            if any(turns_for_player(dist(o.position, cand)) <= my_turns + 1.0
                   for o in opp_list):
                continue
            spd = speed_for_distance(dist(me.position, cand))
            # a linha do toque está livre (o toque não é interceptado)?
            if opponent_can_intercept(me.position, cand, opp_list, spd):
                continue
            near = min((dist(cand, o.position) for o in opp_list), default=1e9)
            advance = dist(me.position, goal_center) - dist(cand, goal_center)
            score = min(near, 2000.0) + 0.6 * advance
            if score > best_score:
                best_score, best = score, cand
        return best

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

    def _support_offer_run(self, inspector, holder, side, base):
        """Designa deterministicamente quem sobe (recebedor) e em qual canal; os
        demais mantêm a forma OU o outlet curto da v9 (fusível anti-Problema 1)."""
        me = inspector.get_me()
        if self.number not in tac.MIDFIELDERS and self.number not in tac.FORWARDS:
            return base                              # FUSÍVEL: zagueiros/GK não sobem

        eligible = [p for p in inspector.get_my_team_players()
                    if p.number != tac.GOALKEEPER
                    and p.number != holder.number
                    and (p.number in tac.MIDFIELDERS or p.number in tac.FORWARDS)]

        if P.get("far_post_run") == "on":
            fp_num = self._far_post_runner(inspector, holder, side)
            if fp_num is not None:
                eligible = [p for p in eligible if p.number != fp_num]
        if not eligible:
            return base

        # eleição por PAPEL (atacantes por número, depois meias): estável no tempo,
        # sem flicker por ruído de posição, determinística sem história (revisor C).
        eligible.sort(key=lambda p: (0 if p.number in tac.FORWARDS else 1, p.number))
        n_run = int(round(P["support_n_forward"]))
        runners = eligible[:max(0, n_run)]

        if all(p.number != self.number for p in runners):
            # não sou runner: perto do portador ainda ofereço a linha CURTA da v9
            # (preserva o outlet curto — revisor A).
            if dist(me.position, holder.position) < P["support_near_holder"]:
                return self._support_offer(inspector, holder, base)
            return base

        # LARGURA: runners por y -> canais espalhados sem cruzamento.
        R = len(runners)
        by_y = sorted(runners, key=lambda p: (p.position.y, p.number))
        slot = next(i for i, p in enumerate(by_y) if p.number == self.number)
        off = 0.0 if R == 1 else (-1.0 + 2.0 * slot / (R - 1))
        # canais centrados no y do PORTADOR (clamp à boca do gol), não no meio do
        # campo -> ofertas em linhas usáveis (revisor D).
        center_y = max(GOAL_MIN_Y, min(GOAL_MAX_Y, holder.position.y))
        channel_y = center_y + off * P["support_channel_width"]
        return self._offer_point(inspector, holder, channel_y, base)

    def _offer_point(self, inspector, holder, channel_y, base):
        """Ponto de recepção à frente do portador no canal dado. Reusa
        lane_clearance, _pressure_on e o veto velocity-aware (revisor B)."""
        opponents = list(inspector.get_opponent_players())
        goal = self.mapper.get_attack_goal().get_center()
        mates = [p for p in inspector.get_my_team_players()
                 if p.number != self.number and p.number != holder.number]

        dir_sign = 1.0 if goal.x > holder.position.x else -1.0
        anchor_x = holder.position.x + dir_sign * P["support_advance"]
        d_holder_goal = dist(holder.position, goal)
        step = P["support_off_search_r"]

        best, best_score = None, -1e18
        for r_mult in (0.0, 1.0, 2.0):
            radius = step * r_mult
            n_ang = 1 if radius == 0.0 else 8
            for k in range(n_ang):
                a = 2.0 * math.pi * k / n_ang if n_ang > 1 else 0.0
                cand = point(anchor_x + math.cos(a) * radius,
                             channel_y + math.sin(a) * radius)
                if dir_sign * (cand.x - holder.position.x) < -300.0:
                    continue
                pd = dist(holder.position, cand)
                if pd < P["pass_min_dist"] or pd > geo.MAX_KICK_RANGE:
                    continue
                clearance = lane_clearance(holder.position, cand, opponents)
                if clearance < PASS_MARGIN:
                    continue
                spd = speed_for_distance(pd)
                if can_be_intercepted(holder.position, cand, opponents, spd,
                                      USE_VELOCITY):
                    continue
                advance = d_holder_goal - dist(cand, goal)
                press = self._pressure_on(cand, opponents)
                crowd = 0.0
                if mates:
                    dmin = min(dist(cand, p.position) for p in mates)
                    crowd = max(0.0, P["support_crowd_radius"] - dmin)
                score = (P["support_off_w_advance"] * advance
                         + P["support_off_w_clear"] * clearance
                         - P["support_off_w_press"] * press
                         - P["support_off_w_crowd"] * crowd)
                if score > best_score:
                    best_score, best = score, cand
        return best if best is not None else base

    def _far_post_runner(self, inspector, holder, side):
        """Número do atacante eleito à corrida ao 2º poste, ou None. Determinístico."""
        hy = holder.position.y
        mid = MAX_Y / 2.0
        if tac.ball_advance_frac(holder.position, side) < 0.62:
            return None
        if abs(hy - mid) < 1200.0:
            return None
        forwards = [p for p in inspector.get_my_team_players()
                    if p.number in tac.FORWARDS and p.number != holder.number]
        if not forwards:
            return None
        sign = 1.0 if hy >= mid else -1.0
        return min(forwards, key=lambda p: sign * (p.position.y - mid)).number

    def _far_post_target(self, inspector, holder, side):
        if self.number not in tac.FORWARDS:
            return None
        if self._far_post_runner(inspector, holder, side) != self.number:
            return None
        hy = holder.position.y
        mid = MAX_Y / 2.0
        goal_center = self.mapper.get_attack_goal().get_center()
        far_y = GOAL_MAX_Y - 350.0 if hy < mid else GOAL_MIN_Y + 350.0
        inward = -1400.0 if goal_center.x > MAX_X / 2 else 1400.0
        return point(goal_center.x + inward, far_y)

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

    @staticmethod
    def _player_status(pos, opponents, opp_gk, goal_center):
        """(estado, t_reach) do jogador em `pos`. estado in {"livre","atencao",
        "perigo"} pela banda de turnos ate o adversario mais proximo alcancar
        `pos`. Coerente com o veto: turns_for_player(d)=(d-300)/100. O goleiro
        adversario e' EXCLUIDO por padrao (status_count_gk="off"); com "on" entra
        com reach 560. Velocity-aware se USE_VELOCITY (so ANTECIPA a ameaca).
        status_measure="ball" mede ~200 a frente, rumo ao gol de ataque. So e'
        chamado com pass_status_mode="on"; o caminho default (off) nunca executa."""
        tx, ty = float(pos.x), float(pos.y)
        if P.get("status_measure") == "ball":
            dx, dy = goal_center.x - pos.x, goal_center.y - pos.y
            m = math.hypot(dx, dy)
            if m > 1e-9:
                tx += 200.0 * dx / m       # a bola fica ~200 a frente do portador
                ty += 200.0 * dy / m
        count_gk = (P.get("status_count_gk") == "on")
        gk_num = opp_gk.number if opp_gk is not None else -1
        t_reach = math.inf
        for o in opponents:
            is_gk = (o.number == gk_num)
            if is_gk and not count_gk:
                continue
            d = math.hypot(tx - o.position.x, ty - o.position.y)
            if USE_VELOCITY:                # so pode APROXIMAR a ameaca
                lx, ly = geo._lead_pos(o, geo.INTERCEPT_LEAD_TURNS)
                d = min(d, math.hypot(tx - lx, ty - ly))
            reach = geo.GOALKEEPER_HALF_EXTENT if is_gk else geo.TOUCH_RADIUS
            t_o = max(0.0, d - reach) / PLAYER_SPEED
            if t_o < t_reach:
                t_reach = t_o
        if t_reach <= P["status_danger_turns"]:
            return "perigo", t_reach
        if t_reach <= P["status_attention_turns"]:
            return "atencao", t_reach
        return "livre", t_reach

    @staticmethod
    def _game_aggr(inspector):
        """Agressividade por estado de jogo (Componente 3, game_state_mode="on"):
        -1 (proteger vantagem) .. 0 (neutro) .. +1 (perseguir). off => 0.0.
        Calibrado: futebol real ~2,9 gols/jogo, Lugo ~4,7-6,9 => 'vantagem
        confortavel' ~3-4 gols (lead_comfortable). So cresce no fim de jogo."""
        if P.get("game_state_mode") != "on":
            return 0.0
        turn = inspector.get_turn()
        margin = inspector.get_my_team().score - inspector.get_opponent_team().score
        L = max(1.0, P["late_game_turns"])
        late = min(1.0, max(0.0, (turn - (6000.0 - L)) / L))
        lead = max(-1.0, min(1.0, margin / max(1.0, P["lead_comfortable"])))
        return max(-1.0, min(1.0, -lead * late))


def pressure_bonus(pressure: float) -> float:
    """Sob pressão, passar vale mais do que conduzir."""
    return min(1.0, pressure / 2.0)
