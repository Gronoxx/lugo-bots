#!/usr/bin/env python3
"""
FRENTE 2e — agregado das 6 partidas nossas contra os dummies + contexto da
perda + portão do PASSE.

Junta as partidas em que jogamos contra os dummies (v1, v2, v3 x3, v6) e
imprime, sobre a soma delas:
  - mapa de perdas 3x3, causas, região de início x região de fim;
  - contexto da perda: há quantos turnos o adversário estava colado no
    portador; quantos turnos o portador conduzia;
  - quantos companheiros passam no teste opponent_can_intercept (portão do
    passe) e quantos passariam ignorando os pontos junto ao passador.
"""
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frente2_possession import (REC, MAX_X, GOAL_MIN_Y, GOAL_MAX_Y, load_turns,
                                detect_kicks, classify_kick,
                                segment_possessions, dist, region, pct)
from frente2c_gate import (blocking_opponent, turns_for_ball, turns_for_player,
                           GOALKEEPER)
from frente2d_gols import _blocked

VS_DUMMIES = [
    ("t1.json", "HOME", "v1"),
    ("eval_0_norm.json", "HOME", "v2"),
    ("var_1.json", "HOME", "v3a"),
    ("var_2.json", "HOME", "v3b"),
    ("swap.json", "AWAY", "v3-away"),
    ("v6_check.json", "HOME", "v6"),
]
SAMPLE = 3          # avalia o portão do passe a cada N turnos com bola nossa


def speed_for_distance(d):
    lo, hi = 2.0, 400.0
    def rng(v0):
        dd, v = 0.0, v0
        while v > 2:
            dd += v - 5
            v -= 10
        return dd
    if rng(400.0) < d:
        return 400.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if rng(mid) < d:
            lo = mid
        else:
            hi = mid
    return hi


