#!/usr/bin/env python3
"""Re-simula uma CENA (sim/scene_extract.py) com o my_bot REAL nos nossos 11.

Modelo:
  - ADVERSÁRIO = ghosts: seguem as trajetórias extraídas do vídeo; a BOLA é
    "fantasma" (segue a trajetória extraída) enquanto o lance original corre.
  - NOSSOS 11 = vivos: MyBot de verdade (bot/src) via inspector-mock, um por
    jogador, decidindo a cada turno sobre o estado corrente.
  - Se um vivo CAPTURA a bola (raio 300 / GK 560, com catch, mais perto que o
    dono-fantasma), a bola vira física normal (fastsim) e os ghosts trocam
    para uma política simples de recuperação/punição: 2 mais próximos caçam;
    portador ghost conduz ao nosso gol e chuta de <4500 no canto longe do GK.
  - FAIL = gol sofrido (fantasma cruza a linha, ou ghost re-rouba e marca).
    PASS = fim da janela +80 turnos sem gol sofrido.

Uso:
  BOT_PARAMS='<genoma>' python sim/scene_runner.py sim/scenes/*.json [--seeds 10]
"""
import argparse
import glob
import json
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "bot", "src"))
sys.path.insert(0, HERE)

import lugo4py                                        # noqa: E402
import fastsim as F                                   # noqa: E402
import geometry as geo                                # noqa: E402
from my_bot import MyBot                              # noqa: E402

TOUCH = 300.0
GK_TOUCH = 560.0
EXTRA_TURNS = 80
PASS_DIST = 7000.0        # bola a isto do nosso gol com posse nossa = escape


class D:
    def __init__(self, **k):
        self.__dict__.update(k)


def P2(x, y):
    return D(x=float(x), y=float(y))


def vel_obj(vx, vy):
    sp = math.hypot(vx, vy)
    if sp < 1e-9:
        return D(direction=D(x=0.0, y=0.0), speed=0.0)
    return D(direction=D(x=vx / sp, y=vy / sp), speed=sp)


class Goal:
    def __init__(self, x):
        self._c = P2(x, 5000.0)

    def get_center(self):
        return self._c


class Mapper:
    def get_attack_goal(self):
        return Goal(20000.0)

    def get_defense_goal(self):
        return Goal(0.0)


class Team:
    def __init__(self, score):
        self.score = score


class Snapshot:
    def __init__(self, turn, zone):
        self.turn = turn
        self.turns_ball_in_goal_zone = zone


class Inspector:
    """Inspector-mock completo p/ os callbacks do MyBot (nós = HOME)."""

    def __init__(self, world, me_num):
        self.w = world
        self.me_num = me_num

    def get_me(self):
        return self.w.home_objs[self.me_num - 1]

    def get_my_team_players(self):
        return self.w.home_objs

    def get_opponent_players(self):
        return self.w.away_objs

    def get_ball(self):
        return self.w.ball_obj

    def get_ball_holder(self):
        return self.w.holder_obj

    def get_opponent_goalkeeper(self):
        return self.w.away_objs[0]

    def get_my_team_side(self):
        return lugo4py.TeamSide.HOME

    def get_snapshot(self):
        return self.w.snapshot

    def get_turn(self):
        return self.w.snapshot.turn

    def get_my_team(self):
        return Team(0)

    def get_opponent_team(self):
        return Team(0)

    def is_ball_holder(self, player):
        h = self.w.holder_obj
        return (h is not None and h.team_side == lugo4py.TeamSide.HOME
                and h.number == player.number)

    # ---- fábricas de ordem (dicts; o conversor entende) ----
    def make_order_move(self, target, speed):
        return {"__move__": (target.x, target.y, float(speed))}

    def make_order_move_max_speed(self, target):
        return {"__move__": (target.x, target.y, 100.0)}

    def make_order_catch(self):
        return {"__catch__": True}

    def make_order_jump(self, target, speed):
        return {"__jump__": (target.x, target.y, float(speed))}


