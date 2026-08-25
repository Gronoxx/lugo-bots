"""
Física do Lugo vetorizada em JAX — B partidas em paralelo na GPU.

Porta o sim escalar (sim/fastsim.py) para jax.numpy, branchless (máscaras via
jnp.where), com State como pytree (flax.struct). jit+scan sobre turnos; o batch
B é o eixo 0 de todos os arrays (sem vmap explícito).

Diferença deliberada vs o escalar: a captura/roubo é resolvida por ARGMIN GLOBAL
(quem, tendo pedido catch e no raio, está mais perto da bola que o dono atual),
independente da ordem de processamento — remove o viés HOME-antes-de-AWAY.

Convenções idênticas ao escalar: side 0=HOME/1=AWAY, idx 0=goleiro (nº 1),
pos[b, side, idx] = (x, y). holder codificado como holder_side (-1=livre) + idx.
"""
import jax
import jax.numpy as jnp
from flax import struct

# ---- constantes (iguais a sim/fastsim.py:24-45) ----
MAX_X = 20000.0
MAX_Y = 10000.0
GOAL_MIN_Y = 3500.0
GOAL_MAX_Y = 6500.0
GOAL_ZONE_RANGE = 1400.0
PLAYER_MAX_SPEED = 100.0
BALL_MAX_SPEED = 400.0
BALL_MIN_SPEED = 2.0
BALL_DECEL = 10.0
BALL_TIME_IN_GOAL_ZONE = 40
TOUCH_RADIUS = 300.0
GK_CATCH_RADIUS = 560.0
BALL_HOLD_OFFSET = 200.0
GOALKEEPER_JUMP_SPEED = 200.0
GOALKEEPER_JUMP_DURATION = 3
SHOT_CLOCK_TIME = 300
HOME, AWAY = 0, 1

# formação default normalizada (igual a fastsim.DEFAULT_FORMATION)
_FORM = jnp.array([
    [0.03, 0.50], [0.16, 0.20], [0.14, 0.40], [0.14, 0.60], [0.16, 0.80],
    [0.35, 0.30], [0.33, 0.50], [0.35, 0.70], [0.60, 0.25], [0.62, 0.50],
    [0.60, 0.75]])
# raio de catch por jogador (goleiro idx 0 = 560, resto 300)
_CATCH_R = jnp.array([GK_CATCH_RADIUS] + [TOUCH_RADIUS] * 10)   # (11,)
_IS_GK = jnp.array([True] + [False] * 10)                       # (11,)


@struct.dataclass
class State:
    turn: jnp.ndarray            # (B,)
    pos: jnp.ndarray             # (B, 2, 11, 2)
    vel: jnp.ndarray             # (B, 2, 11, 2)
    ball_pos: jnp.ndarray        # (B, 2)
    ball_vel: jnp.ndarray        # (B, 2)
    holder_side: jnp.ndarray     # (B,) int32, -1 = livre
    holder_idx: jnp.ndarray      # (B,) int32
    score: jnp.ndarray           # (B, 2) int32
    shot_clock_side: jnp.ndarray  # (B,)
    shot_clock: jnp.ndarray      # (B,)
    jump_left: jnp.ndarray       # (B, 2, 11) int32
    goal_zone_turns: jnp.ndarray  # (B,)


def initial_state(batch: int) -> State:
    home = jnp.stack([_FORM[:, 0] * MAX_X, _FORM[:, 1] * MAX_Y], axis=-1)      # (11,2)
    away = jnp.stack([(1 - _FORM[:, 0]) * MAX_X, _FORM[:, 1] * MAX_Y], axis=-1)
    pos = jnp.stack([home, away], axis=0)                                     # (2,11,2)
    pos = jnp.broadcast_to(pos, (batch, 2, 11, 2))
    z = jnp.zeros((batch, 2, 11, 2))
    return State(
        turn=jnp.zeros(batch, jnp.int32),
        pos=pos.astype(jnp.float32), vel=z.astype(jnp.float32),
        ball_pos=jnp.broadcast_to(jnp.array([MAX_X / 2, MAX_Y / 2]), (batch, 2)).astype(jnp.float32),
        ball_vel=jnp.zeros((batch, 2), jnp.float32),
        holder_side=-jnp.ones(batch, jnp.int32), holder_idx=jnp.zeros(batch, jnp.int32),
        score=jnp.zeros((batch, 2), jnp.int32),
        shot_clock_side=jnp.zeros(batch, jnp.int32),
        shot_clock=jnp.full(batch, SHOT_CLOCK_TIME, jnp.int32),
        jump_left=jnp.zeros((batch, 2, 11), jnp.int32),
        goal_zone_turns=jnp.zeros(batch, jnp.int32))


