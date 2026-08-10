#!/usr/bin/env python3
"""
FRENTE 2 — Onde a posse morre.

Segmenta cada partida em POSSES (sequências de controle de um time), classifica
como cada posse termina (finalização, interceptação de passe, condução tomada,
shot clock) e onde no campo isso acontece.

Só lê replays. Não modifica o bot, não roda partidas.

Uso:  .venv/bin/python analysis/frente2_possession.py [replay ...]
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay  # noqa: E402
from replay import ball_pos, ball_speed, holder, players, pt  # noqa: E402

MAX_X, MAX_Y = 20000, 10000
GOAL_MIN_Y, GOAL_MAX_Y = 3500, 6500
BALL_DECEL = 10.0
TOUCH_RADIUS = 300.0
PLAYER_SPEED = 100.0

REC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "bench", "recordings")

# (arquivo, nosso lado, rótulo). None = não jogamos (baseline).
MATCHES = [
    ("dummies_vs_dummies.json", "HOME", "BASELINE dummies(HOME) x dummies"),
    ("t1.json", "HOME", "v1 HOME x dummies"),
    ("eval_0_norm.json", "HOME", "v2 HOME x dummies"),
    ("var_1.json", "HOME", "v3 HOME x dummies"),
    ("var_2.json", "HOME", "v3 HOME x dummies (2)"),
    ("swap.json", "AWAY", "v3 AWAY x dummies"),
    ("v6_check.json", "HOME", "v6 HOME x dummies"),
    ("smoke_rival.json", "HOME", "v3 HOME x rival_p1"),
    ("p_rival_p2_home_1.json", "HOME", "v3 HOME x rival_p2"),
]


# --------------------------------------------------------------- utilidades
def ball_range(v0):
    """Distância total que a bola percorre saindo a v0 (avanço = v-5/turno)."""
    d, v = 0.0, float(v0)
    while v > 2:
        d += v - 5
        v -= BALL_DECEL
    return max(0.0, d)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def seg_point_dist(a, b, p):
    """Distância do ponto p ao segmento ab."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return dist(a, p)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def load_turns(path):
    """Retorna (lista de turnos, gols).

    turno = dict(turn, ball=(x,y), speed, dir=(dx,dy), holder=(side,num)|None,
                 players={side: {num: (x,y)}}, sc=(side, remaining), score)
    Um snapshot por turno (o último do turno).
    """
    _cfg, events = replay.load(path)
    per = {}
    goals = []
    prev_h = prev_a = 0
    for e in events:
        gs = e.get("game_snapshot")
        if not gs:
            continue
        t = gs.get("turn", 0)
        per[t] = gs
        h = (gs.get("home_team", {}) or {}).get("score", 0)
        a = (gs.get("away_team", {}) or {}).get("score", 0)
        if h > prev_h:
            goals.append(("HOME", t))
        if a > prev_a:
            goals.append(("AWAY", t))
        prev_h, prev_a = h, a

    turns = []
    for t in sorted(per):
        gs = per[t]
        b = gs.get("ball", {}) or {}
        vel = b.get("velocity", {}) or {}
        d = vel.get("direction", {}) or {}
        dx, dy = d.get("x", 0.0), d.get("y", 0.0)
        n = math.hypot(dx, dy) or 1.0
        sc = gs.get("shot_clock") or {}
        turns.append(dict(
            turn=t,
            ball=ball_pos(gs),
            speed=vel.get("speed", 0),
            dir=(dx / n, dy / n),
            holder=holder(gs),
            players={s: {p.get("number", 0): pt(p.get("position"))
                         for p in players(gs, s.lower())}
                     for s in ("HOME", "AWAY")},
            sc=(sc.get("team_side", "HOME"), sc.get("remaining_turns")),
        ))
    return turns, goals


# ------------------------------------------------------------------- posses
HYST_WINDOW = 12   # turnos olhados à frente para decidir se a virada é real
HYST_MIN = 3       # toques do adversário na janela para caracterizar virada


