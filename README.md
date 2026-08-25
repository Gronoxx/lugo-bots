*Versão completa em português: [README.pt-BR.md](README.pt-BR.md)*

# Lugo Bots: `killua-zoldyck`

A multi-agent robot football bot written in Python on top of `lugo4py`, built for the 4th Lugo Bots
Open Championship, from August to October 2026. This repository holds the bot, the measurement
bench, the simulators, the opponent analysis, and above all an honest record of what worked, what
did not, and why.

We did not make it past the group stage. The write-up explains exactly where the project failed,
and the diagnosis is more interesting than the score: **the bot did not lose for lack of
engineering. It lost because we measured the wrong thing for two weeks.**

## The central mistake

We optimised the attack against `level-1`, whose goalkeeper **parries** long shots. A long shot
against that keeper turns into a rebound and often a goal, so the lab rewarded volume from
distance.

The `level-3` keeper **holds** the ball. Against him the same shot is a clean giveaway: no goal and
no rebound either. The measuring stick was not wrong through carelessness. It was wrong because it
measured the opponent that was available, not the opponent that decided qualification.

That is a validity problem, not a tuning problem, and no amount of further optimisation against
`level-1` would have surfaced it.

## Result

Group stage, the matches that counted:

| Opponent | Score | Points | Note |
|---|---|---|---|
| level-1 | 1 to 0 | 5 | 218 completed passes and 2 shots on goal: sterile possession |
| level-2 | 3 to 2 | 7 | 6 shots for 3 goals, but they shot 46 times |
| level-3 | 0 to 0 | 3 | the elimination match: 6 shots against 15, 76% of the time in our half |

Fifteen points and a goal difference of zero against `level-3`. The seeding tiebreak runs goal
difference against L3, then goals against L3, then goal difference against L2. Zero goals in the
first criterion is what knocked us out.

After elimination, with the version that arrived late, the bot won 4 to 2 away against
`BotAdversario7` with **26 shots against 8**, where the tournament version produced 8. The same
opponent had beaten `BotAdversario5` by 8 to 0. The design was right. It was ready after the match
that mattered, and both final versions sat stuck in "On tests" on the platform during the decisive
hours.

## Architecture: the bot as a genome

`lugo4py` calls one callback per state, and the whole bot lives in five functions in
`bot/src/my_bot.py`, around 2000 lines: `on_holding`, `on_supporting`, `on_defending`,
`on_disputing` and `as_goalkeeper`. Supporting modules cover geometry and interception,
dynamic formation and roles, set plays, a non-greedy passing planner, ball carrying and
finishing.

The most important design decision in the repository is that **no behavioural change is written
directly into the code**. Every idea becomes a parameter in `bot/src/params.py`, with a default
value that reproduces the previous version exactly:

```python
DEFAULTS = {"dangerous_shot_range": 6000.0, "dc_floor": 0.52, ...}        # continuous
STRUCTURE_DEFAULTS = {"shot_gate": "threshold", "def_camp": "off", ...}   # structural
BOUNDS = {"dangerous_shot_range": (2000.0, 8000.0), ...}                  # legal ranges
```

Every new behaviour is born switched off. A change only reaches the tournament version if a
measurement turns it on, which means the repository can answer, for any behaviour, when it was
enabled and on what evidence.

## The bench

Half of this repository is instrumentation, and **each tool exists because of a specific
measurement error**.

| Tool | Question it answers |
|---|---|
| `bench/run_match.sh` | a full match across 23 containers, and the replay |
| `bench/escada.py` | offensive ceiling: N matches, median and mean goals |
| `bench/ab_transition.py` | A/B of two arms against the same opponent, with a defensive panel |
| `bench/ab_selfplay.py` | the strong measuring stick: our bot against itself, only the genes differ |
| `bench/shot_distance_curve.py` | conversion against shot distance |
| `bench/shot_veto.py` | why the bot did **not** shoot: out of range, blocked line, keeper slack |
| `bench/chance_origin.py` | where short chances come from: rebound, high turnover, build-up |
| `bench/siege_probe.py` | which local opponent reproduces the geography of the real one |
| `sim/scene_extract.py` | reconstructs plays from the platform's **video** and re-simulates them |

Self-play deserves the emphasis. Measuring against a fixed opponent tells you how well you exploit
that opponent. Measuring against yourself, with only the genes changed, isolates the change from
the opponent, and it was the only instrument that survived the whole project without being
recalibrated.

## Empirical laws the project found

Rules discovered along the way and then used as filters. Each one cost matches.

**The law of passivity**, confirmed six separate times: any change that removes a body from the
attack in order to improve the defence ends up conceding more goals than it saves. It appeared as
dropping the whole line on a contested ball, adding fixed markers, staggering centre backs, closing
the central corridor after restarts, and more conservative passing vetoes.

The sixth form is the treacherous one. Twenty-six genes, **each approved on its own**, drained the
attack when switched on together: goals fell from 1.81 to 0.94, shots from 4.88 to 2.38, and goals
conceded reached a "perfect" 0.06. Classic starvation. The bot became excellent at not losing and
incapable of winning. Only a bisection found it, and the lesson is that approving changes
individually says nothing about approving them jointly.

## Reinforcement learning track

`rl/` holds a track with custom environments, evaluation harness and a JAX implementation. It was
shelved deliberately rather than abandoned: with a measurement stick this noisy, a learned policy
could not be told apart from luck, and fixing the instrument came first. The reasoning is recorded
in the Portuguese write-up.

## Running it

Requires Docker. A full match spins up 23 containers.

```bash
bench/run_match.sh                       # one match with replay
python3 bench/escada.py --reps 10        # offensive ceiling over N matches
python3 bench/ab_selfplay.py --arm-a ... # A/B against ourselves
```

## Layout

`bot/` holds the bot and its genomes, `bench/` the measurement tools, `sim/` the fast simulator and
scene reconstruction, `analysis/` independent analysis scripts, `rivals/` the opponent panel,
`rl/` the reinforcement learning track, and `results/` the reports, including the upstream
contribution triage in `results/UPSTREAM_TRIAGEM.md`.

The Portuguese version carries the full account: the phase-by-phase trajectory, the competitive
strategy, the opponent analysis, the server and laboratory pitfalls that cost real time, and what
I would do differently.

## Credits

Project by Gustavo (@Gronoxx), developed in pairing with Claude (Anthropic).
