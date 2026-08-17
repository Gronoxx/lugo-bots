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
import carry
import shooting
import finish_play
import setplays
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

    def _update_transition(self, inspector):
        """Estado LEVE por processo (programa tático 2026-08): re-derivável do
        snapshot (robusto a reconexão — processo novo converge em ≤1 turno).
        NUNCA lido dentro de _best_pass (o mock do decide_dump não tem
        snapshot/turn). Campos: _reset_turn (kickoff, P2), _last_our_hold
        (contrapressão P4 / segunda bola P3)."""
        try:
            turn = inspector.get_snapshot().turn
            ball = inspector.get_ball()
            h = inspector.get_ball_holder()
            held = h is not None and h.number != 0
            # fallback do reset por assinatura (getting_ready é a via primária):
            # bola parada no centro, sem dono
            if (not held and ball.velocity.speed < 5
                    and abs(ball.position.x - MAX_X / 2.0) <= 60
                    and abs(ball.position.y - MAX_Y / 2.0) <= 60):
                rt = getattr(self, "_reset_turn", None)
                if rt is None or turn - rt > 30:
                    self._reset_turn = turn
                    self._ko_abort = False   # v7 c0: idem via fallback
            if held and h.team_side == inspector.get_my_team_side():
                self._last_our_hold = turn
            # P4 (counterpress): perda RECENTE fora do nosso terço arma a
            # janela de contrapressão (só re-arma depois de fechada).
            elif held:
                lo = getattr(self, "_last_our_hold", None)
                if (lo is not None and turn - lo <= 3
                        and turn > getattr(self, "_cp_until", -1)
                        and tac.ball_advance_frac(
                            ball.position,
                            inspector.get_my_team_side()) >= P["cp_min_frac"]):
                    self._cp_until = turn + int(round(P["cp_window"]))
                # v7/METAMORFO (counter_press_window): perda no campo
                # ADVERSÁRIO (frac >= cpw_min_frac) arma a janela de marcação
                # das LINHAS do 1º passe (revisita do counterpress com OUTRO
                # mecanismo: mesmos chasers; corpos altos marcam receptores —
                # o BotAdversario1 roubou 52 bolas do BotAdversario12 e criou 0: roubada sem
                # transição é estéril). Arming guardado pelo gene (sem estado
                # morto).
                if (P.get("counter_press_window") == "on" and lo is not None
                        and turn - lo <= 3
                        and turn > getattr(self, "_cpw_until", -1)
                        and tac.ball_advance_frac(
                            ball.position,
                            inspector.get_my_team_side()) >= P["cpw_min_frac"]):
                    self._cpw_until = turn + int(round(P["cpw_window"]))
            # P3 (second_ball): NOSSO chute detectado = bola ficou livre e
            # rápida rumo ao gol de ataque logo após posse nossa. Se um
            # companheiro dominar (viramos HOLDING), a janela morre sozinha.
            elif not held and ball.velocity.speed >= 300.0:
                lo = getattr(self, "_last_our_hold", None)
                if lo is not None and turn - lo <= 2:
                    gc = self.mapper.get_attack_goal().get_center()
                    vx, vy = ball.velocity.direction.x, ball.velocity.direction.y
                    gx, gy = gc.x - ball.position.x, gc.y - ball.position.y
                    if (vx * gx + vy * gy > 0.0
                            and tac.ball_advance_frac(
                                ball.position,
                                inspector.get_my_team_side()) > 0.5):
                        prev = getattr(self, "_shot_turn", None)
                        self._shot_turn = turn
                        # contador p/ o gate adaptativo (1 por EVENTO): só conta
                        # se a TRAJETÓRIA cruza a BOCA do gol (senão passes
                        # longos inflam o contador — bug do 0-1 vs level-3:
                        # 337 passes → "12 chutes" no 1º minuto → slack travado
                        # → 3 chutes no jogo inteiro).
                        if prev is None or turn - prev > 5:
                            vx2, vy2 = ball.velocity.direction.x, ball.velocity.direction.y
                            on_goal = False
                            if abs(vx2) > 1e-9:
                                tpar = (gc.x - ball.position.x) / (vx2 / (math.hypot(vx2, vy2) or 1.0))
                                if tpar > 0:
                                    y_at = ball.position.y + (vy2 / (math.hypot(vx2, vy2) or 1.0)) * tpar
                                    d_line = abs(gc.x - ball.position.x)
                                    on_goal = (GOAL_MIN_Y - 300 <= y_at <= GOAL_MAX_Y + 300
                                               and d_line <= 7000.0)
                            if on_goal:
                                self._our_shots = getattr(self, "_our_shots", 0) + 1
        except Exception:
            pass                      # estado é conveniência; nunca derruba o bot

    def _shadow_target(self, inspector, me, side):
        """Sombra do camper (gene camper_shadow, pedido do usuário): UM único
        zagueiro (o mais próximo, determinístico) cola goal-side no camper
        adversário MAIS FUNDO — não-portador — quando a bola está no NOSSO
        campo. Versão mínima da cobertura durante o cerco (a de 2 zagueiros em
        todos os estados foi rejeitada por passividade). None = fluxo normal."""
        if P.get("camper_shadow") != "on" or me.number not in tac.DEFENDERS:
            return None
        ball = inspector.get_ball()
        if tac.ball_advance_frac(ball.position, side) >= 0.5:
            return None                      # bola no campo deles: sem sombra
        ourg = self.mapper.get_defense_goal().get_center()
        h = inspector.get_ball_holder()
        hnum = (h.number if (h is not None and h.number != 0
                             and h.team_side != side) else -1)
        opps = [o for o in inspector.get_opponent_players()
                if o.number not in (tac.GOALKEEPER, hnum)
                and dist(o.position, ourg) <= P["cover_range"]]
        if not opps:
            return None
        alvo = min(opps, key=lambda o: (dist(o.position, ourg), o.number))
        defs = [p for p in inspector.get_my_team_players()
                if p.number in tac.DEFENDERS]
        eleito = min(defs, key=lambda p: (dist(p.position, alvo.position),
                                          p.number))
        if eleito.number != self.number:
            return None
        dx, dy = ourg.x - alvo.position.x, ourg.y - alvo.position.y
        n = math.hypot(dx, dy) or 1.0
        cx = alvo.position.x + dx / n * P["cover_dist"]
        cy = alvo.position.y + dy / n * P["cover_dist"]
        gd = math.hypot(cx - ourg.x, cy - ourg.y)
        if gd < 1400.0:
            cx = ourg.x + (cx - ourg.x) / (gd or 1.0) * 1400.0
            cy = ourg.y + (cy - ourg.y) / (gd or 1.0) * 1400.0
        return point(cx, cy)

    def _ot_active(self, inspector) -> bool:
        """v7/METAMORFO (ot_press): prorrogação (turn>6000; localmente NUNCA
        dispara — partidas terminam em 6000). O BotAdversario1 do 1×1 circulou passivo
        a OT inteira; na OT o jogo é de UMA chance — pressão máxima + chutar
        primeiro (par do ot_gate_relief). off = False na 1ª linha."""
        if P.get("ot_press") != "on":
            return False
        try:
            return inspector.get_snapshot().turn > 6000
        except Exception:
            return False

    def _n_chasers(self, inspector):
        """P4 (counterpress): nº de chasers, com o reforço temporário da janela
        de contrapressão. off (ou fora da janela) = N_CHASERS (=v3).
        v7 (ot_press): na prorrogação o reforço fica SEMPRE ativo (max, sem
        dupla contagem com a janela do counterpress)."""
        n = N_CHASERS
        boost = 0
        if P.get("counterpress") == "on":
            try:
                if inspector.get_snapshot().turn <= getattr(self, "_cp_until", -1):
                    boost = int(round(P["cp_extra"]))
            except Exception:
                pass
        if self._ot_active(inspector):
            boost = max(boost, int(round(P["cp_extra"])))
        return n + boost

    def _staggered_chasers(self, inspector, n):
        """Eleição de chasers com escalonamento anti-CB (cb_stagger, v6).

        off: delega exatamente à eleição atual (inércia por code-path).
        on: com a bola no nosso terço, se TODOS os eleitos são DEFENDERS
        (anatomia do gol de ouro do BotAdversario1: ambos os zagueiros pressionam o
        portador e o corredor central fica vazio para o camper), troca o
        ÚLTIMO eleito pelo melhor não-zagueiro do ranking de chegada — mesmo
        nº de pressionadores (agressividade preservada), zaga nunca esvazia.
        Determinístico: todos os processos calculam igual do mesmo snapshot."""
        elected = (tac.adaptive_chasers(inspector, n, P["chase_margin"])
                   if P.get("chase_mode") == "adaptive"
                   else tac.chasers(inspector, n))
        if P.get("cb_stagger") != "on" or len(elected) < 2:
            return elected
        if any(num not in tac.DEFENDERS for num in elected):
            return elected
        ball = inspector.get_ball()
        side = inspector.get_my_team_side()
        adv = (ball.position.x if side == lugo4py.TeamSide.HOME
               else MAX_X - ball.position.x) / MAX_X
        if adv >= 1.0 / 3.0:
            return elected
        outfield = [p for p in inspector.get_my_team_players()
                    if p.number != tac.GOALKEEPER
                    and p.number not in tac.DEFENDERS]
        if not outfield:
            return elected
        ranked = tac.rank_by_ball_arrival(outfield, ball)
        return elected[:-1] + [ranked[0].number]

    def _second_ball_target(self, inspector, me, side, chasers):
        """P3 (second_ball): ponto de ocupação da ZONA DE LIMPEZA do goleiro
        deles após o nosso chute sem gol (a reposse acontece a ~2300-3000 do
        gol em ~25 turnos; hoje ELES ganham 61-83% dela). Só ATACANTES
        não-chasers (lição da passividade). None = fluxo normal.
        v7 (swarm_rebound): com o gene ligado, a zona única vira o ARCO de
        slots do _swarm_slot (mesma janela pós-chute; cerco do BotAdversario2)."""
        swarm = P.get("swarm_rebound") == "on"
        if not swarm and P.get("second_ball") != "on":
            return None
        st = getattr(self, "_shot_turn", None)
        if st is None:
            return None
        turn = inspector.get_snapshot().turn
        if turn < st or turn - st > P["sb_window"]:
            return None
        if self.number not in tac.FORWARDS:
            return None
        if swarm:
            return self._swarm_slot(inspector, me, chasers, exclude=())
        gc = self.mapper.get_attack_goal().get_center()
        zx = gc.x - P["sb_dist"] if gc.x > MAX_X / 2 else gc.x + P["sb_dist"]
        zone = point(zx, MAX_Y / 2.0)
        cand = [p for p in inspector.get_my_team_players()
                if p.number in tac.FORWARDS and p.number not in chasers]
        cand.sort(key=lambda p: (dist(p.position, zone), p.number))
        k = int(round(P["sb_count"]))
        # P5 (gs_sb_boost): perdendo tarde, +1 crasher de segunda bola.
        if (P.get("gs_sb_boost") == "on"
                and self._game_aggr(inspector) > 0.5):
            k += 1
        chosen = [p.number for p in cand[:max(0, k)]]
        if self.number not in chosen:
            return None
        slot = chosen.index(self.number)
        off = (slot - (len(chosen) - 1) / 2.0) * P["sb_y_spread"]
        return point(zx, max(600.0, min(MAX_Y - 600.0, MAX_Y / 2.0 + off)))

    def _counterpress_target(self, inspector, me, side, chasers):
        """v7/METAMORFO (counter_press_window): na janela pós-perda ALTA,
        1-2 MIDS/FWDS não-chasers marcam a LINHA do 1º passe do novo portador
        (receptores prováveis = colegas dele de linha mais perto do NOSSO gol,
        os 2 mais próximos dele). DEFENDERS/GK nunca (lei da passividade: o
        custo é só de corpos que JÁ estavam altos — nenhum chaser a menos).
        None = fluxo normal."""
        if P.get("counter_press_window") != "on":
            return None
        try:
            if inspector.get_snapshot().turn > getattr(self, "_cpw_until", -1):
                return None
        except Exception:
            return None
        if me.number in tac.DEFENDERS or me.number == tac.GOALKEEPER:
            return None
        h = inspector.get_ball_holder()
        if h is None or h.number == 0 or h.team_side == side:
            return None
        ourg = self.mapper.get_defense_goal().get_center()
        d_h = dist(h.position, ourg)
        recvs = [o for o in inspector.get_opponent_players()
                 if o.number != h.number and o.number != tac.GOALKEEPER
                 and dist(o.position, ourg) < d_h]
        recvs.sort(key=lambda o: (dist(o.position, h.position), o.number))
        recvs = recvs[:2]
        if not recvs:
            return None
        ours = [p for p in inspector.get_my_team_players()
                if (p.number in tac.MIDFIELDERS or p.number in tac.FORWARDS)
                and p.number not in chasers]
        ours.sort(key=lambda p: (dist(p.position, h.position), p.number))
        markers = ours[:len(recvs)]
        nums = [p.number for p in markers]
        if me.number not in nums:
            return None
        r = recvs[nums.index(me.number)]
        f = P["cpw_lane_frac"]
        return point(h.position.x + (r.position.x - h.position.x) * f,
                     h.position.y + (r.position.y - h.position.y) * f)

    def _swarm_slot(self, inspector, me, chasers, exclude=()):
        """v7/METAMORFO (swarm_rebound): slot no ARCO de rebote do GK deles.
        sw_count ATACANTES não-chasers (fora de `exclude`) ocupam ângulos
        espalhados (0/±sw_angle da frontal) a sw_radius do centro do gol —
        onde as defesas do GK caem (BotAdversario2: 39 defesas → 51 finalizações).
        O raio nunca entra no disco 1400+sw_margin (o servidor empurra
        jogador de linha; medido min=1401). Eleição determinística por
        distância à âncora frontal, slot por ordem de y (sem cruzamento).
        None = não sou eleito / sem candidatos."""
        gc = self.mapper.get_attack_goal().get_center()
        cand = [p for p in inspector.get_my_team_players()
                if p.number in tac.FORWARDS and p.number not in chasers
                and p.number not in exclude]
        if not cand:
            return None
        r = max(P["sw_radius"], 1400.0 + P["sw_margin"])
        field_sign = -1.0 if gc.x > MAX_X / 2.0 else 1.0   # gol -> campo
        anchor = point(gc.x + field_sign * r, gc.y)
        cand.sort(key=lambda p: (dist(p.position, anchor), p.number))
        chosen = cand[:int(round(P["sw_count"]))]
        nums = [p.number for p in chosen]
        if me.number not in nums:
            return None
        by_y = sorted(chosen, key=lambda p: (p.position.y, p.number))
        slot = next(i for i, p in enumerate(by_y) if p.number == me.number)
        R = len(by_y)
        off_deg = 0.0 if R == 1 else (-1.0 + 2.0 * slot / (R - 1)) * P["sw_angle"]
        base_ang = 0.0 if field_sign > 0 else math.pi
        ang = base_ang + math.radians(off_deg)
        cx = gc.x + math.cos(ang) * r
        cy = max(400.0, min(MAX_Y - 400.0, gc.y + math.sin(ang) * r))
        gd = math.hypot(cx - gc.x, cy - gc.y)      # clamp radial pós-ajuste
        rmin = 1400.0 + P["sw_margin"]
        if gd < rmin:
            cx = gc.x + (cx - gc.x) / (gd or 1.0) * rmin
            cy = gc.y + (cy - gc.y) / (gd or 1.0) * rmin
        return point(cx, cy)

    # ---------------------------------------------------------------- posse
    def on_holding(self, inspector) -> List[lugo4py.Order]:
        try:
            self._update_transition(inspector)
            me = inspector.get_me()
            goal = self.mapper.get_attack_goal()
            opponents = inspector.get_opponent_players()
            goal_center = goal.get_center()
            d_goal = dist(me.position, goal_center)

            # 1) finalizar, se estivermos em alcance perigoso e com ângulo
            if d_goal <= P["dangerous_shot_range"]:
                # Caso 1 (finish_mode): se existe ponto do gol com GOL CERTO —
                # slack do goleiro > finish_sure_slack (conta pulo), alcancavel e
                # linha livre — chuta esse ponto (o de MAIOR folga). off = v9.
                if P.get("finish_mode") == "on":
                    sh = shooting.best_goal_shot(
                        inspector.get_ball().position, goal_center.x,
                        inspector.get_opponent_goalkeeper(), list(opponents),
                        P["gk_reach_speed"])
                    if sh is not None and sh[1] > P["finish_sure_slack"]:
                        return [geo.kick_to(inspector, me, inspector.get_ball(),
                                            sh[0], BALL_MAX_SPEED)]
                target = self._best_shot_target(inspector, goal)
                if target is not None:
                    return [geo.kick_to(inspector, me, inspector.get_ball(),
                                        target, BALL_MAX_SPEED)]

            # Caso 2 (finish_mode): CRUZAR p/ o Jogador 1 se ele esta aberto (linha
            # livre) E venceria o goleiro da posicao dele (goleiro deslocado). off = v9.
            if P.get("finish_mode") == "on" and d_goal <= P["dangerous_shot_range"] + 1500:
                mates_f = [p for p in inspector.get_my_team_players()
                           if p.number != self.number]
                jog1, _ = finish_play.roles(me, mates_f)
                cross = finish_play.holder_cross(
                    me, jog1, inspector.get_opponent_goalkeeper(),
                    opponents, goal_center.x)
                if cross is not None:
                    tgt, spd = cross
                    return [geo.kick_to(inspector, me, inspector.get_ball(), tgt, spd)]

            # P2 (kickoff_play): saída ENSAIADA do reinício — tabela p/ o #9
            # em corrida → toque pro espaço → cascata normal. off = v3.
            ko = setplays.hold_orders(self, inspector, me, opponents)
            if ko is not None:
                return ko

            # Conducao por HIERARQUIA DE CASOS (spec do usuario) — substitui a
            # cascata v9 abaixo. off (default) => cascata v9 intacta.
            if P.get("hold_logic") == "caso":
                order = self._caso_hold(inspector, me, goal_center, opponents, d_goal)
                if order is not None:
                    return order

            # 2) passar, se houver companheiro melhor posicionado
            pass_order = self._best_pass(inspector)
            if pass_order is not None:
                return [pass_order]

            # v7/METAMORFO (quina_entry): sem chute nem passe, atacar a quina/
            # linha de fundo (desloca o GK ao poste; o chute é reavaliado no
            # topo da cascata a cada turno). off = v6.
            if P.get("quina_entry") == "on":
                qt = self._quina_target(inspector, goal_center)
                if qt is not None and dist(me.position, qt) > 400.0:
                    return [safe_move(inspector, me, qt)]

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

    def _caso_hold(self, inspector, me, goal_center, opponents, d_goal):
        """Conducao por HIERARQUIA DE CASOS (spec do usuario). Marcacao = AREA de
        conducao segura (carry.dribble_freedom). Prioridade:
          [Caso 1/pass] passe p/ FRENTE a receptor DESMARCADO mais perto do gol
                        (se caso_pass_priority='pass_first');
          [Caso 1/2.a]  rota segura rumo ao gol -> conduzir p/ o melhor ponto;
          [dribble_first] passe p/ frente (se essa a prioridade);
          [Caso 2.b]    sem rota frontal: se PRESO escapa por passe seguro; senao
                        reposiciona p/ a maior area livre (de onde a proxima abre).
        Devolve List[Order] ou None (cai na cascata v9). MPC: 1 passo/turno."""
        gk = inspector.get_opponent_goalkeeper()
        fr = carry.dribble_freedom(me.position, opponents, gk, goal_center)
        pass_first = P.get("caso_pass_priority") != "dribble_first"

        if pass_first:
            fp = self._best_pass(inspector, require_unmarked_fwd=True)
            if fp is not None:
                return [fp]

        # Caso 1 / 2.a: rota segura rumo ao gol -> conduzir
        if fr["best_fwd"] is not None and fr["fwd"] > 0.2:
            return [safe_move(inspector, me, fr["best_fwd"])]

        if not pass_first:
            fp = self._best_pass(inspector, require_unmarked_fwd=True)
            if fp is not None:
                return [fp]

        # Caso 2.b: sem rota frontal
        if fr["cls"] == "preso":
            esc = self._best_pass(inspector)          # escape: qualquer passe seguro
            if esc is not None:
                return [esc]
        if fr["best_free"] is not None:               # reposicionar p/ area livre
            return [safe_move(inspector, me, fr["best_free"])]
        esc = self._best_pass(inspector)
        if esc is not None:
            return [esc]
        return None                                   # cai na cascata v9

    def _cover_target(self, inspector, me, side):
        """Cobertura anti-banheira (forense do gol vs BotAdversario1): se ha atacantes
        adversarios PARADOS no nosso campo durante o nosso ataque, os zagueiros
        mais proximos ficam GOAL-SIDE deles (marcando) em vez de subir — evita o
        contra-ataque (sem impedimento no Lugo, banheira e' legal). Determinismo
        por papel. Devolve o ponto de cobertura p/ `me`, ou None. off = v9."""
        if P.get("cover_mode") != "on" or me.number not in tac.DEFENDERS:
            return None
        ourg = self.mapper.get_defense_goal().get_center()
        opps = [o for o in inspector.get_opponent_players()
                if o.number != tac.GOALKEEPER
                and dist(o.position, ourg) <= P["cover_range"]]
        if not opps:
            return None
        targets = sorted(opps, key=lambda o: dist(o.position, ourg))
        targets = targets[:int(round(P["cover_count"]))]
        defs = [p for p in inspector.get_my_team_players()
                if p.number in tac.DEFENDERS]
        # pareamento deterministico: cada alvo (mais perigoso 1o) leva o zagueiro
        # LIVRE mais proximo.
        used, assigned = set(), {}
        for t in targets:
            cand = sorted((d for d in defs if d.number not in used),
                          key=lambda d: dist(d.position, t.position))
            if cand:
                assigned[t.number] = cand[0].number
                used.add(cand[0].number)
        for t in targets:
            if assigned.get(t.number) != me.number:
                continue
            dx, dy = ourg.x - t.position.x, ourg.y - t.position.y
            n = math.hypot(dx, dy) or 1.0
            cx, cy = t.position.x + dx / n * P["cover_dist"], t.position.y + dy / n * P["cover_dist"]
            # B2 (cover_lane_mix): desloca o ponto na direcao da LINHA
            # bola->camper (negacao do passe de contra-ataque), mantendo o
            # goal-side como base. 0.0 = goal-side puro (=v2).
            lm = P["cover_lane_mix"]
            if lm > 0.0:
                b = inspector.get_ball().position
                lx, ly = (b.x + t.position.x) / 2.0, (b.y + t.position.y) / 2.0
                cx, cy = cx + (lx - cx) * lm, cy + (ly - cy) * lm
            gd = math.hypot(cx - ourg.x, cy - ourg.y)      # nao entrar na zona 1400
            if gd < 1400.0:
                cx = ourg.x + (cx - ourg.x) / (gd or 1.0) * 1400.0
                cy = ourg.y + (cy - ourg.y) / (gd or 1.0) * 1400.0
            return geo.point(cx, cy)
        return None

    # ------------------------------------------------------------ apoiando
    def on_supporting(self, inspector) -> List[lugo4py.Order]:
        try:
            self._update_transition(inspector)
            me = inspector.get_me()
            ball = inspector.get_ball()
            holder = inspector.get_ball_holder()
            side = inspector.get_my_team_side()

            # P2 (kickoff_play): rotas do RECV/onda-2 na janela do reinício.
            ko = setplays.route_orders(self, inspector, me,
                                       lambda t: safe_move(inspector, me, t))
            if ko is not None:
                return ko

            # Cobertura anti-banheira (cover_mode): zagueiro designado marca o
            # atacante adversario parado no nosso campo em vez de subir. off = v9.
            cov = self._cover_target(inspector, me, side)
            if cov is not None:
                return self._sup_orders(inspector, safe_move(inspector, me, cov))

            # A4 (def_outlet): companheiro segura a bola no NOSSO terco =>
            # os mais proximos viram valvulas de escape (linha lateral/diagonal
            # recebivel) em vez de manter formacao — cria o passe que o
            # zone_escape aceita. off = v2.
            if (P.get("def_outlet") == "on" and holder is not None
                    and holder.number != 0
                    and holder.number != tac.GOALKEEPER
                    and tac.ball_advance_frac(holder.position, side) < 1.0 / 3.0):
                t_out = self._def_outlet_target(inspector, me, holder, side)
                if t_out is not None:
                    return self._sup_orders(
                        inspector, safe_move(inspector, me, t_out))

            # Caso 2 (finish_mode): corridas COORDENADAS p/ manobrar o goleiro.
            # Jogador 1 (atacante do lado contrario) corre ao ponto livre c/ angulo;
            # Jogador 2 (meia) vira no-rele. Determinismo por papel. off = v9.
            if P.get("finish_mode") == "on" and holder is not None:
                gc = self.mapper.get_attack_goal().get_center()
                if dist(holder.position, gc) <= P["dangerous_shot_range"] + 1500:
                    opps = inspector.get_opponent_players()
                    gk = inspector.get_opponent_goalkeeper()
                    mates = [p for p in inspector.get_my_team_players()
                             if p.number != holder.number]
                    jog1, jog2 = finish_play.roles(holder, mates)
                    if jog1 is not None:
                        j1t = finish_play.run_point(jog1, ball.position, gk, opps,
                                                    gc.x, holder.position, 6.0)
                        if me.number == jog1.number and j1t is not None:
                            return self._sup_orders(
                                inspector, safe_move(inspector, me, j1t))
                        if (jog2 is not None and me.number == jog2.number
                                and j1t is not None):
                            rp = finish_play.relay_point(me, holder.position, j1t,
                                                         opps, gk)
                            return self._sup_orders(
                                inspector, safe_move(inspector, me, rp))

            # v7/METAMORFO (swarm_rebound, fase PRÉ-chute): portador em alcance
            # de finalização → atacantes ocupam o arco de rebote ANTES do chute
            # (o cerco chega junto; a defesa do GK cai onde temos corpos).
            # Eleição DISJUNTA: nunca rouba Jog1/Jog2 do finish_mode nem o
            # far-post runner. off = v6.
            if (P.get("swarm_rebound") == "on" and holder is not None
                    and holder.number != 0):
                gc_sw = self.mapper.get_attack_goal().get_center()
                if dist(holder.position, gc_sw) <= P["dangerous_shot_range"]:
                    excl = {holder.number}
                    if P.get("finish_mode") == "on":
                        mates_sw = [p for p in inspector.get_my_team_players()
                                    if p.number != holder.number]
                        j1, j2 = finish_play.roles(holder, mates_sw)
                        excl |= {j.number for j in (j1, j2) if j is not None}
                    if P.get("far_post_run") == "on":
                        fp_num = self._far_post_runner(inspector, holder, side)
                        if fp_num is not None:
                            excl.add(fp_num)
                    st_sw = self._swarm_slot(inspector, me, (), exclude=excl)
                    if st_sw is not None:
                        return self._sup_orders(
                            inspector, safe_move(inspector, me, st_sw))

            # posição de formação, deslocada para frente (estamos atacando)
            # P3 (attack_width): com posse no campo deles, os atacantes usam a
            # largura do gene em vez da compressão fixa. off = byte-idêntico.
            # v7 (ot_press): na prorrogação a linha de apoio sobe ot_aggr_boost.
            aggr_sup = P["aggression_support"]
            if self._ot_active(inspector):
                aggr_sup = min(1.5, aggr_sup + P["ot_aggr_boost"])
            base = tac.formation_position(
                self.number, ball.position, side,
                aggression=aggr_sup,
                attacking=(tac.ball_advance_frac(ball.position, side)
                           >= P["attack_width_minfrac"]))

            # corrida ao 2º poste (far_post_run) tem prioridade quando ligada e a
            # jogada está madura. Default off.
            if P.get("far_post_run") == "on" and holder is not None:
                fp = self._far_post_target(inspector, holder, side)
                if fp is not None:
                    return self._sup_orders(inspector,
                                            safe_move(inspector, me, fp))

            if holder is None:
                return self._sup_orders(inspector,
                                        safe_move(inspector, me, base))

            # apoio ATIVO (support_mode="offer"): recebedores sobem oferecendo
            # linha de passe segura; default "v9" = oferta em anel (idêntico).
            if P.get("support_mode") == "offer":
                tgt = self._support_offer_run(inspector, holder, side, base)
                return self._sup_orders(inspector,
                                        safe_move(inspector, me, tgt))

            # v9 (default): se perto do portador, abrir linha de passe em vez de colar
            if dist(me.position, holder.position) < P["support_near_holder"]:
                base = self._support_offer(inspector, holder, base)

            return self._sup_orders(inspector, safe_move(inspector, me, base))

        except Exception as e:
            print(f'on_supporting: {e}')
            traceback.print_exc()
            return []

    def _sup_orders(self, inspector, move_order):
        """Ordens do apoiador. L11 (support_catch="on"): também emite catch —
        na disputa do turno seguinte à perda do portador, os apoiadores da v2
        não tentavam agarrar (DEFENDING/DISPUTING emitem, SUPPORTING não).
        off = v2 (só o move)."""
        if P.get("support_catch") == "on":
            return [move_order, inspector.make_order_catch()]
        return [move_order]

    # ----------------------------------------------------------- defendendo
    def on_defending(self, inspector) -> List[lugo4py.Order]:
        try:
            self._update_transition(inspector)
            me = inspector.get_me()
            ball = inspector.get_ball()
            side = inspector.get_my_team_side()
            n_ch = self._n_chasers(inspector)   # P4: reforço da contrapressão
            chasers = self._staggered_chasers(inspector, n_ch)

            if self.number in chasers:
                # pressiona o portador pelo lado do nosso gol (corta o avanço)
                r = geo.intercept_turn(me.position, ball)
                target = r[1] if r else ball.position
                return [safe_move(inspector, me, target),
                        inspector.make_order_catch()]

            # v7/METAMORFO (kickoff_race): corrida do reinício PERDIDA (eles
            # seguram a saída) → arco de interceptação do 1º passe ao redor
            # do círculo central. off = v6.
            ring = setplays.ring_orders(self, inspector, me, chasers,
                                        lambda t: safe_move(inspector, me, t))
            if ring is not None:
                return ring

            # P3 (second_ball): o GK deles segura a nossa bola chutada por
            # ~14-16 turnos DENTRO do anel (estamos DEFENDING) — é exatamente
            # quando a formação puxava os atacantes de volta e perdíamos a
            # corrida da segunda bola (déficit ~789d). off = v3.
            sb = self._second_ball_target(inspector, me, side, chasers)
            if sb is not None:
                return [safe_move(inspector, me, sb),
                        inspector.make_order_catch()]

            # v7/METAMORFO (counter_press_window): janela pós-perda alta —
            # marcar as linhas do 1º passe do novo portador. off = v6.
            cpt = self._counterpress_target(inspector, me, side, chasers)
            if cpt is not None:
                return [safe_move(inspector, me, cpt),
                        inspector.make_order_catch()]

            # Sombra do camper (camper_shadow): 1 zagueiro cola no camper mais
            # fundo durante o cerco (bola no nosso campo). off = v3.
            sh = self._shadow_target(inspector, me, side)
            if sh is not None:
                return [safe_move(inspector, me, sh),
                        inspector.make_order_catch()]

            # B1 (cover_states="all"): a cobertura anti-banheira também vale
            # DEFENDENDO — na v2 só em SUPPORTING, então o camper fica solto
            # justamente quando o contra-ataque nasce. off ("sup") = v2.
            if P.get("cover_states") == "all":
                cov = self._cover_target(inspector, me, side)
                if cov is not None:
                    return [safe_move(inspector, me, cov),
                            inspector.make_order_catch()]

            # F3 (marking_mode="man"): não-chasers marcam homem-a-homem
            # goal-side (tactics.marking_target). default "cover" = v2 (zonal).
            if P.get("marking_mode") == "man":
                mt = tac.marking_target(inspector, self.number)
                if mt is not None:
                    g = self.mapper.get_defense_goal().get_center()
                    mdx, mdy = g.x - mt.position.x, g.y - mt.position.y
                    n = math.hypot(mdx, mdy) or 1.0
                    cx = mt.position.x + mdx / n * P["cover_dist"]
                    cy = mt.position.y + mdy / n * P["cover_dist"]
                    gd = math.hypot(cx - g.x, cy - g.y)
                    if gd < 1400.0:
                        cx = g.x + (cx - g.x) / (gd or 1.0) * 1400.0
                        cy = g.y + (cy - g.y) / (gd or 1.0) * 1400.0
                    return [safe_move(inspector, me, point(cx, cy)),
                            inspector.make_order_catch()]

            # os demais recuam em formação, entre a bola e o nosso gol
            base = tac.formation_position(self.number, ball.position, side,
                                          aggression=P["aggression_defend"])
            cover = self._cover_position(inspector, base)
            # P4 (def_min_depth): âncora do zagueiro nunca abaixo do piso —
            # p10 medido = 1400 (abraçado ao anel intocável). 0.0 = inerte.
            if P["def_min_depth"] > 0.0 and self.number in tac.DEFENDERS:
                g = self.mapper.get_defense_goal().get_center()
                gd = dist(cover, g)
                if gd < P["def_min_depth"]:
                    cover = point(
                        g.x + (cover.x - g.x) / (gd or 1.0) * P["def_min_depth"],
                        g.y + (cover.y - g.y) / (gd or 1.0) * P["def_min_depth"])
            # v7 (kickoff_shield): compactar o corredor central pós-reset.
            cover = self._shield_clamp(inspector, cover)
            return [safe_move(inspector, me, cover),
                    inspector.make_order_catch()]

        except Exception as e:
            print(f'on_defending: {e}')
            traceback.print_exc()
            return []

    # ---------------------------------------------------------- disputando
    def on_disputing(self, inspector) -> List[lugo4py.Order]:
        try:
            self._update_transition(inspector)
            me = inspector.get_me()
            ball = inspector.get_ball()
            side = inspector.get_my_team_side()
            n_ch = self._n_chasers(inspector)   # P4: reforço da contrapressão
            chasers = self._staggered_chasers(inspector, n_ch)

            if self.number in chasers:
                r = geo.intercept_turn(me.position, ball)
                target = r[1] if r else ball.position
                return [safe_move(inspector, me, target),
                        inspector.make_order_catch()]

            # v7/METAMORFO (kickoff_race): disputa do reinício perdendo a
            # corrida → arco de interceptação (antes das rotas do playbook,
            # que pressupõem corrida NOSSA). off = v6.
            ring = setplays.ring_orders(self, inspector, me, chasers,
                                        lambda t: safe_move(inspector, me, t))
            if ring is not None:
                return ring

            # P2 (kickoff_play): não-chasers do playbook pré-correm as rotas
            # durante a corrida do reinício (o TAKER é chaser e persegue normal).
            ko = setplays.route_orders(self, inspector, me,
                                       lambda t: safe_move(inspector, me, t))
            if ko is not None:
                return ko

            # P3 (second_ball): ocupar a zona de limpeza do GK deles enquanto a
            # bola do nosso chute está viva/na mão dele. off = v3.
            sb = self._second_ball_target(inspector, me, side, chasers)
            if sb is not None:
                return [safe_move(inspector, me, sb),
                        inspector.make_order_catch()]

            # C1-b (zone_ambush — ARQUIVADO, default off): emboscar a ejeção da
            # zona (auto-chute dos 40 turnos rumo ao centro) com o 1º chaser.
            # Screening: PIOROU muito (sofridos 0,75→1,33; o emboscador captura
            # fundo demais e é engolido pelo press; um chaser a menos disputa).
            # Fica como gene para eventual reavaliação vs adversário sem press.
            if P.get("zone_ambush") == "on" and self.number in chasers:
                ap = self._autokick_ambush(inspector, me, ball, chasers)
                if ap is not None:
                    return [safe_move(inspector, me, ap),
                            inspector.make_order_catch()]

            # D1 (rebound_crash): após NOSSO chute (bola livre, rápida, rumo ao
            # gol deles, no terço de ataque), crashers convergem ao ponto de
            # queda para a segunda bola em vez de recuar à formação. off = v2.
            if P.get("rebound_crash") == "on":
                rt = self._rebound_target(inspector, me, ball, side, chasers)
                if rt is not None:
                    return [safe_move(inspector, me, rt),
                            inspector.make_order_catch()]

            # Sombra do camper (camper_shadow) também na bola livre. off = v3.
            sh = self._shadow_target(inspector, me, side)
            if sh is not None:
                return [safe_move(inspector, me, sh),
                        inspector.make_order_catch()]

            # B1 (cover_states="all"): camper marcado também na bola livre —
            # o gol 1 vs BotAdversario1 nasceu de bola solta com o camper sozinho.
            if P.get("cover_states") == "all":
                cov = self._cover_target(inspector, me, side)
                if cov is not None:
                    return [safe_move(inspector, me, cov),
                            inspector.make_order_catch()]

            base = tac.formation_position(self.number, ball.position, side,
                                          aggression=0.0)
            # F1 (disputing_mode="defend"): bola livre no NOSSO campo = momento
            # do rebote adversário; recuar como em DEFENDING (na v2 a linha
            # SOBE no instante do chute deles: aggression 0.0 sem recuo).
            if (P.get("disputing_mode") == "defend"
                    and tac.ball_advance_frac(ball.position, side) < 0.5):
                base = tac.formation_position(self.number, ball.position, side,
                                              aggression=P["aggression_defend"])
                base = self._cover_position(inspector, base)
            # v7 (kickoff_shield): compactar o corredor central pós-reset.
            base = self._shield_clamp(inspector, base)
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

            # C0 (gk_probe — sonda de laboratório, NUNCA submeter): falsifica
            # "goleiro preso à linha" pedindo x=1200 nos turnos 100-300.
            if P.get("gk_probe") == "on":
                t_now = inspector.get_snapshot().turn
                if 100 <= t_now <= 300:
                    px = 1200.0 if goal_center.x < MAX_X / 2 else MAX_X - 1200.0
                    return [safe_move(inspector, me, point(px, goal_center.y)),
                            inspector.make_order_catch()]

            # C1 (gk_collect): bola SOLTA e lenta na NOSSA zona-1400 — onde SÓ
            # o goleiro entra — deve ser coletada, não observada da linha (gol
            # 1 vs BotAdversario1: rebote parado é invisível ao _goal_line_threat, que
            # exige speed>5). Também dispara pelo alarme do relógio da zona
            # (40 turnos ⇒ auto-chute ao CENTRO ≈390 = rebote servido). off=v2.
            if P.get("gk_collect") == "on":
                col = self._gk_collect_target(inspector, goal_center)
                if col is not None:
                    return [safe_move(inspector, me, col),
                            inspector.make_order_catch()]

            # onde a bola cruza a linha do gol
            threat = self._goal_line_threat(inspector, goal_center)
            if threat is not None:
                cross_point, turns = threat
                d = dist(me.position, cross_point)
                # não dá para chegar andando: pular (trava 3 turnos, usar por último)
                if turns_for_player(d) > turns and turns <= P["gk_jump_max_turns"]:
                    # C2 (gk_jump_mode="strict"): só pula se o PULO alcança de
                    # fato — 200/turno×3 (lockout não interrompível) + 100
                    # depois. Pulo perdido = 3 turnos travado fora de posição
                    # (o rebote do gol 1 pega o goleiro plantado). off = v2.
                    if P.get("gk_jump_mode") == "strict":
                        jump_reach = (200.0 * min(turns, 3.0)
                                      + 100.0 * max(0.0, turns - 3.0))
                        if d - geo.GOALKEEPER_HALF_EXTENT > jump_reach:
                            return [safe_move(inspector, me, cross_point),
                                    inspector.make_order_catch()]
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
        # P2: marca o reinício (dispara no início E após cada gol). O playbook
        # (setplays) só age com kickoff_play="on"; gravar o turno é inerte.
        try:
            self._reset_turn = snapshot.turn
            self._ko_abort = False      # v7 c0: novo reset re-arma os setplays
        except Exception:
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
        # P5 (gs_shot_scale): PERDENDO tarde (game_aggr>0, exige
        # game_state_mode=on), o gate de chute afrouxa em ate gs_shot_scale —
        # atras no placar, chute "quase bom" + segunda bola > nao chutar.
        gap_relief = 0.0
        if P["gs_shot_scale"] > 0.0:
            ga_ = self._game_aggr(inspector)
            if ga_ > 0.0:
                gap_relief = ga_ * P["gs_shot_scale"]
        # PRORROGAÇÃO (gol de ouro, goleiro ~40% do tamanho — medido): depois
        # do turno 6000 o gate afrouxa em ot_gate_relief. 0.0 = inerte (=v4/v5);
        # localmente nunca dispara (partidas terminam em 6000).
        if P["ot_gate_relief"] > 0.0:
            try:
                if inspector.get_snapshot().turn > 6000:
                    gap_relief += P["ot_gate_relief"]
            except Exception:
                pass

        # GATE ADAPTATIVO (shot_gate_adaptive): goleiro-elite detectado EM-JOGO
        # (muitos chutes nossos, quase nenhum gol) => aperta threshold->slack.
        # Motivo: no dia das chaves UMA versao joga L1+L2+L3, e o gate certo
        # difere (L1 fraco=volume; L3-elite=97,7% defesas, 2,3% de conversao da
        # v4 em 44 chutes). off = gate estatico (=v4).
        gate_mode = P.get("shot_gate")
        if P.get("shot_gate_adaptive") == "on" and gate_mode == "threshold":
            try:
                if (getattr(self, "_our_shots", 0) >= P["ag_min_shots"]
                        and inspector.get_my_team().score <= P["ag_max_goals"]):
                    gate_mode = "slack"
            except Exception:
                pass
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

            # GATE HÍBRIDO (v6): o critério é decidido POR ALVO pela distância.
            # Perto (d<=hybrid_close_range => t_bola<=~9, GK cobre +-1235):
            # threshold — mantém o volume onde os gols reais nascem (rebote,
            # segunda bola, caos). Longe (t_bola 16-20, GK cobre +-2360):
            # slack temporal — mata as ~40 doações de longe do jogo de 44
            # chutes vs level-3. Estático, sem estado: imune ao bug da v5.
            gm = gate_mode
            if gm == "hybrid":
                gm = "threshold" if d <= P["hybrid_close_range"] else "slack"

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
            if gm == "slack" and gk is not None:
                # gate TEMPORAL calibrado: folga do alvo ao goleiro MENOS o quanto
                # ele cobre em t turnos (560 + gk_reach_speed·t). gk_reach_speed=75
                # calibrado (AUC 0.87 vs gol; slack>0 converte 43%, <=0 converte 0%).
                t_ball = turns_for_ball(BALL_MAX_SPEED, d)
                if t_ball == math.inf:
                    continue
                slack = abs(target.y - gk.position.y) - (560.0 + P["gk_reach_speed"] * t_ball)
                if slack <= P["shot_min_slack"] - gap_relief:
                    continue
                score = slack
            elif gm == "xg" and fin.available():
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
                if gap < P["shot_min_gap"] - gap_relief:
                    continue
                score = gap - P["shot_gk_penalty"] * d
            else:
                score = 1e6 - d

            if score > best_score:
                best_score, best = score, target
        return best

    def _best_pass(self, inspector, require_unmarked_fwd=False):
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

        # a3.4 (zone_escape): no TERCO DEFENSIVO o objetivo do passe vira SAIR
        # da pressao (gols 2/3 vs BotAdversario1): barra propria, retencao sempre
        # habilitada e fallback liberado. off = v2 (flag nunca liga).
        side = inspector.get_my_team_side()
        zone_escape_on = (P.get("zone_escape") == "on"
                          and tac.ball_advance_frac(me.position, side) < 1.0 / 3.0)

        # v7/METAMORFO (outlet_press_detect): CERCO no terço defensivo
        # (>= opd_min_opps adversários em opd_radius) => passe curto CENTRAL
        # proibido — é a bola que o pressing do BotAdversario1 come (modo-de-perder
        # nº3; BotAdversario2 fez 5×0 com 5 erros de passe no jogo). O escape sai
        # curto-de-corredor ou longo. GK receptor ISENTO (gk_outlet segue
        # legal: recuo à zona-1400 é seguro por construção). off = v9.
        # Mock-safe: só me/opponents/side (decide_dump não tem snapshot).
        opd_on = (P.get("outlet_press_detect") == "on"
                  and tac.ball_advance_frac(me.position, side) < 1.0 / 3.0
                  and self._opps_within(me.position, opponents,
                                        P["opd_radius"]) >= P["opd_min_opps"])

        # P5 (gs_retain_late/gs_draw_ok): NAO-perdendo no fim de jogo, proteger
        # o resultado — retencao habilitada (reciclo seguro em vez de risco).
        # No mata-mata o EMPATE e' do melhor seed: gs_draw_ok liga-se POR
        # VERSAO antes desses jogos. off = inerte (nem le placar/turno).
        late_protect = False
        if P.get("gs_retain_late") == "on":
            if game_aggr < -0.5:
                late_protect = True
            elif P.get("gs_draw_ok") == "on":
                try:
                    margin = (inspector.get_my_team().score
                              - inspector.get_opponent_team().score)
                    L = max(1.0, P["late_game_turns"])
                    if margin >= 0 and inspector.get_turn() >= 6000.0 - L:
                        late_protect = True
                except Exception:
                    pass

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
        if zone_escape_on:                       # a3.4: barra do terco defensivo
            best_score = min(best_score, P["pass_min_score_defthird"])
        retain = None
        retain_score = -1e18

        # a3.2: sob marcacao/no terco defensivo o passe CURTO vira legal (o
        # escape de 450d existe; a v2 exigia >=800 sempre). 0.0 = inerte (=v2).
        min_pass_d = P["pass_min_dist"]
        if P["pass_min_dist_danger"] > 0.0 and (
                zone_escape_on
                or (status_on and holder_state in ("atencao", "perigo"))):
            min_pass_d = min(min_pass_d, P["pass_min_dist_danger"])

        for mate in mates:
            if mate.number == tac.GOALKEEPER:
                # a3.3 (gk_outlet): goleiro como valvula de reciclo no NOSSO
                # terco com o portador marcado — o adversario nao entra na
                # zona-1400, entao o recuo e' seguro por construcao. off = v2.
                if not (P.get("gk_outlet") == "on"
                        and status_on and holder_state != "livre"
                        and tac.ball_advance_frac(me.position, side)
                        < P["gk_outlet_maxfrac"]):
                    continue
            d = dist(me.position, mate.position)
            if d < min_pass_d or d > geo.MAX_KICK_RANGE:
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
            if mate.number == tac.GOALKEEPER:
                # a3.3: nunca mirar NA linha do gol (bola perdida = gol contra);
                # alvo deslocado 350d para dentro do campo, na frente do GK.
                inward = 350.0 if side == lugo4py.TeamSide.HOME else -350.0
                target = point(target.x + inward, target.y)

            # v7 (outlet_press_detect): sob cerco, veta o curto central.
            if (opd_on and mate.number != tac.GOALKEEPER
                    and d < P["opd_short_dist"]
                    and abs(target.y - MAX_Y / 2.0) < P["opd_center_halfwidth"]):
                continue

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
            elif P.get("pass_veto_mode") == "turnwise":
                # A2: veto por fronteiras de turno, origem = BOLA (o chute sai
                # dela, ~200 a frente), SEM o carve-out de 700d — o presser
                # colado na linha de saida conta (gol 3 vs BotAdversario1). off = v2.
                if geo.intercept_slack_turnwise(
                        inspector.get_ball().position, target, opponents,
                        kick_speed) <= P["veto_margin_turns"]:
                    continue
            elif can_be_intercepted(me.position, target, opponents, kick_speed, USE_VELOCITY):
                continue

            mate_gain = dist(target, goal_center)
            advance = my_gain - mate_gain
            clearance = lane_clearance(me.position, target, opponents)
            mate_pressure = self._pressure_on(mate.position, opponents)

            # gate de receptor MARCADO (spec do usuario): um receptor sem area de
            # conducao (marcado) NAO e' destino terminal — so como rele (planejador)
            # ou p/ abrir angulo. require_unmarked_fwd (usado pelo Caso): exige
            # receptor DESMARCADO e mais perto do gol. off = v9 (nenhum gate).
            if require_unmarked_fwd:
                if advance <= 0.0:
                    continue
                rf = carry.dribble_freedom(mate.position, opponents,
                                           inspector.get_opponent_goalkeeper(), goal_center)
                if rf["cls"] in ("preso", "restrito"):
                    continue
            elif P.get("pass_recv_gate") == "on":
                rf = carry.dribble_freedom(mate.position, opponents,
                                           inspector.get_opponent_goalkeeper(), goal_center)
                if rf["cls"] == "preso":
                    continue

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

            # v7 (outlet_press_detect): preferência de corredor sob cerco
            # (0.0 = só o veto; soma 0 => decisão idêntica com gene off).
            flank_bonus = 0.0
            if opd_on and P["opd_w_flank"] > 0.0:
                flank_bonus = P["opd_w_flank"] * abs(target.y - MAX_Y / 2.0)

            score = (advance
                     + P["pass_w_clearance"] * clearance
                     - P["pass_w_mate_pressure"] * mate_pressure
                     + P["pass_w_pressure_bonus"] * pressure_bonus(pressure)
                     + switch
                     - P["pass_w_overmark"] * max(0.0, mate_pressure
                                                  - P["pass_mark_threshold"])
                     + safety
                     + recv_bonus
                     + flank_bonus)

            # candidato de RETENÇÃO: passe seguro que perde menos avanço, recuo
            # LIMITADO por pass_retain_backmax. Habilitado por pass_retain="on" OU
            # (Componente 1) portador em atencao/perigo (escape seguro).
            retain_enabled = (P.get("pass_retain") == "on"
                              or (status_on and holder_state in ("atencao", "perigo"))
                              or zone_escape_on or late_protect)
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

        if best is None and (under_pressure or zone_escape_on
                             or late_protect) and retain is not None:
            best = retain
        if best is None:
            return None
        target, speed = best
        return geo.kick_to(inspector, me, inspector.get_ball(), target, speed)

    def _quina_target(self, inspector, goal_center):
        """v7/METAMORFO (quina_entry): sem chute nem passe aprovados, conduzir
        à QUINA — qe_depth da linha de fundo deles, y fora da boca, lado
        oposto ao GK (BotAdversario10: 62% de conversão deslocando o GK ao poste;
        nosso g1 da v6 teve a mesma anatomia). Segurança por construção:
        BOUNDS de qe_depth têm piso 1500 => o alvo fica FORA da faixa x<=1400
        (o relógio de 40t da zona nem arma) e fora do disco 1400
        (hypot(1500, >=1300) >= 1984). qe_zone_alarm cobre o residual (bola
        já funda por outra via => recua ao fluxo). None = carry normal."""
        if P.get("quina_entry") != "on":
            return None
        me = inspector.get_me()
        side = inspector.get_my_team_side()
        if tac.ball_advance_frac(me.position, side) < P["qe_minfrac"]:
            return None
        try:
            if getattr(inspector.get_snapshot(),
                       "turns_ball_in_goal_zone", 0) >= P["qe_zone_alarm"]:
                return None
        except Exception:
            pass
        sign_x = -1.0 if goal_center.x > MAX_X / 2.0 else 1.0
        tx = goal_center.x + sign_x * P["qe_depth"]
        gk = inspector.get_opponent_goalkeeper()
        gk_y = gk.position.y if gk is not None else MAX_Y / 2.0
        opponents = list(inspector.get_opponent_players())
        best, best_score = None, -1e18
        for ty in (GOAL_MIN_Y - P["qe_y_off"], GOAL_MAX_Y + P["qe_y_off"]):
            ty = max(500.0, min(MAX_Y - 500.0, ty))
            cand = point(tx, ty)
            press = self._pressure_on(cand, opponents)
            score = (0.001 * abs(gk_y - ty) - 600.0 * press
                     - 0.15 * dist(me.position, cand))
            if score > best_score:
                best_score, best = score, cand
        return best

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
        # A1 (carry_gate): a repulsão abaixo só desvia de adversário a <334d —
        # com a rota ao gol BLOQUEADA o portador dribla direto para o desarme
        # (gol 2 vs BotAdversario1: #4 conduziu no presser #8). v2 do gene (a v1, que
        # usava best_free puro, RECUAVA para o canto sob pressing: escape do
        # terço 37%→20% no screening — rejeitada): com a área frontal abaixo da
        # barra, (a) prefere o MELHOR endpoint seguro rumo-ao-gol (best_fwd =
        # enfiar-se com segurança); (b) senão aceita a melhor direção livre SÓ
        # se ela não recua (componente ao gol >= -0.25); (c) senão carrega no
        # caminho v9 (a coragem da base vale mais que a fuga p/ a armadilha).
        # off = v2 (nem computa).
        if P.get("carry_gate") == "on":
            fr = carry.dribble_freedom(me.position, opponents,
                                       inspector.get_opponent_goalkeeper(),
                                       goal_center)
            if fr["fwd"] <= P["carry_gate_fwd_min"]:
                tgt = fr["best_fwd"]
                if tgt is None and fr["best_free"] is not None:
                    bf = fr["best_free"]
                    gdx = goal_center.x - me.position.x
                    gdy = goal_center.y - me.position.y
                    gn = math.hypot(gdx, gdy) or 1.0
                    sx, sy = bf.x - me.position.x, bf.y - me.position.y
                    sn = math.hypot(sx, sy) or 1.0
                    if (sx * gdx + sy * gdy) / (gn * sn) >= -0.25:
                        tgt = bf
                if tgt is not None:
                    return tgt
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

    def _def_outlet_target(self, inspector, me, holder, side):
        """A4 (def_outlet): ponto de recepção de ESCAPE quando um companheiro
        segura a bola no NOSSO terço. Elegíveis: os `def_outlet_count` de linha
        mais próximos do portador (desempate por número — determinístico, todos
        calculam igual). Cada elegível varre meio-anel próprio (1º = metade
        superior, 2º = inferior — sem colisão de destino) de raio
        `def_outlet_radius` ao redor do portador; exige não afundar atrás do
        portador, ponto dentro do campo e linha BOLA→ponto não interceptável.
        Score = folga da linha − pressão no destino + leve avanço."""
        mates = [p for p in inspector.get_my_team_players()
                 if p.number not in (tac.GOALKEEPER, holder.number)]
        mates.sort(key=lambda p: (dist(p.position, holder.position), p.number))
        k = int(round(P["def_outlet_count"]))
        elig = [p.number for p in mates[:max(0, k)]]
        if me.number not in elig:
            return None
        slot = elig.index(me.number)
        opponents = list(inspector.get_opponent_players())
        ball = inspector.get_ball()
        dir_sign = 1.0 if side == lugo4py.TeamSide.HOME else -1.0
        radius = P["def_outlet_radius"]
        best, best_score = None, -1e18
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            sy = math.sin(a)
            if slot == 0 and sy < -0.01:        # 1º elegível: metade superior
                continue
            if slot == 1 and sy > 0.01:         # 2º elegível: metade inferior
                continue
            cand = point(holder.position.x + math.cos(a) * radius,
                         holder.position.y + sy * radius)
            if not (300.0 <= cand.x <= MAX_X - 300.0
                    and 300.0 <= cand.y <= MAX_Y - 300.0):
                continue
            if dir_sign * (cand.x - holder.position.x) < -300.0:
                continue                        # não afundar atrás do portador
            pd = dist(holder.position, cand)
            spd = min(BALL_MAX_SPEED, speed_for_distance(pd) * P["pass_speed_mult"])
            if can_be_intercepted(ball.position, cand, opponents, spd,
                                  USE_VELOCITY):
                continue
            clear = lane_clearance(ball.position, cand, opponents)
            press = self._pressure_on(cand, opponents)
            score = (clear - 1200.0 * press
                     + 0.3 * dir_sign * (cand.x - holder.position.x))
            if score > best_score:
                best_score, best = score, cand
        return best

    def _gk_collect_target(self, inspector, goal_center):
        """C1 v2 (gk_collect): alvo de coleta do goleiro — SÓ o que ele
        alcança DE VERDADE (sonda C0: preso à linha, anda só em y). Bola SEM
        DONO, lenta, a ≤560 da linha (raio de pegada) e com y dentro da boca
        estendida — alinhar o y e agarrar. A v1 (zona inteira + emboscada do
        chaser) PIOROU no screening e virou o gene arquivado zone_ambush.
        None = sem coleta (segue o fluxo normal)."""
        ball = inspector.get_ball()
        h = inspector.get_ball_holder()
        if h is not None and h.number != 0:
            return None                          # bola tem dono
        if abs(ball.position.x - goal_center.x) > geo.GOALKEEPER_HALF_EXTENT:
            return None                          # fundo demais: inalcançável (x travado)
        if not (GOAL_MIN_Y - 700.0 <= ball.position.y <= GOAL_MAX_Y + 700.0):
            return None                          # longe da boca: deixar p/ a linha
        zone_t = getattr(inspector.get_snapshot(), "turns_ball_in_goal_zone", 0)
        urgent = zone_t >= P["gk_zone_alarm"]
        if ball.velocity.speed > P["gk_collect_speed_max"] and not urgent:
            return None                          # bola rápida: _goal_line_threat cuida
        return point(goal_center.x, ball.position.y)

    def _autokick_ambush(self, inspector, me, ball, chasers):
        """C1-b: ponto de emboscada da ejeção automática da zona do gol. Só
        para bola SOLTA dentro da NOSSA zona-1400 e além do alcance em x do
        goleiro (x>~560 da linha, onde nem ele chega — sonda C0: GK travado em
        x). O auto-chute dos 40 turnos mira o CENTRO do campo (10000,5000)
        [MEDIDO]; plantar o 1º chaser no segmento bola->centro a 1450 do centro
        do NOSSO gol captura a saída. None = não se aplica."""
        h = inspector.get_ball_holder()
        if h is not None and h.number != 0:
            return None
        our_goal = self.mapper.get_defense_goal().get_center()
        d_zone = dist(ball.position, our_goal)
        if d_zone > 1380.0:
            return None                       # fora da nossa zona
        depth_x = abs(ball.position.x - our_goal.x)
        if depth_x <= geo.GOALKEEPER_HALF_EXTENT - 60.0:
            return None                       # goleiro alcança (alinha y+catch)
        # só o chaser MAIS PRÓXIMO da bola embosca; o 2º segue o fluxo normal
        if chasers and self.number != chasers[0]:
            return None
        cx, cy = MAX_X / 2.0, MAX_Y / 2.0     # alvo medido do auto-chute
        vx, vy = cx - ball.position.x, cy - ball.position.y
        n = math.hypot(vx, vy) or 1.0
        # ponto no segmento bola->centro a 1450 do centro do nosso gol
        lo, hi = 0.0, 1.0
        for _ in range(24):                   # bisseção: cruza o anel de 1400
            mid = (lo + hi) / 2.0
            px = ball.position.x + vx * mid
            py = ball.position.y + vy * mid
            if math.hypot(px - our_goal.x, py - our_goal.y) < 1450.0:
                lo = mid
            else:
                hi = mid
        px = ball.position.x + vx * hi
        py = ball.position.y + vy * hi
        return point(px, py)

    def _rebound_target(self, inspector, me, ball, side, chasers):
        """D1 (rebound_crash): ponto de convergência para a SEGUNDA BOLA após
        o nosso chute. Só com bola livre rápida rumo ao gol adversário e já no
        terço de ataque. Ponto de queda = fim de ball_trajectory, clampado FORA
        da zona-1400 deles (jogador de linha não entra). Os
        `rebound_crashers` meias/atacantes não-chasers mais próximos convergem,
        espalhados em y por slot. None = não sou crasher."""
        if (self.number not in tac.MIDFIELDERS
                and self.number not in tac.FORWARDS):
            return None
        if ball.velocity.speed < 150.0:
            return None
        if tac.ball_advance_frac(ball.position, side) < P["rebound_zone_frac"]:
            return None
        goal_center = self.mapper.get_attack_goal().get_center()
        vx, vy = ball.velocity.direction.x, ball.velocity.direction.y
        gx, gy = goal_center.x - ball.position.x, goal_center.y - ball.position.y
        if vx * gx + vy * gy <= 0.0:
            return None                          # não vai na direção do gol deles
        traj = geo.ball_trajectory(ball, max_turns=40)
        _t, ex, ey = traj[-1]
        dgo = math.hypot(ex - goal_center.x, ey - goal_center.y)
        if dgo < 1500.0:                          # fora da zona deles
            ex = goal_center.x + (ex - goal_center.x) / (dgo or 1.0) * 1500.0
            ey = goal_center.y + (ey - goal_center.y) / (dgo or 1.0) * 1500.0
        drop = point(ex, ey)
        cand = [p for p in inspector.get_my_team_players()
                if p.number not in chasers and p.number != tac.GOALKEEPER
                and (p.number in tac.MIDFIELDERS or p.number in tac.FORWARDS)]
        cand.sort(key=lambda p: (dist(p.position, drop), p.number))
        k = int(round(P["rebound_crashers"]))
        chosen = [p.number for p in cand[:max(0, k)]]
        if self.number not in chosen:
            return None
        slot = chosen.index(self.number)
        off = (slot - (len(chosen) - 1) / 2.0) * 800.0
        return point(ex, max(300.0, min(MAX_Y - 300.0, ey + off)))

    def _shield_clamp(self, inspector, base):
        """v7/METAMORFO (kickoff_shield): por ks_turns pós-reset, DEFENDERS e
        MIDFIELDERS têm o Y da posição de FORMAÇÃO clampado ao corredor
        central (|y-5000| <= ks_halfwidth). SÓ y — nunca recua x, nunca
        empurra ninguém ao centro (clamp = min/max: quem já está no corredor
        fica intocado). Fecha a janela ~15s pós-kickoff/pós-gol em que o BotAdversario1
        novo marca (único gol dele no 1×1: transição central contra bloco
        desorganizado 16s pós-gol). Modificador do fallback de formação:
        perde para TODOS os branches anteriores. off = base intocada."""
        if P.get("kickoff_shield") != "on":
            return base
        if (self.number not in tac.DEFENDERS
                and self.number not in tac.MIDFIELDERS):
            return base
        rt = getattr(self, "_reset_turn", None)
        if rt is None:
            return base
        try:
            turn = inspector.get_snapshot().turn
        except Exception:
            return base
        if turn < rt or turn - rt > P["ks_turns"]:
            return base
        lo = MAX_Y / 2.0 - P["ks_halfwidth"]
        hi = MAX_Y / 2.0 + P["ks_halfwidth"]
        return point(base.x, max(lo, min(hi, base.y)))

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
        ref_y = ball.position.y
        div = 3000.0
        # C3 (gk_guard_mode="track"): com o ADVERSÁRIO segurando em zona
        # perigosa, a linha de chute nasce no PORTADOR — alinhar ao y dele com
        # saturação mais curta (gk_track_div), não ao da bola amortecido. off=v2.
        if P.get("gk_guard_mode") == "track":
            h = inspector.get_ball_holder()
            if (h is not None and h.number != 0
                    and h.team_side != inspector.get_my_team_side()
                    and dist(h.position, goal_center) <= P["dangerous_shot_range"]):
                ref_y = h.position.y
                div = P["gk_track_div"]
        dy = ref_y - goal_center.y
        # segue a bola em y, limitado à boca do gol
        y = goal_center.y + max(-1.0, min(1.0, dy / div)) * P["gk_y_range"]
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

        # C4 (gk_clear_mode="safe"): se o relógio da zona está prestes a
        # estourar (40 turnos ⇒ auto-chute ao CENTRO = rebote servido ao
        # camper), chutão de flanco IMEDIATO — nunca esperar o auto-chute.
        safe_mode = P.get("gk_clear_mode") == "safe"
        if safe_mode:
            zone_t = getattr(inspector.get_snapshot(),
                             "turns_ball_in_goal_zone", 0)
            if zone_t >= P["gk_zone_alarm"]:
                far_y = 500 if me.position.y > MAX_Y / 2 else MAX_Y - 500
                target = point(goal_center.x * 0.35 + me.position.x * 0.65, far_y)
                return geo.kick_to(inspector, me, inspector.get_ball(), target,
                                   BALL_MAX_SPEED)

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
            if safe_mode:
                # C4: corrida no destino (padrão pass_endpoint_race) + veto por
                # fronteiras de turno com origem na bola — o veto v2 (estático,
                # cego a <700d) deixava a saída do goleiro ser interceptada.
                t_recv = turns_for_player(dist(mate.position, target))
                if any(turns_for_player(dist(o.position, target))
                       <= t_recv + P["gk_clear_margin"] for o in opponents):
                    continue
                if geo.intercept_slack_turnwise(
                        inspector.get_ball().position, target, opponents,
                        speed) <= 0.0:
                    continue
            elif opponent_can_intercept(me.position, target, opponents, speed):
                continue
            score = -dist(target, goal_center) + 1.5 * lane_clearance(
                me.position, target, opponents)
            if safe_mode:
                score += P["gk_clear_w_flank"] * abs(target.y - MAX_Y / 2.0)
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
    def _opps_within(pos, opponents, radius) -> int:
        """v7 (outlet_press_detect): CONTAGEM crua de adversários em `radius`
        (a _pressure_on é soma ponderada — não serve de contagem de cerco).
        Mock-safe: só posições."""
        return sum(1 for o in opponents if dist(pos, o.position) <= radius)

    @staticmethod
    def _player_status(pos, opponents, opp_gk, goal_center):
        """(estado, t_reach) do jogador em `pos`. estado in {"livre","atencao",
        "perigo"} pela banda de turnos ate o adversario mais proximo alcancar
        `pos`. Coerente com o veto: turns_for_player(d)=(d-300)/100. O goleiro
        adversario e' EXCLUIDO por padrao (status_count_gk="off"); com "on" entra
        com reach 560. Velocity-aware se USE_VELOCITY (so ANTECIPA a ameaca).
        status_measure="ball" mede ~200 a frente, rumo ao gol de ataque. So e'
        chamado com pass_status_mode="on"; o caminho default (off) nunca executa."""
        # Comp 1 v2: marcacao por AREA de conducao segura (spec do usuario) em vez
        # do raio. preso => perigo; restrito => atencao; senao livre. off = raio (v9).
        if P.get("status_metric") == "area":
            f = carry.dribble_freedom(pos, opponents, opp_gk, goal_center)
            if f["cls"] == "preso":
                return "perigo", 0.0
            if f["cls"] == "restrito":
                return "atencao", 1.0
            return "livre", 9.0
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