def touch_runs(turns):
    """Sequências consecutivas do mesmo estado ('HOME'/'AWAY'/'LOOSE')."""
    runs = []
    cur, start = None, 0
    for i, T in enumerate(turns):
        h = T["holder"]
        s = h[0] if h else "LOOSE"
        if s != cur:
            if cur is not None:
                runs.append((cur, start, i - 1))
            cur, start = s, i
    runs.append((cur, start, len(turns) - 1))
    return runs


def segment_possessions(turns):
    """Divide a partida em posses com histerese contra disputa picotada.

    Regra: a posse pertence a S enquanto os toques forem de S. Quando O toca,
    olhamos os próximos HYST_WINDOW turnos: se O tocar >= HYST_MIN turnos e
    mais que S, é virada de posse (a posse de S termina no primeiro toque de
    O); senão o toque de O é um roubo momentâneo dentro da disputa.
    """
    n = len(turns)
    side_of = []
    for T in turns:
        h = T["holder"]
        side_of.append(h[0] if h else None)

    poss = []
    cur_side = None
    cur_start = None
    i = 0
    while i < n:
        s = side_of[i]
        if s is None:
            i += 1
            continue
        if cur_side is None:
            cur_side, cur_start = s, i
            i += 1
            continue
        if s == cur_side:
            i += 1
            continue
        # adversário tocou: virada real?
        opp = s
        w = turns[i:i + HYST_WINDOW]
        c_opp = sum(1 for T in w if T["holder"] and T["holder"][0] == opp)
        c_cur = sum(1 for T in w if T["holder"] and T["holder"][0] == cur_side)
        if c_opp >= HYST_MIN and c_opp > c_cur:
            poss.append(dict(side=cur_side, i0=cur_start, i1=i - 1, iend=i))
            cur_side, cur_start = opp, i
        i += 1
    if cur_side is not None:
        poss.append(dict(side=cur_side, i0=cur_start, i1=n - 1, iend=n - 1))
    return poss


# ------------------------------------------------------------------- chutes
def detect_kicks(turns):
    """Eventos de chute: (i, side, num, v0, pos, dir).

    Chute = o portador solta a bola e ela ganha velocidade. Conduzir mantém a
    bola a ~100 d/f (a velocidade do jogador), logo v0 > 130 já é chute.
    """
    kicks = []
    for i in range(len(turns) - 1):
        a, b = turns[i], turns[i + 1]
        if a["holder"] is None:
            continue
        if b["holder"] is not None and b["holder"] == a["holder"]:
            continue
        gained = b["speed"] - a["speed"]
        if b["speed"] >= 130 and (gained >= 30 or b["holder"] is None):
            if gained < 5 and b["speed"] < 150:
                continue
            kicks.append(dict(i=i + 1, side=a["holder"][0], num=a["holder"][1],
                              v0=b["speed"], pos=b["ball"], dir=b["dir"]))
    return kicks


def classify_kick(k, turns, our_goal_x_of_side):
    """'chute' | 'passe' | 'outro' — e a que ponto do gol miraria."""
    side = k["side"]
    gx = our_goal_x_of_side[side]        # gol que ESTE lado ataca
    px, py = k["pos"]
    dx, dy = k["dir"]
    rng = ball_range(k["v0"])

    on_goal = False
    if (gx - px) * dx > 0:               # indo na direção do gol atacado
        t = (gx - px) / dx if dx != 0 else math.inf
        if t != math.inf and t <= rng + 250:
            y_at = py + dy * t
            if GOAL_MIN_Y - 100 <= y_at <= GOAL_MAX_Y + 100:
                on_goal = True
    if on_goal:
        return "chute"

    # passe: algum companheiro na linha do chute, dentro do alcance
    T = turns[k["i"]]
    mates = [(num, p) for num, p in T["players"][side].items()
             if num != k["num"]]
    end = (px + dx * rng, py + dy * rng)
    for num, p in mates:
        if seg_point_dist((px, py), end, p) <= 900 and dist((px, py), p) <= rng + 600:
            return "passe"
    return "outro"


