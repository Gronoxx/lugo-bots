"""
Parser dos replays do servidor Lugo.

Formato: uma linha por evento, cada linha = base64(gzip(json)).
  linha 0: {"date": ...}
  linha 1: configuração da partida (game_duration, listening_mode, times)
  linha 2+: {"game_snapshot": {...}, "state_change"|"orders"|...}

O JSON vem da serialização protobuf, logo CAMPOS COM VALOR DEFAULT SÃO
OMITIDOS (x=0, side=HOME, score=0 não aparecem). Todo acesso usa .get().
"""

import base64
import gzip
import json
from dataclasses import dataclass, field


def decode_line(line: str) -> dict:
    return json.loads(gzip.decompress(base64.b64decode(line)).decode())


def load(path: str):
    """Retorna (config, [eventos])."""
    with open(path) as f:
        lines = [ln for ln in f.read().strip().split("\n") if ln]
    events = [decode_line(ln) for ln in lines]
    config = next((e for e in events if "protocol_version" in e), {})
    return config, events


def snapshots(events):
    """Itera os game_snapshots do replay."""
    for e in events:
        gs = e.get("game_snapshot")
        if gs:
            yield gs


# ---------- acessores tolerantes a campos omitidos ----------

def pt(p):
    p = p or {}
    return (p.get("x", 0), p.get("y", 0))


def team(gs, side):
    return gs.get(f"{side}_team", {}) or {}


def score(gs, side):
    return team(gs, side).get("score", 0)


def players(gs, side):
    return team(gs, side).get("players", []) or []


def ball(gs):
    return gs.get("ball", {}) or {}


def ball_pos(gs):
    return pt(ball(gs).get("position"))


def ball_speed(gs):
    return (ball(gs).get("velocity", {}) or {}).get("speed", 0)


def holder(gs):
    """Retorna (side, number) de quem tem a bola, ou None."""
    h = ball(gs).get("holder")
    if not h:
        return None
    return (h.get("team_side", "HOME"), h.get("number", 0))


@dataclass
class MatchStats:
    turns: int = 0
    n_snapshots: int = 0
    goals_home: int = 0
    goals_away: int = 0
    possession_home: int = 0
    possession_away: int = 0
    loose: int = 0
    goal_turns: list = field(default_factory=list)
    max_ball_speed: float = 0.0
    ball_x_sum: float = 0.0
    shot_clock_expiries: int = 0

    @property
    def possession_pct_home(self):
        tot = self.possession_home + self.possession_away
        return 100 * self.possession_home / tot if tot else 0

    @property
    def avg_ball_x(self):
        # médias são por snapshot, não por turno (há vários snapshots/turno)
        return self.ball_x_sum / self.n_snapshots if self.n_snapshots else 0


def analyze(path: str) -> tuple[MatchStats, dict]:
    config, events = load(path)
    st = MatchStats()
    prev_h = prev_a = 0
    prev_shot_side = None
    prev_shot_remaining = None

    for gs in snapshots(events):
        st.turns = max(st.turns, gs.get("turn", 0))
        st.n_snapshots += 1
        h, a = score(gs, "home"), score(gs, "away")
        if h > prev_h:
            st.goal_turns.append(("HOME", gs.get("turn", 0)))
        if a > prev_a:
            st.goal_turns.append(("AWAY", gs.get("turn", 0)))
        prev_h, prev_a = h, a
        st.goals_home, st.goals_away = h, a

        hold = holder(gs)
        if hold is None:
            st.loose += 1
        elif hold[0] == "AWAY":
            st.possession_away += 1
        else:
            st.possession_home += 1

        st.max_ball_speed = max(st.max_ball_speed, ball_speed(gs))
        st.ball_x_sum += ball_pos(gs)[0]

        sc = gs.get("shot_clock") or {}
        rem = sc.get("remaining_turns")
        side = sc.get("team_side", "HOME")
        if prev_shot_remaining is not None and prev_shot_side == side \
                and rem is not None and prev_shot_remaining <= 1 and rem > 100:
            st.shot_clock_expiries += 1
        prev_shot_remaining, prev_shot_side = rem, side

    return st, config


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "../bench/recordings/dummies_vs_dummies.json"
    st, cfg = analyze(path)
    print(f"=== {path} ===")
    print(f"config: duração={cfg.get('game_duration')} turnos, "
          f"modo={cfg.get('listening_mode')}, dev={cfg.get('dev_mode')}")
    print(f"placar: HOME {st.goals_home} x {st.goals_away} AWAY  ({st.turns} turnos)")
    print(f"gols: {st.goal_turns}")
    print(f"posse: HOME {st.possession_pct_home:.1f}%  "
          f"(bola solta em {100*st.loose/max(1,st.turns):.0f}% dos turnos)")
    print(f"velocidade máx da bola observada: {st.max_ball_speed:.0f} d/f")
    print(f"posição média da bola em x: {st.avg_ball_x:.0f} (campo 0..20000)")