def order_to_action(o, px, py):
    """Ordem (dict-mock ou protobuf de geo.kick_to) -> ação fastsim."""
    if isinstance(o, dict):
        if "__move__" in o:
            tx, ty, sp = o["__move__"]
            dx, dy = tx - px, ty - py
            n = math.hypot(dx, dy)
            if n < 1e-9:
                return {"move": (0.0, 0.0)}
            return {"move": (dx / n * sp, dy / n * sp)}
        if "__catch__" in o:
            return {"catch": True}
        if "__jump__" in o:
            tx, ty, sp = o["__jump__"]
            dx, dy = tx - px, ty - py
            n = math.hypot(dx, dy) or 1.0
            return {"jump": (dx / n * sp, dy / n * sp)}
        return {}
    # protobuf Order (kick de geo.kick_to)
    try:
        k = o.kick.velocity
        dx, dy, sp = k.direction.x, k.direction.y, k.speed
        n = math.hypot(dx, dy) or 1.0
        return {"kick": (dx / n * sp, dy / n * sp)}
    except Exception:
        return {}


class World:
    """Snapshot corrente exposto aos inspectors."""

    def refresh(self, s, holder, turn):
        self.home_objs = []
        for i in range(11):
            self.home_objs.append(D(
                number=i + 1, team_side=lugo4py.TeamSide.HOME,
                position=P2(*s.pos[F.HOME, i]),
                velocity=vel_obj(*s.vel[F.HOME, i])))
        self.away_objs = []
        for i in range(11):
            self.away_objs.append(D(
                number=i + 1, team_side=lugo4py.TeamSide.AWAY,
                position=P2(*s.pos[F.AWAY, i]),
                velocity=vel_obj(*s.vel[F.AWAY, i])))
        self.ball_obj = D(position=P2(*s.ball_pos),
                          velocity=vel_obj(*s.ball_vel))
        if holder is None:
            self.holder_obj = None
        else:
            side, idx = holder
            objs = self.home_objs if side == F.HOME else self.away_objs
            self.holder_obj = objs[idx]
        self.snapshot = Snapshot(turn, 0)


