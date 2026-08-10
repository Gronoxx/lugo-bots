"""
FRENTE 3 - biblioteca de metricas por replay/lado.

Convencao: tudo e calculado do ponto de vista de UM lado ("us"), com o campo
espelhado para que "us" SEMPRE ataque em x=20000.

Descobertas da exploracao (var_1.json):
  - bola presa a um jogador  -> speed == 100 sempre
  - chute/passe = transicao holder -> solto com aumento de velocidade
  - gol = placar sobe e bola volta para (10000,5000)
"""
import os
import numpy as np

D = "<cache local>"

FX, FY = 20000.0, 10000.0
GOAL_LO, GOAL_HI = 3500.0, 6500.0
GOAL_C = 5000.0
DECEL = 10.0


def travel_distance(v0):
    """Distancia total percorrida por uma bola solta com velocidade v0.
    Avanco por turno = v-5, decel 10/turno, para quando v<=2."""
    d, v = 0.0, float(v0)
    while v > 2:
        d += max(v - 5.0, 0.0)
        v -= DECEL
    return d


_TRAVEL = {}


def travel(v0):
    k = int(round(v0))
    if k not in _TRAVEL:
        _TRAVEL[k] = travel_distance(k)
    return _TRAVEL[k]


def turns_to_cover(v0, dist):
    """Quantos turnos para a bola cobrir `dist`; inf se nao alcanca."""
    d, v, t = 0.0, float(v0), 0
    while v > 2:
        d += max(v - 5.0, 0.0)
        t += 1
        if d >= dist:
            return t
        v -= DECEL
    return np.inf


class Match:
    """Um replay visto do lado `side` (0=home, 1=away), campo espelhado."""

    def __init__(self, name, side):
        d = np.load(os.path.join(D, name + ".npz"))
        self.name, self.side = name, side
        mir = (side == 1)
        s = -1.0 if mir else 1.0
        off = FX if mir else 0.0

        self.turn = d["turn"]
        self.n = len(self.turn)
        self.bx = off + s * d["bx"]
        self.by = d["by"] if not mir else FY - d["by"]
        self.bdx = s * d["bdx"]
        self.bdy = d["bdy"] if not mir else -d["bdy"]
        self.bsp = d["bsp"]

        hs = d["hold_side"]
        # 1 = nosso, 0 = deles, -1 = solta
        self.hold = np.where(hs < 0, -1, (hs == side).astype(np.int8))
        self.hold_num = d["hold_num"]

        self.us_score = d["sh"] if side == 0 else d["sa"]
        self.them_score = d["sa"] if side == 0 else d["sh"]

        px, py = d["px"], d["py"]
        self.us_x = off + s * px[:, side, :]
        self.us_y = py[:, side, :] if not mir else FY - py[:, side, :]
        o = 1 - side
        self.op_x = off + s * px[:, o, :]
        self.op_y = py[:, o, :] if not mir else FY - py[:, o, :]
        self.op_num = d["pnum"][:, o, :]

        self.reset = (d["bx"] == 10000) & (d["by"] == 5000) & (d["bsp"] == 0)
        self._kicks = None

    # ------------------------------------------------------------ eventos
    def kicks(self):
        """Lista de chutes/passes: dict com turno, pos, dir, speed, dono, gol."""
        if self._kicks is not None:
            return self._kicks
        ev = []
        h = self.hold
        for i in range(self.n - 1):
            if h[i] >= 0 and h[i + 1] < 0 and self.bsp[i + 1] > self.bsp[i] + 5:
                if self.reset[i + 1]:
                    continue
                ev.append(self._kick_info(i))
        self._kicks = ev
        return ev

    def _kick_info(self, i):
        j = i + 1
        x0, y0 = self.bx[j], self.by[j]
        # origem real do chute ~ posicao no turno i
        ox, oy = self.bx[i], self.by[i]
        dx, dy = self.bdx[j], self.bdy[j]
        v = self.bsp[j]
        mine = self.hold[i] == 1

        # resultado: percorre ate a bola ser presa de novo, parar ou gol
        goal = False
        end = j
        for k in range(j, min(j + 60, self.n)):
            if mine and self.us_score[k] > self.us_score[j]:
                goal = True
                end = k
                break
            if (not mine) and self.them_score[k] > self.them_score[j]:
                goal = True
                end = k
                break
            if self.reset[k]:
                break
            if self.hold[k] >= 0:
                end = k
                break
            end = k

        gx = FX if mine else 0.0
        dist = float(np.hypot(gx - ox, GOAL_C - oy))
        # intersecao da reta do chute com a linha de gol
        yc, tt, reaches = np.nan, np.inf, False
        denom = dx if mine else -dx
        if denom > 1e-6:
            lam = (gx - ox) / dx
            yc = oy + lam * dy
            reaches = travel(v) >= lam - 1e-9
            tt = turns_to_cover(v, lam)
        on_target = bool(reaches and GOAL_LO - 100 <= yc <= GOAL_HI + 100)

        # goleiro adversario (do time que defende gx)
        if mine:
            gkx, gky, num = self.op_x[j], self.op_y[j], self.op_num[j]
        else:
            gkx, gky, num = self.us_x[j], self.us_y[j], np.zeros(11)
        gk_gap = np.nan
        if mine:
            sel = np.where(num == 1)[0]
            if len(sel) and np.isfinite(yc):
                gk_gap = abs(gky[sel[0]] - yc)

        return dict(i=i, turn=int(self.turn[i]), x=float(ox), y=float(oy),
                    dx=float(dx), dy=float(dy), v=float(v), mine=bool(mine),
                    goal=bool(goal), dist=dist, y_cross=float(yc),
                    on_target=on_target, t_arrive=float(tt),
                    gk_gap=float(gk_gap) if np.isfinite(gk_gap) else np.nan,
                    end=end)

    def possessions(self):
        """Sequencias contiguas de posse (ignora turnos com bola solta:
        a posse continua se o mesmo lado retoma antes do outro tocar)."""
        seq = []
        cur = None
        for i in range(self.n):
            h = self.hold[i]
            if h < 0:
                continue
            if cur is None or cur["side"] != h:
                if cur is not None:
                    cur["end"] = i - 1
                    seq.append(cur)
                cur = dict(side=int(h), start=i, end=i)
            else:
                cur["end"] = i
        if cur is not None:
            seq.append(cur)
        return seq
