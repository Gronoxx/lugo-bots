#!/usr/bin/env python3
"""Raspa o histórico de partidas dos perfis públicos em lugobots.ai/bots/<handle>.

Objetivo: medir com que margem os melhores bots batem os adversários oficiais
`level-0..3`, para comparar com a nossa margem (levantar a régua competitiva).

Por que um parser dedicado (o alinhamento é traiçoeiro): a página lista os
placares (`score-value">X – Y`) e os nomes dos bots em elementos separados;
casar por listas paralelas se desloca. Aqui a página é fatiada POR BLOCO de
partida (`<div class="matche-items ">`), e de cada bloco extraímos mandante
(`team--home`), visitante (`team--away`), placar (mandante–visitante), data e
o id da partida. Assim o pareamento nunca desalinha.

Paginação: `?page=N`. Iteramos até uma página não trazer nenhum match_id novo
(dedup por id), então páginas repetidas/vazias encerram naturalmente.

Validado contra caso conhecido: BotAdversario3 (BotAdversario9) = 94V-13D-2E, 109 partidas.

Uso:
  python3 analysis/scrape_profiles.py BotAdversario1 BotAdversario3 BotAdversario9 BotAdversario4 BotAdversario8 \
          --out results/levels_vs_bots.csv
  python3 analysis/scrape_profiles.py BotAdversario3 --expect BotAdversario3=94-13-2   # valida
"""
import argparse
import csv
import html
import re
import sys
import time
import urllib.request
from collections import defaultdict

BASE = "https://lugobots.ai/bots/"
UA = "Mozilla/5.0 (compatible; lugo-analysis/1.0)"
DEFAULT_LEVELS = ["level-0", "level-1", "level-2", "level-3"]


def fetch(handle, page, retries=3):
    url = f"{BASE}{handle}?page={page}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def _team(block, side):
    """(handle, nome) do time `home`/`away` dentro de um bloco de partida."""
    seg = re.search(r'matche-items__team--' + side +
                    r'(.*?)(?=matche-items__team--|matche-items__footer|$)',
                    block, re.S)
    seg = seg.group(1) if seg else ""
    m = re.search(r'/bots/([a-z0-9\-]+)"[^>]*>\s*([^<]+?)\s*</a>', seg)
    if m:
        return m.group(1), html.unescape(m.group(2).strip())
    m = re.search(r'/bots/([a-z0-9\-]+)', seg)
    return (m.group(1) if m else None), None


def parse_page(text):
    """Lista de partidas de uma página (uma por bloco `matche-items`)."""
    starts = [m.start() for m in re.finditer(r'<div class="matche-items ', text)]
    starts.append(len(text))
    out = []
    for i in range(len(starts) - 1):
        b = text[starts[i]:starts[i + 1]]
        hh, hn = _team(b, "home")
        ah, an = _team(b, "away")
        sc = re.search(r'score-value">\s*(\d+)\s*[–\-]\s*(\d+)', b)
        if not sc or not hh or not ah:
            continue
        d = re.search(r'match-time.*?<p[^>]*>(.*?)</p>', b, re.S)
        date = re.sub(r'\s+', ' ', d.group(1)).strip() if d else ""
        mid = re.search(r'/matches/([0-9a-f\-]{36})/watch', b)
        out.append(dict(home_h=hh, home_n=hn, away_h=ah, away_n=an,
                        hg=int(sc.group(1)), ag=int(sc.group(2)),
                        date=date, mid=mid.group(1) if mid else None))
    return out


def _key(r):
    """Chave de dedup: match_id quando existe; senão a partida em si.

    Nem toda partida tem link 'Watch' (as antigas sem replay não têm), então
    não dá para exigir match_id — isso descartaria partidas reais e subcontaria
    o histórico. A tupla home+away+placar+data (com segundos) é única na prática.
    """
    return r["mid"] or (r["home_h"], r["away_h"], r["hg"], r["ag"], r["date"])


