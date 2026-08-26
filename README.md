*Versão completa em português: [README.pt-BR.md](README.pt-BR.md)*

# Lugo Bots: `killua-zoldyck`

A multi-agent robot football bot written in Python on top of `lugo4py`, built for the 4th Lugo Bots
Open Championship, from August to October 2026. This repository holds the bot, the measurement
bench, the simulators, the opponent analysis, and above all an honest record of what worked, what
did not, and why.

The bot was eliminated **undefeated**, and the write-up explains exactly how. The diagnosis is
more interesting than the score: it was not beaten by better opponents. It was ruled out by a
tiebreak, and the tiebreak punished precisely the thing the measuring bench had been optimising
in the wrong direction for two weeks.

> **A note on names.** Bots written by other entrants appear throughout under fictitious names
> (`BotAdversario1`…`BotAdversario14`, `Participante1`…), consistently numbered across every
> document. Their source code is not redistributed here — see
> [`rivals/README.md`](rivals/README.md). Scores and statistics are real; the platform's match
> identifiers were replaced with labels, because each one opens a public match page that would
> undo the anonymisation. The official opponents (`level-0`…`level-3`) are platform-provided
> and named as they are.

## How the tournament works, because it explains everything

The first phase is not a group stage. Entrants are challenged by three official bots, and
**points depend on which one you beat**: a win against level-3 is worth 8, against level-2 is
worth 7, against level-1 is worth 5. Draws are worth 3, 3 and 1.

Ranking is by points. The first tiebreak is **overall goal difference**. Only if that also ties
does the specific sequence begin: goal difference against L3, then goals against L3, then goal
difference against L2, then goals against L2, then goal difference against L1, and finally the
registration date.

The eight best-placed entrants go through to the knockout stage.

Two consequences drove the entire project. **Winning is not enough, the criterion is margin**,
which is what pushed the work towards offensive volume. And since a version can be swapped at any
time, one genome per opponent is both legal and advantageous.

## Result

| Opponent | Score | Points | Note |
|---|---|---|---|
| level-1 | 1 to 0 | 5 | 218 completed passes and 2 shots on goal: sterile possession |
| level-2 | 3 to 2 | 7 | 6 shots for 3 goals, but they shot 46 times |
| level-3 | 0 to 0 | 3 | the match that decided everything: 6 shots against 15, 76% of the time in our half |

Fifteen points, three matches, no defeats, and an overall goal difference of plus two. Out
anyway, because with only eight slots the field was decided on tiebreaks, and the goalless draw
against `level-3` left every criterion that follows overall goal difference at zero.

## The central mistake

The regulation rewards margin, so the bench was built to maximise offensive volume. Volume was
measured against `level-1`, whose goalkeeper **parries** long shots. Against that keeper a long
shot turns into a rebound and often a goal, so the bench kept rewarding distance.

The `level-3` keeper **holds** the ball. Against him the same shot is a clean giveaway: no goal
and no rebound either.

One measurement closes the diagnosis. When `chance_origin.py` was finally built, it showed that
**73% of our chances came from opponent goalkeeper rebounds**. A keeper who holds does not reduce
that production, he eliminates it. The 0 to 0 was not bad luck on the day, it was the predictable
output of a chance factory whose main input did not exist against that opponent.

The measuring stick was not wrong through carelessness. It was wrong because it measured the
opponent that was available, not the opponent that decided qualification. That is a validity
problem rather than a tuning problem, and no further optimisation against `level-1` would have
surfaced it.

After elimination, in the challenge matches, the corrected version won 4 to 2 away against
`BotAdversario7`, producing **26 shots** where the tournament version had produced 8. The same
opponent had beaten `BotAdversario5` by 8 to 0. The design was right and it was finished after the match that mattered, with both final versions
stuck in "On tests" on the platform during the decisive hours.

## Architecture: the bot as a genome

`lugo4py` calls one callback per state, and the whole bot lives in five functions in
`bot/src/my_bot.py`, 2,404 lines: `on_holding`, `on_supporting`, `on_defending`,
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

`params.py` holds **241 parameters** — 172 continuous and 69 structural, each with its legal
range. A published version is a small subset of them: the most aggressive one shipped, `v14`,
turns on 36. The 17 `bot/genome_*.json` files are the versions that actually played.

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

### The noise floor, and what it costs to see through it

The single number that governed every decision here is how loud the environment is. The **same
genome**, measured five separate times at 16 matches each, scored 4.44, 3.88, 3.12, 3.81 and
2.94 goals per match — a spread of **±0.75 goals with nothing changed at all**. For a stretch of
this project every experiment being run was below that floor, which is another way of saying they
were measuring nothing.

Three consequences ran through the rest of the work:

