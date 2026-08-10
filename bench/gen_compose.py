#!/usr/bin/env python3
"""Gera o docker-compose da bancada: servidor + 11 bots por time.

Cada bot precisa de BOT_NUMBER único (1-11), então não dá para usar `replicas`.

Uso:
  python3 gen_compose.py --home lugobots/the-dummies-go:latest \
                         --away lugobots/the-dummies-go:latest \
                         --out docker-compose.yml
"""
import argparse

TPL_HEADER = """name: lugo-bench

services:
  server:
    image: lugobots/server:latest
    command: >
      play
      --dev-mode
      --timer-mode={timer_mode}
      --record-path=/recordings/{match_id}.json
      {extra}
    ports:
      - "5000:5000"
      - "8080:8080"
    volumes:
      - ./recordings:/recordings
    networks: [lugo]
"""

# Sem `restart: on-failure`: quando a partida acaba e o servidor sai, os 22
# bots reiniciariam em loop, consumindo CPU e travando o `down` da próxima
# partida. Os bots já esperam a porta do servidor ativamente (main.py), então
# a política de restart não é mais necessária.
TPL_BOT = """
  {team}_{num:02d}:
    image: {image}
    depends_on: [server]
    environment:
      - BOT_TEAM={team}
      - BOT_NUMBER={num}
      - BOT_GRPC_URL=server:5000
      - BOT_PARAMS=${{{team_upper}_PARAMS:-}}
    networks: [lugo]
"""

TPL_FOOTER = """
networks:
  lugo:
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="lugobots/the-dummies-go:latest")
    ap.add_argument("--away", default="lugobots/the-dummies-go:latest")
    ap.add_argument("--timer-mode", default="rush",
                    choices=["wait", "rush", "remote"])
    ap.add_argument("--match-id", default="match")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--out", default="docker-compose.yml")
    a = ap.parse_args()

    extra = []
    if a.headless:
        extra.append("--headless")
    if a.quiet:
        extra.append("--quiet")

    parts = [TPL_HEADER.format(timer_mode=a.timer_mode, match_id=a.match_id,
                               extra="\n      ".join(extra))]
    for num in range(1, 12):
        parts.append(TPL_BOT.format(team="home", team_upper="HOME", num=num, image=a.home))
    for num in range(1, 12):
        parts.append(TPL_BOT.format(team="away", team_upper="AWAY", num=num, image=a.away))
    parts.append(TPL_FOOTER)

    with open(a.out, "w") as f:
        f.write("".join(parts))
    print(f"escrito {a.out}: home={a.home} away={a.away} timer={a.timer_mode}")


if __name__ == "__main__":
    main()
