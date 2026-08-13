"""
Converte um `fastsim.State` num `server_pb2.GameSnapshot` real, para que o
`lugo4py.GameSnapshotInspector` (e portanto o my_bot exato) rode dentro do
simulador em processo — sem gRPC nem Docker.

Templado em bench/latency.py (que já monta um GameSnapshot campo-a-campo).

Convenções (ver results/REFERENCIA_LUGO.md):
- fastsim: pos[side][idx]=(x,y), idx 0..10; número do jogador = idx+1; goleiro idx 0.
- fastsim vel é Cartesiano (vx,vy); o protobuf usa direction (mag 100) + speed.
- holder = (side, idx) ou None; no snapshot, bola livre = SEM campo holder
  (o dispatch usa ball.HasField("holder")).
"""
import math

from lugo4py.protos import server_pb2

MAX_X, MAX_Y = 20000, 10000
_SIDES = (server_pb2.Team.Side.HOME, server_pb2.Team.Side.AWAY)  # 0, 1


def _set_velocity(vel_msg, vx, vy):
    """Escreve (vx,vy) Cartesiano como direction(mag 100)+speed, como o servidor.
    Velocidade zero -> direção unitária arbitrária p/ frente (speed 0 a torna
    irrelevante) e evita direção de comprimento zero em cálculos do bot."""
    sp = math.hypot(vx, vy)
    vel_msg.speed = sp
    if sp > 0.0:
        vel_msg.direction.x = vx / sp * 100.0
        vel_msg.direction.y = vy / sp * 100.0
    else:
        vel_msg.direction.x = 100.0
        vel_msg.direction.y = 0.0


def state_to_snapshot(state, init_positions=None):
    """Constrói um GameSnapshot absoluto (coordenadas do servidor) a partir do
    State. `init_positions[side][idx]` opcional para preencher init_position
    (senão usa a posição atual, como faz latency.py)."""
    snap = server_pb2.GameSnapshot()
    snap.turn = int(state.turn)
    snap.state = server_pb2.GameSnapshot.State.LISTENING

    players = {}   # (side, idx) -> Player msg, p/ o CopyFrom do holder
    for side in _SIDES:
        team = snap.home_team if side == server_pb2.Team.Side.HOME else snap.away_team
        team.side = side
        team.name = "HOME" if side == server_pb2.Team.Side.HOME else "AWAY"
        team.score = int(state.score[side])
        for idx in range(11):
            p = team.players.add()
            p.number = idx + 1
            p.team_side = side
            px, py = state.pos[side, idx]
            p.position.x = int(px)
            p.position.y = int(py)
            _set_velocity(p.velocity, float(state.vel[side, idx, 0]),
                          float(state.vel[side, idx, 1]))
            if init_positions is not None:
                ix, iy = init_positions[side][idx]
                p.init_position.x = int(ix)
                p.init_position.y = int(iy)
            else:
                p.init_position.x = int(px)
                p.init_position.y = int(py)
            players[(side, idx)] = p

    snap.ball.position.x = int(state.ball_pos[0])
    snap.ball.position.y = int(state.ball_pos[1])
    _set_velocity(snap.ball.velocity, float(state.ball_vel[0]),
                  float(state.ball_vel[1]))
    if state.holder is not None:
        hs, hi = state.holder
        snap.ball.holder.CopyFrom(players[(hs, hi)])

    snap.shot_clock.team_side = int(state.shot_clock_side)
    snap.shot_clock.remaining_turns = int(state.shot_clock)
    return snap