- **Self-play cuts the variance.** Same image on both sides, only the genes differ. Standard
  error ≈ **0.17 goals at n=20**, against ~0.9 for the same comparison over a fixed opponent.
  It is what made verdicts like *status +0.28 (z=2.91, n=40)* and *planner −2.65 (z=−8.32)*
  readable at all.
- **State the detectable difference before running.** `compare.sh` prints it: at 8 matches per
  arm the test only sees differences above ~2.7 goals. An early version was declared
  "inconclusive" by a test that had **17% power** — the experiment never could have answered the
  question.
- **The winner's curse is the default, not the exception.** The genetic algorithm's champion led
  at +1.42 goals in the fast search mode and regressed to **+0.38** when revalidated in the
  platform's own timing mode, against +0.88 for the incumbent it was supposed to beat. Every
  search result was re-measured before being believed.

### The gates every commit had to pass

| Gate | What it enforces |
|---|---|
| `bench/test_edge_cases.py` | 140 boundary states; no callback may raise. The `lugo4py` template wraps the callback in `try/except`, so an exception is not a crash — it is a **silently frozen bot** |
| `bench/decide_dump.py` | replays every snapshot through the real decision function under two `PYTHONPATH`s and diffs. With the new gene off, the diff must be empty — 5,999 turns identical, 926 decisions byte-for-byte |
| `bench/latency.py` | 50 ms per turn is the server budget. Worst case measured with every gene on: **2.7 ms** |
| prove it fires | added after two genes were measured as "neutral" while never executing: one was missing from the loader's dictionary, which **ignores unknown keys in silence**; the other was overridden downstream, and tracing the real decision showed the player moving 87 units *backwards* with the gene on |

That fourth gate is the one worth keeping: **"neutral" and "never ran" produce exactly the same
number.**

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

## The simulators

Matches run in Docker, 23 containers each, at roughly one match per minute in the fast mode and
six in the platform's own timing. That is too slow to learn anything from, so `sim/fastsim.py`
reimplements the **server** — not the bot — in NumPy, and `rl/jax/step.py` vectorises the same
physics.

Fidelity was treated as the deliverable, not a detail. The original ball model predicted the next
position from the current velocity and drifted **5.0 units per turn**; reading the trajectories
back showed the server integrates trapezoidally (`v − decel/2`), which brought the error down to
**0.38 units**, and the whole simulator to a median of ~0.4 units per turn against real replays.
Fixing it improved interception, passing and defending at once, because all three were built on
the same wrong prediction. The JAX rewrite is checked against the scalar one and agrees to
**0.00 units over 40 turns**; batched at 4096 environments on a GTX 1660 SUPER it runs
**45 M env-steps/s**, about 7,500 full matches per second.

The other simulator is stranger and more useful. Platform matches ship as **video only**, no
replay file — so `sim/scene_extract.py` recovers the 22 player positions and the ball from the
MP4 by computer vision, and `scene_runner.py` drops the live bot into that reconstructed state.
Thirteen conceded goals were rebuilt this way and turned into a pass/fail suite: the candidate
had to survive all of them. It went from 42/55 to **130/130**.

## Reinforcement learning track

`rl/` holds the full stack: the bridge that runs the real bot inside the fast simulator, CTDE
observations (109 egocentric dims, 96 global), a `MultiDiscrete` action space, and MAPPO with a
shared actor and a central critic in JAX.

It never beat the heuristic, and **the four bugs it took to find that out are the most
transferable thing in this repository**. All four produced the same symptom — 0% possession, no
goals — and each one masked the next:

1. **Potential-based shaping is invariant by construction.** With reward entirely of the form
   `γΦ' − Φ`, the advantage is ≈ 0: the critic happily learns `V ≈ −Φ` and *looks* like it is
   training, while the actor receives noise. Ng's theorem is exactly why it cannot teach anything.
2. **Uniform exploration destroys the very skill being learned.** The shoot head has 17 options,
   so a random ball carrier shoots on **~94% of turns** and loses the ball the turn it gets it.
   "Hold the ball" is not discoverable by chance. Fixed with an initialisation prior, not more
   samples.
3. **The reward was farmable by standing still.** Rewarding ball advance unconditionally makes
   the optimal policy push the ball forward once and collect. The diagnostic was unambiguous:
   possession **0.04%**, the agent parked 1,550 units from the ball, the ball stationary 80% of
   the time. The fix was to make shaping effort-based and conditional on possession.
4. **A measurement bug hid the first three.** Evaluation read the final score *after* the
   environment's auto-reset, which zeroes it — so every run reported 0×0 regardless of what the
   policy did. Counting goals by event during the rollout was the actual fix.