def finishing_state(batch: int, key) -> State:
    """Estado de 'treino de finalização' (start-state curriculum): a bola começa
    PERTO do gol AWAY (x∈[15000,18000], y∈[3500,6500], fora do círculo 1400) com um
    jogador de LINHA do HOME (idx 1..10) segurando-a. Expõe o policy a MUITAS
    situações de chute -> aprende a finalizar (sinal de gol denso). Demais jogadores
    na formação padrão. Usar em fração inicial do treino, depois misturar starts
    normais (initial_state)."""
    s = initial_state(batch)
    k1, k2, k3 = jax.random.split(key, 3)
    bx = jax.random.uniform(k1, (batch,), minval=15000.0, maxval=18000.0)
    by = jax.random.uniform(k2, (batch,), minval=GOAL_MIN_Y, maxval=GOAL_MAX_Y)
    ball_pos = jnp.stack([bx, by], axis=-1)                          # (B,2)
    hidx = jax.random.randint(k3, (batch,), 1, 11).astype(jnp.int32)  # linha 1..10
    bi = jnp.arange(batch)
    pos = s.pos.at[bi, HOME, hidx].set(ball_pos)                     # holder na bola
    return s.replace(pos=pos, ball_pos=ball_pos,
                     holder_side=jnp.zeros(batch, jnp.int32),        # HOME segura
                     holder_idx=hidx,
                     shot_clock_side=jnp.zeros(batch, jnp.int32),
                     shot_clock=jnp.full(batch, SHOT_CLOCK_TIME, jnp.int32))


def _norm(v):
    return jnp.sqrt(jnp.sum(v * v, axis=-1))


def _clip_speed(v, vmax):
    sp = _norm(v)
    scale = jnp.where(sp > vmax, vmax / jnp.maximum(sp, 1e-9), 1.0)
    return v * scale[..., None]


def _move_ball(ball_pos, ball_vel):
    """Um turno da bola solta. Retorna (pos, vel, goal_side[-1/0/1])."""
    sp = _norm(ball_vel)                                    # (B,)
    moving = sp > BALL_MIN_SPEED
    adv = jnp.maximum(0.0, sp - BALL_DECEL / 2) / jnp.maximum(sp, 1e-9)
    new_pos = ball_pos + ball_vel * adv[..., None]
    new_pos = jnp.where(moving[..., None], new_pos, ball_pos)
    # gol (antes do quique)
    iny = (new_pos[..., 1] >= GOAL_MIN_Y) & (new_pos[..., 1] <= GOAL_MAX_Y)
    g_away = moving & (new_pos[..., 0] <= 0) & iny
    g_home = moving & (new_pos[..., 0] >= MAX_X) & iny
    goal = jnp.where(g_away, AWAY, jnp.where(g_home, HOME, -1)).astype(jnp.int32)
    # quique
    px, py = new_pos[..., 0], new_pos[..., 1]
    vx, vy = ball_vel[..., 0], ball_vel[..., 1]
    lo = px < 0
    hi = px > MAX_X
    px = jnp.where(lo, -px, jnp.where(hi, 2 * MAX_X - px, px))
    vx = jnp.where(lo | hi, -vx, vx)
    lo = py < 0
    hi = py > MAX_Y
    py = jnp.where(lo, -py, jnp.where(hi, 2 * MAX_Y - py, py))
    vy = jnp.where(lo | hi, -vy, vy)
    new_pos = jnp.stack([px, py], axis=-1)
    bvel = jnp.stack([vx, vy], axis=-1)
    # desaceleração
    new_sp = jnp.maximum(0.0, sp - BALL_DECEL)
    stop = new_sp <= BALL_MIN_SPEED
    scale = jnp.where(moving & ~stop, new_sp / jnp.maximum(sp, 1e-9), 0.0)
    new_vel = jnp.where(moving[..., None], bvel * scale[..., None], 0.0)
    new_pos = jnp.where(moving[..., None], new_pos, ball_pos)
    return new_pos, new_vel, goal