# --------------------------------------------------------------------- mapa
def region(pos, attack_x):
    """(terço em x na direção do ataque, faixa em y)."""
    x, y = pos
    adv = x / MAX_X if attack_x == MAX_X else 1 - x / MAX_X
    tx = "def" if adv < 1 / 3 else ("meio" if adv < 2 / 3 else "ataque")
    ty = "alto" if y < GOAL_MIN_Y else ("central" if y <= GOAL_MAX_Y else "baixo")
    return tx, ty


# ---------------------------------------------------------------- análise
def analyze(path, our_side, label):
    turns, goals = load_turns(path)
    n = len(turns)
    their_side = "AWAY" if our_side == "HOME" else "HOME"
    attack_x = {"HOME": MAX_X, "AWAY": 0}
    our_attack_x = attack_x[our_side]

    kicks = detect_kicks(turns)
    for k in kicks:
        k["tipo"] = classify_kick(k, turns, attack_x)
    kicks_by_i = defaultdict(list)
    for k in kicks:
        kicks_by_i[k["i"]].append(k)

    poss = segment_possessions(turns)

    # tempo de bola solta / posse (por turno)
    hold_count = Counter()
    for T in turns:
        h = T["holder"]
        hold_count[h[0] if h else "LOOSE"] += 1

    # quem está mais perto da bola quando ela está solta
    near = Counter()
    for T in turns:
        if T["holder"] is not None:
            continue
        b = T["ball"]
        do = min((dist(b, p) for p in T["players"][our_side].values()),
                 default=1e9)
        dt = min((dist(b, p) for p in T["players"][their_side].values()),
                 default=1e9)
        near["nosso" if do < dt else "deles"] += 1

    # shot clock: expira quando remaining chega a <=2 e reseta com o mesmo lado
    sc_exp = Counter()
    sc_min = {"HOME": 999, "AWAY": 999}
    prev = None
    for T in turns:
        s, r = T["sc"]
        if r is None:
            prev = None
            continue
        sc_min[s] = min(sc_min[s], r)
        if prev and prev[0] == s and prev[1] <= 3 and r > 200:
            sc_exp[s] += 1
        prev = (s, r)

    goal_turns = {side: [t for sd, t in goals if sd == side]
                  for side in ("HOME", "AWAY")}

    # -------- percorre as posses
    recs = []
    for p in poss:
        i0, i1, iend = p["i0"], p["i1"], p["iend"]
        side = p["side"]
        gx = attack_x[side]
        segment = turns[i0:i1 + 1]
        b0 = turns[i0]["ball"]
        b1 = turns[i1]["ball"]

        def adv(pos):
            return pos[0] if gx == MAX_X else MAX_X - pos[0]

        best = max(adv(T["ball"]) for T in segment)
        ks = [k for k in kicks if i0 <= k["i"] <= min(i1 + 4, n - 1)
              and k["side"] == side]
        shots = [k for k in ks if k["tipo"] == "chute"]
        last_k = ks[-1] if ks else None

        # gol nesta posse?
        t0, t1 = turns[i0]["turn"], turns[min(i1 + 6, n - 1)]["turn"]
        scored = any(t0 <= gt <= t1 for gt in goal_turns[side])

        # causa do fim
        if scored:
            causa = "GOL"
        elif i1 >= n - 2:
            causa = "fim de jogo"
        else:
            # shot clock estourou dentro da posse?
            sc_hit = any(turns[j]["sc"][0] == side and
                         (turns[j]["sc"][1] or 999) <= 3
                         for j in range(i0, min(i1 + 2, n)))
            gap = iend - i1              # turnos de bola solta antes da virada
            if sc_hit:
                causa = "shot clock"
            elif last_k is not None and last_k["i"] >= i1 - 2 and gap >= 1:
                causa = {"chute": "chute perdido/bloqueado",
                         "passe": "passe interceptado",
                         "outro": "chutão perdido"}[last_k["tipo"]]
            elif gap <= 1:
                causa = "conducao tomada"
            else:
                causa = "bola solta perdida"

        recs.append(dict(
            side=side, i0=i0, i1=i1,
            dur=turns[i1]["turn"] - turns[i0]["turn"] + 1,
            x0=adv(b0), x1=adv(b1), xbest=best,
            ganho=adv(b1) - adv(b0), ganho_max=best - adv(b0),
            n_kicks=len(ks), n_shots=len(shots),
            ends_shot=bool(shots and shots[-1]["i"] >= i1 - 3),
            causa=causa,
            reg=region(b1, gx),
            reg_start=region(b0, gx),
        ))

    return dict(label=label, path=path, our=our_side, their=their_side,
                turns=n, hold=hold_count, near=near, sc_exp=sc_exp,
                sc_min=sc_min, kicks=kicks, poss=recs, goals=goals)


