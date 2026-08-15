"""Logica de CONDUCAO + MARCACAO (spec do usuario), como primitivas puras.

MARCACAO = area de conducao segura por direcao (NAO um raio): todo ponto aonde o
portador pode conduzir a bola (100/turno) sem ser desarmado nos proximos t turnos,
ponderada por direcao (rumo ao gol > lateral > tras). A assimetria frente/tras
EMERGE da reachability (marcador atras nao intercepta a cunha frontal). Seguranca
de um raio: para todo passo s=1..t e todo adversario k, |B(s)-Q_k| > 100*s+reach.

Tudo default-off no bot; estas sao funcoes puras usadas por my_bot quando
hold_logic="caso" / status_metric="area".
"""
import math

import geometry as geo
from geometry import PLAYER_SPEED, point
from params import P


def _opp_discs(opponents, gk, count_gk):
    """Lista (x, y, reach) dos adversarios; GK excluido salvo count_gk."""
    gknum = gk.number if gk is not None else -1
    out = []
    for o in opponents:
        is_gk = (o.number == gknum)
        if is_gk and not count_gk:
            continue
        reach = geo.GOALKEEPER_HALF_EXTENT if is_gk else geo.TOUCH_RADIUS
        out.append((o.position.x, o.position.y, reach))
    return out


def _safe_reach(bx, by, dx, dy, opps, t_max, step):
    """Maior distancia segura conduzindo de (bx,by) na direcao unitaria (dx,dy)."""
    safe = 0.0
    for s in range(1, t_max + 1):
        px, py = bx + dx * step * s, by + dy * step * s
        if not (0.0 <= px <= geo.MAX_X and 0.0 <= py <= geo.MAX_Y):
            break
        blocked = False
        for ox, oy, reach in opps:
            if math.hypot(px - ox, py - oy) <= step * s + reach:
                blocked = True
                break
        if blocked:
            break
        safe = step * s
    return safe


def dribble_freedom(me_pos, opponents, gk, goal_center):
    """Marcacao por AREA. Devolve dict:
      fwd/lat/back : fracao media da reach segura (0..1) nas cunhas rumo-ao-gol /
                     lateral / tras (ponderacao por direcao da spec).
      total        : fracao media geral.
      cls          : 'livre_gol' | 'lateral' | 'restrito' | 'preso'.
      best_fwd     : endpoint seguro que MAIS progride rumo ao gol (Caso 1/2.a) ou None.
      best_free    : endpoint seguro de maior reach (Caso 2.b reposicionar) ou None.
    """
    t_max = int(round(P["mark_t_max"]))
    n_dirs = int(round(P["mark_n_dirs"]))
    opps = _opp_discs(opponents, gk, P.get("status_count_gk") == "on")
    bx, by = float(me_pos.x), float(me_pos.y)
    gdx, gdy = goal_center.x - bx, goal_center.y - by
    gn = math.hypot(gdx, gdy) or 1.0
    gdx, gdy = gdx / gn, gdy / gn
    step = PLAYER_SPEED
    maxd = step * t_max
    fwd = lat = back = 0.0
    nf = nl = nb = 0
    best_fwd = (-1.0, None)
    best_free = (-1.0, None)
    for i in range(n_dirs):
        a = 2.0 * math.pi * i / n_dirs
        dx, dy = math.cos(a), math.sin(a)
        safe = _safe_reach(bx, by, dx, dy, opps, t_max, step)
        comp = dx * gdx + dy * gdy       # projecao na direcao do gol
        frac = safe / maxd
        if comp > 0.5:
            fwd += frac; nf += 1
        elif comp < -0.5:
            back += frac; nb += 1
        else:
            lat += frac; nl += 1
        if safe > 0.0 and comp > 0.3:
            prog = comp * safe
            if prog > best_fwd[0]:
                best_fwd = (prog, point(bx + dx * safe, by + dy * safe))
        if safe > best_free[0]:
            best_free = (safe, point(bx + dx * safe, by + dy * safe))
    fwd = fwd / nf if nf else 0.0
    lat = lat / nl if nl else 0.0
    back = back / nb if nb else 0.0
    ntot = nf + nl + nb
    total = (fwd * nf + lat * nl + back * nb) / ntot if ntot else 0.0
    if fwd > P["mark_free_frac"]:
        cls = "livre_gol"
    elif fwd > 0.2 or lat > 0.4:
        cls = "lateral"
    elif total < P["mark_trapped_frac"]:
        cls = "preso"
    else:
        cls = "restrito"
    return dict(fwd=fwd, lat=lat, back=back, total=total, cls=cls,
                best_fwd=best_fwd[1], best_free=best_free[1])


def is_marked(me_pos, opponents, gk, goal_center):
    """Atalho booleano p/ 'esta marcado' (sem rota segura rumo ao gol)."""
    f = dribble_freedom(me_pos, opponents, gk, goal_center)
    return f["cls"] in ("restrito", "preso") or f["fwd"] <= 0.2