def _advance_players(pos, vel):
    """pos += vel, com clamp de campo, goleiro preso à linha e empurrão do gol."""
    pos = pos + vel
    x = jnp.clip(pos[..., 0], 0.0, MAX_X)
    y = jnp.clip(pos[..., 1], 0.0, MAX_Y)
    # goleiro (idx 0) preso à linha: HOME x=0, AWAY x=MAX_X
    gk_x = jnp.array([0.0, MAX_X]).reshape(1, 2, 1)         # (1,2,1) por side
    is_gk = _IS_GK.reshape(1, 1, 11)                        # (1,1,11)
    x = jnp.where(is_gk, jnp.broadcast_to(gk_x, x.shape), x)
    # empurrão: jogadores de LINHA fora de 1400 do gol ATACADO
    goal_x = jnp.array([MAX_X, 0.0]).reshape(1, 2, 1)       # HOME ataca MAX_X, AWAY 0
    dx = x - goal_x
    dy = y - MAX_Y / 2
    d = jnp.sqrt(dx * dx + dy * dy)
    inside = (~is_gk) & (d < GOAL_ZONE_RANGE)
    scale = GOAL_ZONE_RANGE / jnp.maximum(d, 1e-6)
    x = jnp.where(inside, goal_x + dx * scale, x)
    y = jnp.where(inside, MAX_Y / 2 + dy * scale, y)
    return jnp.stack([x, y], axis=-1)