def scrape(handle, max_pages=80, delay=0.4):
    """Todas as partidas do perfil, deduplicadas (mid ou chave composta)."""
    seen, rows = set(), []
    for page in range(1, max_pages + 1):
        try:
            page_rows = parse_page(fetch(handle, page))
        except Exception as e:
            print(f"  [{handle} p{page}] ERRO apos retries: {e} "
                  f"(historico pode estar incompleto)", file=sys.stderr)
            break
        new = [r for r in page_rows if _key(r) not in seen]
        for r in new:
            seen.add(_key(r))
        rows.extend(new)
        if not new:
            break
        time.sleep(delay)
    return rows


def perspective(handle, r):
    """Do ponto de vista de `handle`: (adv_handle, adv_nome, gols_pro, gols_contra, mando)."""
    if r["home_h"] == handle:
        return r["away_h"], r["away_n"], r["hg"], r["ag"], "home"
    return r["home_h"], r["home_n"], r["ag"], r["hg"], "away"


def outcome(pro, contra):
    return "V" if pro > contra else ("D" if pro < contra else "E")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("handles", nargs="+")
    ap.add_argument("--out", default="results/levels_vs_bots.csv")
    ap.add_argument("--levels", nargs="+", default=DEFAULT_LEVELS,
                    help="adversários oficiais a manter no CSV")
    ap.add_argument("--expect", action="append", default=[],
                    help="validação handle=V-D-E (ex.: BotAdversario3=94-13-2)")
    ap.add_argument("--delay", type=float, default=0.4)
    a = ap.parse_args()

    expect = {}
    for e in a.expect:
        k, v = e.split("=")
        expect[k] = tuple(int(x) for x in v.split("-"))

    levels = set(a.levels)
    csv_rows = []
    # agregação para o resumo de margens: (bot, level) -> lista de (pro, contra)
    agg = defaultdict(list)

    for handle in a.handles:
        rows = scrape(handle, delay=a.delay)
        rec = {"V": 0, "D": 0, "E": 0}
        kept = 0
        for r in rows:
            if handle not in (r["home_h"], r["away_h"]):
                print(f"  aviso: {handle} ausente do bloco {r['mid']}", file=sys.stderr)
                continue
            opp, opp_n, pro, contra, mando = perspective(handle, r)
            rec[outcome(pro, contra)] += 1
            if opp in levels:
                kept += 1
                agg[(handle, opp)].append((pro, contra))
                csv_rows.append(dict(
                    bot=handle, adversario=opp, adversario_nome=opp_n or "",
                    placar=f"{pro} – {contra}", bot_gols=pro, adv_gols=contra,
                    resultado=outcome(pro, contra), mando=mando,
                    data=r["date"], match_id=r["mid"]))
        tag = ""
        if handle in expect:
            exp = expect[handle]
            got = (rec["V"], rec["D"], rec["E"])
            tag = "  [OK]" if got == exp else f"  [DIVERGE! esperado {exp[0]}V-{exp[1]}D-{exp[2]}E]"
        print(f"{handle}: {len(rows)} partidas  "
              f"{rec['V']}V-{rec['D']}D-{rec['E']}E  "
              f"({kept} vs levels){tag}")

    cols = ["bot", "adversario", "adversario_nome", "placar", "bot_gols",
            "adv_gols", "resultado", "mando", "data", "match_id"]
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(csv_rows, key=lambda x: (x["bot"], x["adversario"], x["data"])))
    print(f"\nescrito {a.out}: {len(csv_rows)} confrontos vs {sorted(levels)}")

    # resumo de margens (o que responde a pergunta do Mac)
    print("\n=== margem média por bot × level (gols pró − contra) ===")
    print(f"{'bot':<14}{'level':<9}{'n':>3}  {'V-D-E':>7}  {'gols pró/contra':>16}  {'margem méd':>10}")
    for (bot, lvl) in sorted(agg):
        games = agg[(bot, lvl)]
        n = len(games)
        v = sum(1 for p, c in games if p > c)
        d = sum(1 for p, c in games if p < c)
        e = n - v - d
        gp = sum(p for p, c in games)
        gc = sum(c for p, c in games)
        margin = (gp - gc) / n
        print(f"{bot:<14}{lvl:<9}{n:>3}  {v}-{d}-{e:>1}  {gp:>7}/{gc:<7}  {margin:>+10.2f}")


if __name__ == "__main__":
    main()