def main():
    G = dict(loss_map=Counter(), causes=Counter(), start_end=Counter(),
             poss=0, reach=0, shot_poss=0, dur=[], gain=[], marked=[],
             carry=[], pass_open=Counter(), pass_tot=0, loose_rec=Counter(),
             maxadv=[], first_third=Counter())
    per = []
    for fn, side, tag in VS_DUMMIES:
        path = os.path.join(REC, fn)
        turns, goals = load_turns(path)
        their = "AWAY" if side == "HOME" else "HOME"
        gx = MAX_X if side == "HOME" else 0
        goal_c = (gx, 5000)
        kicks = detect_kicks(turns)
        for k in kicks:
            k["tipo"] = classify_kick(k, turns, {"HOME": MAX_X, "AWAY": 0})
        shot_i = {k["i"] for k in kicks
                  if k["side"] == side and k["tipo"] == "chute"}
        poss = [p for p in segment_possessions(turns) if p["side"] == side]
        gt = [t for s, t in goals if s == side]
        idx = {T["turn"]: i for i, T in enumerate(turns)}

        for p in poss:
            i0, i1 = p["i0"], p["i1"]
            seg = turns[i0:i1 + 1]
            adv = lambda q: q[0] if gx == MAX_X else MAX_X - q[0]
            G["poss"] += 1
            G["dur"].append(turns[i1]["turn"] - turns[i0]["turn"] + 1)
            G["maxadv"].append(max(adv(T["ball"]) for T in seg) - adv(turns[i0]["ball"]))
            zt = sum(1 for T in seg if T["holder"] and T["holder"][0] == side
                     and dist(T["ball"], goal_c) <= 6000)
            if zt:
                G["reach"] += 1
            if any(i0 <= i <= i1 + 4 for i in shot_i):
                G["shot_poss"] += 1
            r0 = region(turns[i0]["ball"], gx)
            r1 = region(turns[i1]["ball"], gx)
            scored = any(turns[i0]["turn"] <= t <= turns[min(i1 + 6, len(turns) - 1)]["turn"]
                         for t in gt)
            if not scored:
                G["loss_map"][r1] += 1
                G["start_end"][(r0[0], r1[0])] += 1
                # contexto: há quantos turnos o adversário está colado?
                T1 = turns[i1]
                h = T1["holder"]
                me = T1["players"][side].get(h[1]) if h else T1["ball"]
                dmin = min((dist(me, q) for q in T1["players"][their].values()),
                           default=1e9)
                G["marked"].append(dmin)
                # há quantos turnos o mesmo jogador conduzia
                c = 0
                for j in range(i1, i0 - 1, -1):
                    hh = turns[j]["holder"]
                    if hh and hh == h:
                        c += 1
                    else:
                        break
                G["carry"].append(c)
            G["first_third"][r0[0]] += 1

        # portão do passe
        for n_, T in enumerate(turns):
            if n_ % SAMPLE:
                continue
            h = T["holder"]
            if not h or h[0] != side:
                continue
            me = T["players"][side].get(h[1])
            if me is None:
                continue
            opps = list(T["players"][their].values())
            mates = [(num, q) for num, q in T["players"][side].items()
                     if num != h[1] and num != GOALKEEPER]
            G["pass_tot"] += 1
            n_ok = n_okA = 0
            for num, q in mates:
                d = dist(me, q)
                if d < 800 or d > 8000:
                    continue
                sp = min(400.0, speed_for_distance(d) * 1.25)
                b, _, _ = blocking_opponent(me, q, opps, sp)
                if not b:
                    n_ok += 1
                if not _blocked(me, q, opps, "A"):
                    n_okA += 1
            G["pass_open"]["algum"] += 1 if n_ok else 0
            G["pass_open"]["algumA"] += 1 if n_okA else 0
            G["pass_open"]["n"] += n_ok
            G["pass_open"]["nA"] += n_okA

        # recuperação de bola solta
        cur = None
        for T in turns:
            h = T["holder"]
            if h is None:
                if cur is None:
                    cur = "start"
            else:
                if cur == "start":
                    G["loose_rec"][h[0]] += 1
                cur = None
        per.append((tag, len(poss)))

    print("=" * 78)
    print("AGREGADO — 6 partidas nossas contra os dummies")
    print("=" * 78)
    print("posses por partida:", ", ".join(f"{t}={n}" for t, n in per))
    d = sorted(G["dur"])
    a = sorted(G["maxadv"])
    print(f"\nposses nossas no total: {G['poss']} | duração média "
          f"{sum(d)/len(d):.1f} turnos (mediana {d[len(d)//2]}) | "
          f"avanço máximo médio {sum(a)/len(a):+.0f}d (mediana {a[len(a)//2]:+.0f})")
    print(f"chegaram a <=6000d do gol: {G['reach']} "
          f"({pct(G['reach'], G['poss']):.0f}%) | "
          f"produziram >=1 finalização: {G['shot_poss']} "
          f"({pct(G['shot_poss'], G['poss']):.0f}%)")
    print(f"  -> {G['poss'] - G['shot_poss']} posses "
          f"({pct(G['poss']-G['shot_poss'], G['poss']):.0f}%) morrem sem "
          f"nenhum chute a gol")

    tot = sum(G["loss_map"].values())
    print(f"\nMAPA DE PERDAS ({tot} perdas)  linhas = terço em x, "
          f"colunas = faixa em y")
    print(f"  {'':<9}" + "".join(f"{c:>12}" for c in ("alto(<3500)", "central", "baixo(>6500)")))
    for tx in ("def", "meio", "ataque"):
        print(f"  {tx:<9}" + "".join(
            f"{G['loss_map'][(tx,ty)]:>5} ({pct(G['loss_map'][(tx,ty)],tot):>3.0f}%)"
            for ty in ("alto", "central", "baixo")))
    print("  por terço:  " + "  ".join(
        f"{tx}={sum(G['loss_map'][(tx,ty)] for ty in ('alto','central','baixo'))}"
        f" ({pct(sum(G['loss_map'][(tx,ty)] for ty in ('alto','central','baixo')),tot):.0f}%)"
        for tx in ("def", "meio", "ataque")))

    print("\nonde a posse COMEÇA -> onde ela MORRE (terço):")
    for r0 in ("def", "meio", "ataque"):
        row = [G["start_end"][(r0, r1)] for r1 in ("def", "meio", "ataque")]
        if sum(row):
            print(f"  começa em {r0:<7} -> " + "  ".join(
                f"{r1}:{v} ({pct(v,sum(row)):.0f}%)"
                for r1, v in zip(("def", "meio", "ataque"), row)))

    m = sorted(G["marked"])
    c = sorted(G["carry"])
    print(f"\nno instante da perda: adversário mais próximo do nosso portador "
          f"a mediana {m[len(m)//2]:.0f}d "
          f"(p25={m[len(m)//4]:.0f}, p75={m[3*len(m)//4]:.0f}); "
          f"{pct(sum(1 for x in m if x <= 600), len(m)):.0f}% a <=600d (contato)")
    print(f"  o portador conduzia havia mediana {c[len(c)//2]} turnos "
          f"(média {sum(c)/len(c):.1f}, p90={c[int(0.9*len(c))]})")

    pt_ = G["pass_tot"]
    print(f"\nPORTÃO DO PASSE ({pt_} turnos amostrados com a bola nossa):")
    print(f"  regra atual  (opponent_can_intercept): existe >=1 companheiro "
          f"liberado em {G['pass_open']['algum']} turnos "
          f"({pct(G['pass_open']['algum'], pt_):.0f}%) | "
          f"média {G['pass_open']['n']/pt_:.2f} opções por turno")
    print(f"  ignorando os 2 pontos junto ao passador: "
          f"{G['pass_open']['algumA']} turnos "
          f"({pct(G['pass_open']['algumA'], pt_):.0f}%) | "
          f"média {G['pass_open']['nA']/pt_:.2f} opções por turno")

    lr = G["loose_rec"]
    print(f"\nbolas soltas: {sum(lr.values())} sequências; "
          + ", ".join(f"{k}={v} ({pct(v,sum(lr.values())):.0f}%)"
                      for k, v in lr.most_common()))


if __name__ == "__main__":
    main()