# ------------------------------------------------------------------ relato
def pct(a, b):
    return 100.0 * a / b if b else 0.0


def report(R):
    our, their = R["our"], R["their"]
    n = R["turns"]
    ours = [p for p in R["poss"] if p["side"] == our]
    theirs = [p for p in R["poss"] if p["side"] == their]
    ok = R["kicks"]
    our_k = [k for k in ok if k["side"] == our]
    gf = len([1 for s, _ in R["goals"] if s == our])
    ga = len([1 for s, _ in R["goals"] if s == their])

    print("=" * 78)
    print(f"{R['label']}   ({os.path.basename(R['path'])})  placar {gf}x{ga}")
    print("=" * 78)
    print(f"turnos: {n} | bola SOLTA em {R['hold']['LOOSE']} turnos "
          f"({pct(R['hold']['LOOSE'], n):.0f}%) | com o portador nosso "
          f"{pct(R['hold'][our], n):.0f}% | deles {pct(R['hold'][their], n):.0f}%")
    tot_near = sum(R["near"].values())
    print(f"  bola solta: jogador MAIS PRÓXIMO é nosso em "
          f"{pct(R['near']['nosso'], tot_near):.0f}% desses turnos")

    kt = Counter(k["tipo"] for k in our_k)
    print(f"\nchutes emitidos por nós: {len(our_k)}  "
          f"(finalizações a gol {kt['chute']}, passes {kt['passe']}, "
          f"outros {kt['outro']})   -> conversão real "
          f"{pct(gf, max(1, kt['chute'])):.0f}% ({gf}/{kt['chute']})")

    def blk(ps, tag):
        if not ps:
            return
        durs = sorted(p["dur"] for p in ps)
        gan = sorted(p["ganho_max"] for p in ps)
        med = lambda L: L[len(L) // 2]
        with_shot = [p for p in ps if p["n_shots"] > 0]
        print(f"\n{tag}: {len(ps)} posses | duração média "
              f"{sum(durs)/len(durs):.1f} turnos (mediana {med(durs)}) | "
              f"avanço máx médio {sum(gan)/len(gan):+.0f}d "
              f"(mediana {med(gan):+.0f})")
        print(f"  posses com >=1 finalização: {len(with_shot)} "
              f"({pct(len(with_shot), len(ps)):.0f}%) | "
              f"posses >= 20 turnos: {sum(1 for p in ps if p['dur']>=20)} "
              f"({pct(sum(1 for p in ps if p['dur']>=20), len(ps)):.0f}%) | "
              f"posses <= 3 turnos: {sum(1 for p in ps if p['dur']<=3)} "
              f"({pct(sum(1 for p in ps if p['dur']<=3), len(ps)):.0f}%)")
        c = Counter(p["causa"] for p in ps)
        print("  como terminam:")
        for k, v in c.most_common():
            print(f"    {k:<26} {v:>4}  {pct(v, len(ps)):>5.1f}%")

    blk(ours, "NOSSAS POSSES")
    blk(theirs, "POSSES DELES")

    # mapa de perdas nossas
    perdas = [p for p in ours if p["causa"] not in ("GOL", "fim de jogo")]
    print(f"\nMAPA DE PERDAS (onde a bola foi perdida) — {len(perdas)} perdas")
    grid = defaultdict(int)
    for p in perdas:
        grid[p["reg"]] += 1
    print(f"  {'':<8}" + "".join(f"{ty:>10}" for ty in ("alto", "central", "baixo")))
    for tx in ("def", "meio", "ataque"):
        row = "".join(f"{grid[(tx, ty)]:>4} ({pct(grid[(tx,ty)], len(perdas)):>3.0f}%)"
                      for ty in ("alto", "central", "baixo"))
        print(f"  {tx:<8}" + row)

    # causa x terço
    print("\n  causa por terço do campo:")
    cz = defaultdict(Counter)
    for p in perdas:
        cz[p["reg"][0]][p["causa"]] += 1
    causas = sorted({c for z in cz.values() for c in z})
    print(f"    {'causa':<26}" + "".join(f"{z:>9}" for z in ("def", "meio", "ataque")))
    for c in causas:
        print(f"    {c:<26}" + "".join(f"{cz[z][c]:>9}" for z in ("def", "meio", "ataque")))

    print(f"\nshot clock: expirou contra NÓS {R['sc_exp'][our]}x, "
          f"contra ELES {R['sc_exp'][their]}x "
          f"(mínimo de turnos restantes visto: nosso {R['sc_min'][our]}, "
          f"deles {R['sc_min'][their]})")
    print()
    return dict(label=R["label"], gf=gf, ga=ga,
                loose=pct(R["hold"]["LOOSE"], n),
                poss_ours=len(ours), poss_theirs=len(theirs),
                dur=sum(p["dur"] for p in ours) / max(1, len(ours)),
                gan=sum(p["ganho_max"] for p in ours) / max(1, len(ours)),
                shots=kt["chute"], passes=kt["passe"],
                with_shot=pct(sum(1 for p in ours if p["n_shots"] > 0),
                              max(1, len(ours))),
                sc_exp=R["sc_exp"][our],
                causas=Counter(p["causa"] for p in ours))


if __name__ == "__main__":
    sel = sys.argv[1:]
    rows = []
    for fn, side, label in MATCHES:
        if sel and not any(s in fn for s in sel):
            continue
        path = os.path.join(REC, fn)
        if not os.path.exists(path):
            print(f"(faltando {fn})")
            continue
        rows.append(report(analyze(path, side, label)))

    print("=" * 110)
    print("RESUMO")
    print("=" * 110)
    hdr = (f"{'partida':<32}{'gols':>5}{'solta%':>8}{'posses':>8}{'dur':>7}"
           f"{'avanço':>8}{'final.':>8}{'passes':>8}{'%c/fin':>8}{'SC':>4}")
    print(hdr)
    for r in rows:
        print(f"{r['label']:<32}{r['gf']:>3}x{r['ga']:<1}{r['loose']:>8.0f}"
              f"{r['poss_ours']:>8}{r['dur']:>7.1f}{r['gan']:>+8.0f}"
              f"{r['shots']:>8}{r['passes']:>8}{r['with_shot']:>8.0f}"
              f"{r['sc_exp']:>4}")

    print("\nCAUSAS DE FIM DAS NOSSAS POSSES (agregado, % por partida)")
    allc = sorted({c for r in rows for c in r["causas"]})
    print(f"{'partida':<32}" + "".join(f"{c[:11]:>13}" for c in allc))
    for r in rows:
        tot = sum(r["causas"].values())
        print(f"{r['label']:<32}" +
              "".join(f"{100*r['causas'][c]/tot:>12.0f}%" for c in allc))