With those closed, possession climbed monotonically from 1% to **73%**. The track was then **shelved on a
structural argument, not on frustration**: the heuristic bot is a Python object over `lugo4py`
and cannot run inside a vmapped JAX batch, behaviour cloning of it fails on distribution shift,
and the strongest JAX-native opponent that could be built loses to it 0–12. So self-play had a
ceiling below the incumbent *by construction* — measured at 0–8.

`results/RL_MOTHBALL_CONDICOES.md` records **two objective conditions for reopening it**: port
the scalar simulator's fidelity fixes into the JAX step and pass the cross-check, and get a
faithful strong opponent into the JAX loop. Nothing was deleted, nothing runs, and the criteria
are written down rather than remembered.

## Contributing upstream

Working this close to `lugo4py` surfaced a long list of oddities. Rather than reporting the list,
each one was tested against the library's own API: ~13 candidates, **11 discarded** as our
misreading or as behaviour that was actually correct, **2 confirmed and turned into patches** —
including a constant defined as `PLAYER_SIZE * 2.3,` whose trailing comma silently makes it a
tuple, so any arithmetic on it raises. The triage, including the discarded ones and why, is in
[`results/UPSTREAM_TRIAGEM.md`](results/UPSTREAM_TRIAGEM.md).

## What I would do differently

The six items below are the actual output of this project, more than any score.

**Measure against the opponent that decides, from day one.** `level-2` and `level-3` exist only on
the platform, with a quota of five matches per day. That is not an obstacle, it is a budget to be
spent with discipline, and it was spent late and badly. One challenge against `level-3` per day,
from the first week, would have exposed the conversion curve months earlier.

**Decompose every gain by mechanism before celebrating it.** The jump from 1.44 to 3.58 goals
looked like progress and was half artefact. The question "through which channel?" should be
mandatory alongside "by how much?".

**Build `chance_origin.py` at the start, not at the end.** Knowing that 73% of chances came from
opponent keeper rebounds would have changed every earlier decision, and would have predicted that
a keeper who holds zeroes the entire factory.

**Treat the platform queue as part of the deadline.** Publishing two hours before the match is not
publishing on time. The validation window is a resource the opponent also consumes.

**Shelve the reinforcement learning track a week earlier.** Stopping was the right call and it was
well documented, but the signals were available long before the structural ceiling was proved
against a strong opponent.

**Buy information before the window closes.** The last call was a bet made with almost no data.
An older version had won 3 to 0 against `level-3`, but on a single match, and access to `level-3`
is rationed, so revalidating it close to the deadline was not possible. The choice was between a
result with a sample of one and a newer version with a higher ceiling. Since the ranking is decided
on goal difference, even a confirmed 3 to 0 was unlikely to be enough, which made the newer version
the rational bet.

The bet itself was defensible. What went wrong was upstream of it: by the time the decision had to
be made, there was no budget left to reduce the uncertainty. Both final versions then sat stuck in
platform testing during the decisive hours, so the aggressive option never even played.

## Running it

Requires Docker. A full match spins up 23 containers.

```bash
bench/run_match.sh                        # one match with replay
python3 bench/escada.py --reps 16         # offensive ceiling over N matches
python3 bench/ab_selfplay.py --arm-a ...  # A/B against ourselves, the strong stick
```

The three gates, which every commit had to pass:

```bash
python3 bench/test_edge_cases.py          # 140 boundary states, no callback may raise
python3 bench/decide_dump.py <replay>     # decisions must be byte-identical with the gene off
python3 bench/latency.py                  # 50 ms/turn budget
```

## Layout

| Directory | Contents |
|---|---|
| `bot/` | the bot, its five decision functions, and the 17 genomes that played |
| `bench/` | the measurement bench: match runners, A/B harnesses, the genetic algorithm, the gates |
| `sim/` | the fast simulator, its fidelity regression, and scene reconstruction from match video |
| `rl/` | the reinforcement learning track — bridge, JAX environment, MAPPO, evaluation |
| `analysis/` | replay parsing, physics measurement, and platform scraping |
| `results/` | every report, phase by phase, including the post-mortems and the upstream triage |
| `rivals/` | how to rebuild the opponent panel; third-party code is deliberately not included |

[`README.pt-BR.md`](README.pt-BR.md) carries the full account in Portuguese, several times
longer: the phase-by-phase trajectory with the numbers behind each decision, the competitive
strategy, the opponent analysis, and the server and laboratory pitfalls that cost real time.

## Credits

Project by Gustavo (@Gronoxx), developed in pairing with Claude (Anthropic) through Claude Code.
The strategic decisions, the experiment design and several of the central ideas came from the
author: the self-play measuring stick, the simulated scenes reconstructed from video, and the
requirement of forensic justification rather than a binary result. Implementation, measurement and
reporting were built together.