def run_scene(scene, seed=0, jitter=120.0, log=None):
    """True = PASS (sem gol sofrido), False = FAIL."""
    rng = random.Random(seed)
    Htr = np.asarray(scene["home"])
    Atr = np.asarray(scene["away"])
    Btr = np.asarray(scene["ball"])
    n_scene = len(Btr)

    s = F.State()
    for i in range(11):
        jx = rng.uniform(-jitter, jitter) if (seed and i != 0) else 0.0
        jy = rng.uniform(-jitter, jitter) if (seed and i != 0) else 0.0
        s.pos[F.HOME, i] = [Htr[0, i, 0] + jx, Htr[0, i, 1] + jy]
        s.pos[F.AWAY, i] = Atr[0, i]
        # FIDELIDADE: vivos começam com a VELOCIDADE real (não parados)
        s.vel[F.HOME, i] = Htr[1, i] - Htr[0, i]
    s.ball_pos[:] = Btr[0]
    s.turn = 0
    WARMUP = 3      # turnos em que os vivos SEGUEM o vídeo (reação real ~150ms)
                    # — o contrafactual só começa depois; sem isso os vivos
                    # "re-decidem do zero" um lance que no real já corria

    bots = []
    for i in range(11):
        b = MyBot.__new__(MyBot)
        b.number = i + 1
        b.mapper = Mapper()
        bots.append(b)
    world = World()

    ghost_mode = True          # bola-fantasma seguindo a trajetória
    captured_at = None
    total = n_scene + EXTRA_TURNS
    for t in range(total):
        # ---------- bola / ghosts ----------
        if ghost_mode:
            ti = min(t, n_scene - 1)
            prev = s.ball_pos.copy()
            s.ball_pos[:] = Btr[ti]
            s.ball_vel[:] = (Btr[min(ti + 1, n_scene - 1)] - Btr[ti])
            for i in range(11):
                s.pos[F.AWAY, i] = Atr[ti, i]
                s.vel[F.AWAY, i] = (Atr[min(ti + 1, n_scene - 1), i]
                                    - Atr[ti, i])
            # dono-fantasma: ghost mais próximo a <=300
            da = np.hypot(Atr[ti, :, 0] - s.ball_pos[0],
                          Atr[ti, :, 1] - s.ball_pos[1])
            gidx = int(np.argmin(da))
            holder = (F.AWAY, gidx) if da[gidx] <= TOUCH else None
            # GOL fantasma? (bola cruzou a linha do nosso gol na boca)
            if (s.ball_pos[0] <= 60.0
                    and F.GOAL_MIN_Y - 100 <= s.ball_pos[1] <= F.GOAL_MAX_Y + 100):
                if log is not None:
                    log.append((t, "GOL fantasma"))
                return False
            if t >= n_scene - 1:
                # trajetória acabou (animação truncou o desfecho): resolver
                # por FÍSICA — com dono ghost, ele joga a política de punição
                # (conduz+chuta); bola solta segue a última velocidade.
                if holder is not None:
                    s.holder = holder
                    ghost_mode = False
                    if log is not None:
                        log.append((t, "fim da trajetória: física assume"))
                    continue
                for _ in range(30):
                    scored = F._move_ball(s)
                    if scored == F.AWAY:
                        if log is not None:
                            log.append((t, "GOL extrapolado"))
                        return False
                return True
        else:
            holder = s.holder
            # ghosts pós-captura: 2 mais próximos caçam; portador ghost
            # conduz ao nosso gol e chuta; demais mantêm posição
            orders_a = [None] * 11
            da = np.hypot(s.pos[F.AWAY, :, 0] - s.ball_pos[0],
                          s.pos[F.AWAY, :, 1] - s.ball_pos[1])
            chase = np.argsort(da)[:2]
            for i in range(11):
                if s.holder == (F.AWAY, i):
                    gd = math.hypot(s.pos[F.AWAY, i, 0],
                                    s.pos[F.AWAY, i, 1] - 5000.0)
                    if gd < 4500.0:
                        gk_y = s.pos[F.HOME, 0, 1]
                        ty = F.GOAL_MIN_Y + 250 if gk_y > 5000 else F.GOAL_MAX_Y - 250
                        dx, dy = 0.0 - s.pos[F.AWAY, i, 0], ty - s.pos[F.AWAY, i, 1]
                        n = math.hypot(dx, dy) or 1.0
                        orders_a[i] = {"kick": (dx / n * 400.0, dy / n * 400.0)}
                    else:
                        dx, dy = 0.0 - s.pos[F.AWAY, i, 0], 5000.0 - s.pos[F.AWAY, i, 1]
                        n = math.hypot(dx, dy) or 1.0
                        orders_a[i] = {"move": (dx / n * 100.0, dy / n * 100.0)}
                elif i in chase:
                    dx = s.ball_pos[0] - s.pos[F.AWAY, i, 0]
                    dy = s.ball_pos[1] - s.pos[F.AWAY, i, 1]
                    n = math.hypot(dx, dy) or 1.0
                    orders_a[i] = {"move": (dx / n * 100.0, dy / n * 100.0),
                                   "catch": True}
                else:
                    orders_a[i] = {"move": (0.0, 0.0)}

        # ---------- warmup: vivos seguem o vídeo ----------
        if t < WARMUP and ghost_mode:
            ti2 = min(t, n_scene - 2)
            for i in range(11):
                s.vel[F.HOME, i] = Htr[ti2 + 1, i] - Htr[ti2, i]
                F._advance_player(s, F.HOME, i)
            s.turn += 1
            continue

        # ---------- nossos vivos decidem ----------
        world.refresh(s, holder if ghost_mode else s.holder, t)
        orders_h = [None] * 11
        for i in range(11):
            bot = bots[i]
            insp = Inspector(world, i + 1)
            me = world.home_objs[i]
            try:
                h = (holder if ghost_mode else s.holder)
                if i == 0:
                    ords = bot.as_goalkeeper(insp, None) or []
                elif h is None:
                    ords = bot.on_disputing(insp) or []
                elif h[0] == F.HOME:
                    ords = (bot.on_holding(insp) if h[1] == i
                            else bot.on_supporting(insp)) or []
                else:
                    ords = bot.on_defending(insp) or []
            except Exception:
                ords = []
            act = {}
            for o in ords:
                act.update(order_to_action(o, me.position.x, me.position.y))
            orders_h[i] = act

        # ---------- aplicar ----------
        if ghost_mode:
            # move só os vivos; tenta captura
            for i in range(11):
                o = orders_h[i]
                m = o.get("move")
                if m is not None:
                    v = F._clip_speed(np.array(m, dtype=np.float64), 100.0)
                    s.vel[F.HOME, i] = v
                    F._advance_player(s, F.HOME, i)
                if o.get("catch"):
                    d = math.hypot(s.ball_pos[0] - s.pos[F.HOME, i, 0],
                                   s.ball_pos[1] - s.pos[F.HOME, i, 1])
                    radius = GK_TOUCH if i == 0 else TOUCH
                    # FIDELIDADE: bola em POSSE-fantasma é defendida pelo
                    # dono (re-captura constante no real) — roubo só colado
                    # (150). Bola SOLTA (passe em trânsito) = captura normal:
                    # interceptar o passe É o contrafactual que a cena mede.
                    if holder is not None:
                        radius = min(radius, 150.0)
                    dh = (da[gidx] if holder is not None else 1e18)
                    if d <= radius and d < dh:
                        # CAPTURA: mundo vira física normal
                        s.holder = (F.HOME, i)
                        ghost_mode = False
                        captured_at = t
                        if log is not None:
                            log.append((t, f"captura por #{i+1}"))
                        break
            s.turn += 1
        else:
            s = F.step(s, orders_h, orders_a)
            if log is not None and os.environ.get("SCENE_TRACE"):
                hstr = ("-" if s.holder is None
                        else f"{'H' if s.holder[0]==F.HOME else 'A'}{s.holder[1]+1}")
                log.append((t, f"h={hstr} b=({s.ball_pos[0]:.0f},"
                               f"{s.ball_pos[1]:.0f})"))
            if s.score[F.AWAY] > 0:
                if log is not None:
                    log.append((t, "GOL pós-captura"))
                return False
            # escape: posse nossa e bola longe do nosso gol
            if (s.holder is not None and s.holder[0] == F.HOME
                    and math.hypot(s.ball_pos[0], s.ball_pos[1] - 5000.0)
                    > PASS_DIST):
                if log is not None:
                    log.append((t, "escape limpo"))
                return True
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes", nargs="+")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    files = []
    for pat in args.scenes:
        files += sorted(glob.glob(pat))
    total_pass = 0
    total_runs = 0
    for f in files:
        scene = json.load(open(f))
        results = []
        for seed in range(args.seeds):
            log = [] if args.verbose else None
            ok = run_scene(scene, seed=seed, log=log)
            results.append(ok)
            if args.verbose and log:
                print(f"    seed{seed}: {log}")
        p = sum(results)
        total_pass += p
        total_runs += len(results)
        name = os.path.basename(f).replace(".json", "")
        print(f"{name:16s}  PASS {p}/{len(results)}"
              f"  {'✓' if p == len(results) else ''}")
    print(f"\nTOTAL: {total_pass}/{total_runs} "
          f"({100.0 * total_pass / max(1, total_runs):.0f}%)")


if __name__ == "__main__":
    main()