def _resolve_catch(pos, ball_pos, do_catch, holder_side, holder_idx):
    """Argmin global: entre quem pediu catch e está no raio e (livre ou lado ≠
    do dono), o mais perto da bola rouba SE estiver mais perto que o dono."""
    B = pos.shape[0]
    d = _norm(pos - ball_pos[:, None, None, :])            # (B,2,11)
    within = d <= _CATCH_R.reshape(1, 1, 11)
    free = holder_side < 0                                  # (B,)
    same_side = jnp.arange(2).reshape(1, 2, 1) == holder_side[:, None, None]
    eligible = do_catch & within & (free[:, None, None] | ~same_side)
    d_flat = jnp.where(eligible, d, jnp.inf).reshape(B, 22)
    cand = jnp.argmin(d_flat, axis=1).astype(jnp.int32)     # (B,)
    min_d = jnp.min(d_flat, axis=1)
    # distância do dono atual à bola (inf se livre)
    h_flat = (holder_side * 11 + holder_idx).astype(jnp.int32)
    d_all = d.reshape(B, 22)
    d_holder = jnp.where(free, jnp.inf,
                         jnp.take_along_axis(d_all, jnp.clip(h_flat, 0, 21)[:, None], axis=1)[:, 0])
    take = jnp.isfinite(min_d) & (min_d < d_holder)
    new_flat = jnp.where(take, cand, h_flat)
    new_side = jnp.where(free & ~take, -1, new_flat // 11).astype(jnp.int32)
    new_idx = jnp.where(free & ~take, 0, new_flat % 11).astype(jnp.int32)
    changed_side = take & (~free) & ((cand // 11) != holder_side) | (take & free)
    return new_side, new_idx, changed_side


def _apply_kick(ball_vel, kick_vec, holder_vel):
    """Chute do dono: fator de ângulo com a direção do jogador, soma à bola, cap."""
    psp = _norm(holder_vel)
    ksp = _norm(kick_vec)
    cos = jnp.sum(holder_vel * kick_vec, axis=-1) / jnp.maximum(psp * ksp, 1e-9)
    cos = jnp.clip(cos, -1.0, 1.0)
    ang = jnp.degrees(jnp.arccos(cos))
    factor = jnp.where((psp > 1e-9) & (ksp > 1e-9), 0.5 + 0.5 * ((180 - ang) / 180), 1.0)
    kv = kick_vec * factor[..., None]
    return _clip_speed(ball_vel + kv, BALL_MAX_SPEED)


def _glue(pos, vel, holder_side, holder_idx):
    """Bola ~200d à frente do dono (na direção da vel; se parado, rumo ao gol)."""
    B = pos.shape[0]
    bi = jnp.arange(B)
    hs = jnp.clip(holder_side, 0, 1)
    hp = pos[bi, hs, holder_idx]                            # (B,2)
    hv = vel[bi, hs, holder_idx]
    sp = _norm(hv)
    gx = jnp.where(holder_side == HOME, MAX_X, 0.0)
    to_goal = jnp.stack([gx - hp[:, 0], MAX_Y / 2 - hp[:, 1]], axis=-1)
    d = jnp.where((sp > 1e-6)[:, None], hv / jnp.maximum(sp[:, None], 1e-9),
                  to_goal / jnp.maximum(_norm(to_goal)[:, None], 1e-9))
    return hp + d * BALL_HOLD_OFFSET, hv


def step(state: State, move, kick, do_catch, do_jump) -> State:
    """Avança um turno em todas as B partidas.
    move,kick: (B,2,11,2); do_catch,do_jump: (B,2,11) bool."""
    B = state.pos.shape[0]
    bi = jnp.arange(B)
    free = state.holder_side < 0

    # --- fase A: bola solta move primeiro ---
    ball_pos_A, ball_vel_A, goal_A = _move_ball(state.ball_pos, state.ball_vel)
    ball_pos = jnp.where(free[:, None], ball_pos_A, state.ball_pos)
    ball_vel = jnp.where(free[:, None], ball_vel_A, state.ball_vel)
    goal_side = jnp.where(free, goal_A, -1)

    # --- fase B: velocidades e avanço dos jogadores ---
    jumping = state.jump_left > 0                           # (B,2,11)
    is_gk = _IS_GK.reshape(1, 1, 11)
    start_jump = do_jump & is_gk & ~jumping
    move_vel = _clip_speed(move, PLAYER_MAX_SPEED)
    jump_vel = _clip_speed(move, GOALKEEPER_JUMP_SPEED)
    vel = jnp.where(jumping[..., None], _clip_speed(state.vel, GOALKEEPER_JUMP_SPEED),
                    jnp.where(start_jump[..., None], jump_vel, move_vel))
    jump_left = jnp.maximum(0, state.jump_left - jumping.astype(jnp.int32))
    jump_left = jnp.where(start_jump, GOALKEEPER_JUMP_DURATION - 1, jump_left)
    pos = _advance_players(state.pos, vel)

    # --- fase C: catch/roubo (argmin global) ---
    hs, hi, _ = _resolve_catch(pos, ball_pos, do_catch, state.holder_side, state.holder_idx)
    # reset do shot clock quando a posse muda de lado
    changed = (hs != state.holder_side) & (hs >= 0)
    sc_side = jnp.where(changed, hs, state.shot_clock_side)
    sc = jnp.where(changed, SHOT_CLOCK_TIME, state.shot_clock)

    # --- fase D: chute do dono ---
    held = hs >= 0
    hs_c = jnp.clip(hs, 0, 1)
    holder_kick = kick[bi, hs_c, hi]                       # (B,2)
    holder_vel = vel[bi, hs_c, hi]
    wants_kick = held & (_norm(holder_kick) > 1e-9)
    kicked_vel = _apply_kick(ball_vel, holder_kick, holder_vel)
    # a bola do dono, se não chutar, fica colada; se chutar, vira solta e move
    glue_pos, glue_vel = _glue(pos, vel, hs, hi)
    ball_pos = jnp.where(held[:, None] & ~wants_kick[:, None], glue_pos, ball_pos)
    ball_vel = jnp.where(held[:, None] & ~wants_kick[:, None], glue_vel, ball_vel)
    # aplica o chute
    ball_vel = jnp.where(wants_kick[:, None], kicked_vel, ball_vel)
    ball_pos = jnp.where(wants_kick[:, None], glue_pos, ball_pos)   # sai da frente do chutador
    hs = jnp.where(wants_kick, -1, hs)                     # chute solta a bola
    # move a bola recém-chutada (e checa gol)
    kmoved_pos, kmoved_vel, goal_D = _move_ball(ball_pos, ball_vel)
    ball_pos = jnp.where(wants_kick[:, None], kmoved_pos, ball_pos)
    ball_vel = jnp.where(wants_kick[:, None], kmoved_vel, ball_vel)
    goal_side = jnp.where((goal_side < 0) & wants_kick, goal_D, goal_side)

    # --- fase E: shot clock (posse) ---
    held = hs >= 0
    sc = jnp.where(held & (hs == sc_side), sc - 1, sc)
    expired = held & (sc <= 0)
    other = 1 - jnp.clip(hs, 0, 1)
    hs = jnp.where(expired, other, hs)
    hi = jnp.where(expired, 0, hi)
    ball_pos = jnp.where(expired[:, None], pos[bi, other, 0], ball_pos)
    ball_vel = jnp.where(expired[:, None], 0.0, ball_vel)
    sc_side = jnp.where(expired, other, sc_side)
    sc = jnp.where(expired, SHOT_CLOCK_TIME, sc)

    # --- fase F: goal zone (bola solta parada na área) ---
    loose = hs < 0
    dz0 = jnp.sqrt(ball_pos[:, 0] ** 2 + (ball_pos[:, 1] - MAX_Y / 2) ** 2)
    dz1 = jnp.sqrt((ball_pos[:, 0] - MAX_X) ** 2 + (ball_pos[:, 1] - MAX_Y / 2) ** 2)
    in_zone = loose & ((dz0 < GOAL_ZONE_RANGE) | (dz1 < GOAL_ZONE_RANGE))
    gz = jnp.where(in_zone, state.goal_zone_turns + 1, 0)
    eject = in_zone & (gz >= BALL_TIME_IN_GOAL_ZONE)
    to_center = jnp.stack([MAX_X / 2 - ball_pos[:, 0], MAX_Y / 2 - ball_pos[:, 1]], axis=-1)
    to_center = to_center / jnp.maximum(_norm(to_center)[:, None], 1e-9) * BALL_MAX_SPEED
    ball_vel = jnp.where(eject[:, None], to_center, ball_vel)
    gz = jnp.where(eject, 0, gz)

    # --- monta o estado do turno ---
    ns = State(
        turn=state.turn + 1, pos=pos, vel=vel, ball_pos=ball_pos, ball_vel=ball_vel,
        holder_side=hs.astype(jnp.int32), holder_idx=hi.astype(jnp.int32),
        score=state.score, shot_clock_side=sc_side.astype(jnp.int32),
        shot_clock=sc.astype(jnp.int32), jump_left=jump_left, goal_zone_turns=gz.astype(jnp.int32))

    # --- gol: incrementa placar e RESETA as partidas que marcaram ---
    scored = goal_side >= 0
    add = jax.nn.one_hot(jnp.clip(goal_side, 0, 1), 2, dtype=jnp.int32) * scored[:, None].astype(jnp.int32)
    new_score = state.score + add
    fresh = initial_state(B)
    fresh = fresh.replace(score=new_score, turn=ns.turn)
    def sel(a, b):
        m = scored.reshape((B,) + (1,) * (a.ndim - 1))
        return jnp.where(m, a, b)
    ns = jax.tree_util.tree_map(sel, fresh, ns.replace(score=new_score))
    return ns
