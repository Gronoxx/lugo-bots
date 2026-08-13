"""
Codificação de observação a partir do State do sim JAX.

- Por-agente (ator descentralizado): vetor egocêntrico, CANONIZADO para "sempre
  ataca +x" (o AWAY tem x espelhado), de forma que UMA rede compartilhada serve
  os dois lados. Saída (B, 2, 11, OBS_DIM).
- Global (crítico central CTDE): estado completo canonizado por lado.
  Saída (B, 2, GLOBAL_DIM).
"""
import jax.numpy as jnp

import step as J

MAX_X, MAX_Y = J.MAX_X, J.MAX_Y
_IS_GK = jnp.array([1.0] + [0.0] * 11)[:11]   # (11,)
_PX = jnp.array([MAX_X, MAX_Y])               # normalizador de posição


def _canon(state, p):
    """Arrays canonizados na perspectiva do lado p (ataca +x). Retorna dict."""
    if p == J.HOME:
        fx_p = lambda a: a
        fx_v = lambda a: a
    else:                                     # espelha x
        fx_p = lambda a: jnp.stack([MAX_X - a[..., 0], a[..., 1]], -1)
        fx_v = lambda a: jnp.stack([-a[..., 0], a[..., 1]], -1)
    my = fx_p(state.pos[:, p]); myv = fx_v(state.vel[:, p])        # (B,11,2)
    th = fx_p(state.pos[:, 1 - p]); thv = fx_v(state.vel[:, 1 - p])
    ball = fx_p(state.ball_pos); ballv = fx_v(state.ball_vel)      # (B,2)
    return dict(my=my, myv=myv, th=th, thv=thv, ball=ball, ballv=ballv,
                hs=state.holder_side, hi=state.holder_idx, p=p,
                jl=state.jump_left[:, p], sc=state.shot_clock,
                scs=state.shot_clock_side, gz=state.goal_zone_turns,
                score=state.score, turn=state.turn)


def _agent_obs(c):
    """Vetor por-agente (B,11,OBS_DIM) para o lado c['p']."""
    my, myv, th, thv = c["my"], c["myv"], c["th"], c["thv"]
    ball, ballv = c["ball"], c["ballv"]
    B = my.shape[0]
    posn = my / _PX                                                # (B,11,2)
    veln = myv / 100.0
    is_holder_me = ((c["hs"] == c["p"])[:, None] &
                    (c["hi"][:, None] == jnp.arange(11)[None, :])).astype(jnp.float32)  # (B,11)
    self_feat = jnp.concatenate([
        posn, veln, jnp.broadcast_to(_IS_GK, (B, 11))[..., None],
        (c["jl"] / J.GOALKEEPER_JUMP_DURATION)[..., None],
        is_holder_me[..., None]], axis=-1)                         # (B,11,7)

    ball_rel = (ball[:, None, :] - my) / MAX_X                     # (B,11,2)
    ballv_b = jnp.broadcast_to((ballv / J.BALL_MAX_SPEED)[:, None, :], (B, 11, 2))
    ball_d = jnp.sqrt(jnp.sum((ball[:, None, :] - my) ** 2, -1, keepdims=True)) / MAX_X
    hs, hi = c["hs"], c["p"]
    h_me = is_holder_me                                            # (B,11)
    h_team = ((c["hs"] == c["p"])[:, None].astype(jnp.float32)) - h_me
    h_opp = jnp.broadcast_to((c["hs"] == (1 - c["p"]))[:, None].astype(jnp.float32), (B, 11))
    h_loose = jnp.broadcast_to((c["hs"] < 0)[:, None].astype(jnp.float32), (B, 11))
    ball_feat = jnp.concatenate([ball_rel, ballv_b, ball_d,
                                 h_me[..., None], h_team[..., None],
                                 h_opp[..., None], h_loose[..., None]], axis=-1)  # (B,11,9)

    team_rel = (my[:, None, :, :] - my[:, :, None, :]) / MAX_X     # (B,11,11,2)
    teamv = jnp.broadcast_to((myv / 100.0)[:, None, :, :], (B, 11, 11, 2))
    team_feat = jnp.concatenate([team_rel, teamv], -1).reshape(B, 11, 11 * 4)

    opp_rel = (th[:, None, :, :] - my[:, :, None, :]) / MAX_X      # (B,11,11,2)
    oppv = jnp.broadcast_to((thv / 100.0)[:, None, :, :], (B, 11, 11, 2))
    opp_feat = jnp.concatenate([opp_rel, oppv], -1).reshape(B, 11, 11 * 4)

    sc_mine = (c["scs"] == c["p"]).astype(jnp.float32)
    ctx = jnp.stack([c["sc"] / J.SHOT_CLOCK_TIME, sc_mine,
                     (c["score"][:, c["p"]] - c["score"][:, 1 - c["p"]]) / 10.0,
                     c["turn"] / 6000.0, c["gz"] / J.BALL_TIME_IN_GOAL_ZONE], -1)  # (B,5)
    ctx = jnp.broadcast_to(ctx[:, None, :], (B, 11, 5))

    return jnp.concatenate([self_feat, ball_feat, team_feat, opp_feat, ctx], -1)


def _global_obs(c):
    """Estado completo canonizado (B, GLOBAL_DIM) para o crítico do lado c['p']."""
    B = c["my"].shape[0]
    flat = lambda a: a.reshape(B, -1)
    return jnp.concatenate([
        flat(c["my"] / _PX), flat(c["myv"] / 100.0),
        flat(c["th"] / _PX), flat(c["thv"] / 100.0),
        c["ball"] / _PX, c["ballv"] / J.BALL_MAX_SPEED,
        (c["sc"] / J.SHOT_CLOCK_TIME)[:, None],
        (c["scs"] == c["p"]).astype(jnp.float32)[:, None],
        ((c["score"][:, c["p"]] - c["score"][:, 1 - c["p"]]) / 10.0)[:, None],
        (c["turn"] / 6000.0)[:, None]], axis=-1)


def get_obs(state):
    """Retorna (agent_obs (B,2,11,OBS_DIM), global_obs (B,2,GLOBAL_DIM))."""
    per, glob = [], []
    for p in (J.HOME, J.AWAY):
        c = _canon(state, p)
        per.append(_agent_obs(c))
        glob.append(_global_obs(c))
    return jnp.stack(per, axis=1), jnp.stack(glob, axis=1)


# dimensões (computadas uma vez)
OBS_DIM = 7 + 9 + 44 + 44 + 5     # 109
GLOBAL_DIM = 11 * 4 + 11 * 4 + 4 + 4   # 96
