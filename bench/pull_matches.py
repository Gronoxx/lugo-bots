#!/usr/bin/env python3
"""Puxa DADOS + REPLAYS (vídeos) das partidas do nosso bot na plataforma.

A plataforma NÃO expõe o replay JSON (só o vídeo MP4 em
storage.googleapis.com/lugobots-prod-videos/<match_id>.mp4). Então:
  - dados/placares vêm por scraping do perfil (reusa analysis/scrape_profiles);
  - replay = vídeo MP4, baixado por match_id.

Uso: python3 bench/pull_matches.py [handle]        # default: patrick-estrela
Escreve results/<handle>_matches.csv e baixa os vídeos novos em videos/.
"""
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


def main():
    h = sys.argv[1] if len(sys.argv) > 1 else "patrick-estrela"
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
        vurl = VIDEO.format(mid) if mid else ""
        out.append(dict(adversario=opp, placar=f"{pro}-{contra}", resultado=res,
                        mando=mando, data=r["date"], match_id=mid, video=vurl))
        if mid:
            dest = os.path.join(viddir, f"{opp}_{mid}.mp4")
            if not os.path.exists(dest):
                try:
                    req = urllib.request.Request(vurl, headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=180) as resp, \
                            open(dest, "wb") as f:
                        f.write(resp.read())
                    new += 1
                    print(f"  baixado {os.path.basename(dest)}")
                except Exception as e:
                    print(f"  falha no vídeo {mid}: {e}", file=sys.stderr)

    csvp = os.path.join(ROOT, "results", f"{h}_matches.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["adversario", "placar", "resultado",
                                          "mando", "data", "match_id", "video"])
        w.writeheader()
        w.writerows(out)
    print(f"\n{h}: {rec['V']}V-{rec['E']}E-{rec['D']}D  ({len(out)} partidas) | "
          f"{new} vídeos novos")
    print(f"CSV: {csvp}\nvídeos: {viddir}/")


if __name__ == "__main__":
    main()
