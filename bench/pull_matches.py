#!/usr/bin/env python3
"""Puxa DADOS + STATS + VÍDEOS das partidas do nosso bot na plataforma.

Versão do worktree (régua nova): além de placares (scraping do perfil, reusa
analysis/scrape_profiles) e vídeos MP4, anexa as 12 STATS POR PARTIDA da página
/matches/<id>/watch (posse bruta/líquida, finalizações, passes, defesas do GK,
roubadas — bot_*/adv_*). É o insumo do maximin da promoção por plataforma.

Uso: python3 bench/pull_matches.py [handle] [--no-stats] [--no-video]
     (default: killua-zoldyck)
Escreve results/<handle>_matches.csv (DO WORKTREE) e baixa vídeos em videos/.
"""
import argparse
import csv
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import scrape_profiles as sp  # noqa: E402

VIDEO = "https://storage.googleapis.com/lugobots-prod-videos/{}.mp4"
UA = "Mozilla/5.0 (compatible; lugo-analysis/1.0)"
STAT_COLS = ([f"bot_{k}" for k in sp.STAT_KEYS.values()]
             + [f"adv_{k}" for k in sp.STAT_KEYS.values()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("handle", nargs="?", default="killua-zoldyck")
    ap.add_argument("--no-stats", action="store_true")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()

    h = a.handle
    rows = sp.scrape(h)
    viddir = os.path.join(ROOT, "videos")
    os.makedirs(viddir, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)

    out, rec, new = [], {"V": 0, "D": 0, "E": 0}, 0
    for r in rows:
        if h not in (r["home_h"], r["away_h"]):
            continue
        opp, _opp_n, pro, contra, mando = sp.perspective(h, r)
        res = sp.outcome(pro, contra)
        rec[res] += 1
        mid = r["mid"] or ""
        row = dict(adversario=opp, placar=f"{pro}-{contra}", resultado=res,
                   mando=mando, data=r["date"], match_id=mid,
                   video=VIDEO.format(mid) if mid else "")
        if not a.no_stats and mid:
            row.update(sp.match_stats_for(h, r))
        out.append(row)
        if mid and not a.no_video:
            dest = os.path.join(viddir, f"{opp}_{mid}.mp4")
            if not os.path.exists(dest):
                try:
                    req = urllib.request.Request(row["video"],
                                                 headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=180) as resp, \
                            open(dest, "wb") as f:
                        f.write(resp.read())
                    new += 1
                    print(f"  baixado {os.path.basename(dest)}")
                except Exception as e:
                    print(f"  falha no vídeo {mid}: {e}", file=sys.stderr)

    csvp = os.path.join(ROOT, "results", f"{h}_matches.csv")
    cols = (["adversario", "placar", "resultado", "mando", "data",
             "match_id", "video"] + STAT_COLS)
    with open(csvp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print(f"\n{h}: {rec['V']}V-{rec['E']}E-{rec['D']}D  ({len(out)} partidas) | "
          f"{new} vídeos novos")
    print(f"CSV: {csvp}\nvídeos: {viddir}/")


if __name__ == "__main__":
    main()
