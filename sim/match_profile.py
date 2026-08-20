#!/usr/bin/env python3
"""PERFIL MACRO de uma partida a partir do vídeo da plataforma.

Não reconstrói o lance (isso é o scene_extract): mede a GEOGRAFIA do jogo —
onde a bola vive, quantos corpos cada time mantém em cada terço, e quem está
perto da bola. É o instrumento para comparar o NOSSO desenho com o dos bots
que fazem 6–11 gols no level-3 (o desempate do seeding).

Uso: python3 sim/match_profile.py <video.mp4> [--fps 4] [--out perfil.json]
Convenção: HOME (anel azul-marinho) ataca para a DIREITA (x→20000).
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene_extract as SE


def profile(video, sample_fps=4.0, t0=0.0, t1=None):
    step = max(1, int(round(SE.FPS / sample_fps)))
    frames = SE.read_frames(video, t0, t1 if t1 else 1e9)
    cal = None
    rows = []
    for i, fr in enumerate(frames):
        if i % step:
            continue
        if cal is None:
            cal = SE.calibrate(fr)
        homes, aways, balls, frac_cyan, _all = SE.detect(fr, cal)
        if frac_cyan < 0.35:          # animação de gol cobrindo o campo
            rows.append({"t": i / SE.FPS, "anim": True})
            continue
        H = [SE.px_to_field(cal, x, y) for x, y in homes]
        A = [SE.px_to_field(cal, x, y) for x, y in aways]
        B = [SE.px_to_field(cal, x, y) for x, y in balls]
        rows.append({"t": i / SE.FPS, "home": H, "away": A, "ball": B})
    return {"video": os.path.basename(video), "cal": list(cal or []),
            "sample_fps": sample_fps, "rows": rows}


def ball_track(rows):
    """Escolhe 1 bola por frame por continuidade (candidato mais próximo do
    anterior; sem candidato = herda)."""
    prev = None
    out = []
    for r in rows:
        if r.get("anim") or not r.get("ball"):
            out.append(prev)
            continue
        if prev is None:
            b = min(r["ball"], key=lambda p: abs(p[0] - 10000) + abs(p[1] - 5000))
        else:
            b = min(r["ball"], key=lambda p: (p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2)
            if (b[0] - prev[0]) ** 2 + (b[1] - prev[1]) ** 2 > 2500 ** 2:
                b = prev
        out.append(b)
        prev = b
    return out


def summarize(prof, label=""):
    rows = prof["rows"]
    bt = ball_track(rows)
    T3 = 20000.0 / 3
    n = 0
    ball_third = [0, 0, 0]
    home_att, away_def = [], []
    home_att_when_att = []
    near_home, near_away = [], []
    for r, b in zip(rows, bt):
        if r.get("anim") or b is None:
            continue
        n += 1
        k = 0 if b[0] < T3 else (1 if b[0] < 2 * T3 else 2)
        ball_third[k] += 1
        H = r.get("home") or []
        A = r.get("away") or []
        nh = sum(1 for p in H if p[0] > 2 * T3)
        na = sum(1 for p in A if p[0] < T3)
        home_att.append(nh)
        away_def.append(na)
        if k == 2:
            home_att_when_att.append(nh)
        if H:
            near_home.append(min(np.hypot(p[0] - b[0], p[1] - b[1]) for p in H))
        if A:
            near_away.append(min(np.hypot(p[0] - b[0], p[1] - b[1]) for p in A))
    f = lambda v: (float(np.mean(v)) if v else 0.0)
    print(f"--- {label or prof['video']} ({n} amostras) ---")
    print(f"  bola por terço: def {100*ball_third[0]/max(1,n):4.1f}% | "
          f"meio {100*ball_third[1]/max(1,n):4.1f}% | ATAQUE {100*ball_third[2]/max(1,n):4.1f}%")
    print(f"  corpos HOME no terço de ataque: media {f(home_att):.2f} "
          f"(quando a bola LA: {f(home_att_when_att):.2f})")
    print(f"  corpos AWAY no terco defensivo deles: media {f(away_def):.2f}")
    print(f"  dist. do mais proximo da bola: HOME {f(near_home):5.0f} | AWAY {f(near_away):5.0f}")
    return dict(n=n, ball_third=[x / max(1, n) for x in ball_third],
                home_att=f(home_att), home_att_when_att=f(home_att_when_att),
                away_def=f(away_def), near_home=f(near_home), near_away=f(near_away))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--out")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    prof = profile(a.video, a.fps)
    if a.out:
        json.dump(prof, open(a.out, "w"))
    summarize(prof, a.label or a.video)


if __name__ == "__main__":
    main()
