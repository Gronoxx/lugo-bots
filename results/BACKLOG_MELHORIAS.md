# Backlog de melhorias — insights da sessão de 15-17/08 ainda não realizados

> Três baldes: (A) ideias NÃO implementadas; (B) genes implementados SEM veredito/adoção;
> (C) validações pendentes de canal (plataforma/bancada). Prioridade P1>P2>P3; esforço
> em horas de dev (validação por fora).

## A. Não implementadas (ideias com desenho pronto)

| # | Ideia | Tese/insight de origem | Prioridade | Esforço |
|---|---|---|---|---|
| A1 | ~~`adaptive_gate`~~ **IMPLEMENTADO 17/08** (gene `shot_gate_adaptive` + `ag_min_shots`/`ag_max_goals`). Screening v1 (8 chutes/≤1 gol): funciona vs sparring (qualidade 0,41→0,62) mas dispara cedo vs L1 (gols 2,31→1,94 — auto-armadilha: modo seletivo atrasa o gol que destravaria a volta). Recalibrado p/ 12/0 (paredão de verdade); re-screening em curso | **P1** | feito |
| A2 | **`auto_profile`** — detector de ESTILO em-jogo (muralha: ≥8 adversários numa banda vertical estreita; pressing: n chasers médios; posse) ligando o perfil-resposta (inanição/normal) | Uma versão cobrindo dois mundos no mata-mata; generaliza A1 | P2 | ~3h |
| A3 | **Bloqueio de linha de chute** — zagueiro mais próximo se planta NA reta portador→gol (~1000 do portador) quando ele entra na zona perigosa | Anatomia dos 3 gols da v3 vs BotAdversario1 (cerco→chute no canto); gk_track falhou; corpo ATIVO na linha ≠ passividade | P2 | ~1h |
| A4 | **Ambush OFENSIVO do auto-chute** — bola presa 40 turnos no anel DELES → ejeção ao centro é previsível → receptor na trajetória | Item do plano P2.c nunca construído; a versão DEFENSIVA falhou, a ofensiva é outra física (campo deles vazio atrás da ejeção) | P3 | ~1h |
| A5 | **Protocolo de travessia (3-vs-GK)** — coreografia explícita: condutor compromete um lado, far-post one-touch | "Erradicar o gol perdido livre"; slack-gate resolve o grosso; a coreografia completa fica se a v4s/v4k não bastarem | P3 | ~2-3h |
| A6 | **Adaptação de formação em-jogo** — contar campers/estilo e ajustar shift/aggression dinamicamente | Da discussão de formações; hoje adaptação é só por versão | P3 | ~2h |
| A7 | **P6: veto com modelo de oponente offline** — P(deslocamento do defensor\|estado) de replays reais relaxa o pior-caso dos vetos (gap medido até 27pp); padrão finishing.py, gene `veto_model=learned` | Herança da linha RL (única direção de aprendizado não-bloqueada) | P3 (pós-quartas) | ~4-6h |
| A8 | **Métricas condicionais ao placar** no defense/setplay_report (segmentar por estado do jogo) | Sem isso os genes P5 (gs_*) não têm régua local | P2 (se P5 for validar) | ~1h |
| A9 | **sb_dist por adversário** — a zona de limpeza varia com o estilo do GK adversário (2600 confirmado vs level-1; muralha chuta mais longe) | Duelo sb_dist + jogo da BotAdversario9 | P3 | ~0,5h |

## B. Implementadas, default-off, SEM veredito de adoção (reavaliáveis)

| Gene | Status/evidência | Onde reavaliar |
|---|---|---|
| `pass_veto_mode=turnwise` | HOLD — segurança na direção certa solo (CA 2→0), sinergia não materializou | plataforma/bancada, sobre a v4 |
| `init_variant=sym` | Legal, corrige o bug de quantização; SEM vantagem de corrida comprovada | adotar como conserto cosmético na próxima versão? decisão pendente |
| kickoff pack (`kick9`+`kickoff_play`) | Elegível local (converte reinícios ganhos 0→38%); parked p/ mata-mata vs iguais | plataforma vs classe igual |
| `gk_clear_mode=safe`, `def_outlet`, `pass_min_dist_danger`, `cover_lane_mix`, `marking_mode=man`, `support_catch`, `attack_width`, `far_post_run` | testados de raspão ou nunca solo; nenhum sinal forte | fila de oportunidade / bancada |
| P5: `gs_shot_scale`, `gs_sb_boost`, `gs_retain_late`, `gs_draw_ok` | implementados; `gs_retain_late+draw_ok` já embarcados na v4k SEM validação própria (travas da v4k passaram como pacote) | métricas condicionais (A8) + mata-mata real |
| `init_variant=fine` (d=1451) | legal, ganho ≤1 turno; **banida de main** (risco W.O. se plataforma divergir) | arquivada |
| `zone_ambush` (defensivo) | REJEITADA (sofridos 0,75→1,33) — arquivada como gene | só vs adversário sem press |

## C. Validações/canais pendentes

| O quê | Como |
|---|---|
| **Bancada-patrick** (2º bot, mesma conta e cota) | subir patrick com genes defensivos rejeitados-no-espelho (gk_track; camper_shadow) e desafiar BotAdversario1 REAL — o sparring-espelho não julga bem genes defensivos (4 falsos-vereditos possíveis) |
| **v4×BotAdversario1 e v4k×BotAdversario9** | os 2 testes pendentes da quota de hoje (prioridades 1-2) |
| **v4s×level-3** | o teste da margem no desempate nº 1 (44 chutes/1 gol da v4 pede gate seletivo) |
| **level-2** | NUNCA medido em lugar nenhum — 1 jogo de quota |
| **BotAdversario6** | scouting do estilo posse (provável adversário de chave) |
| Confirmações wait roteirizadas | `bench/confirm_queue.sh` (herança da 1ª sessão, ainda válida p/ genes da v3) |
| **RL: condições de reabertura** | `results/RL_MOTHBALL_CONDICOES.md` (2 fixes de fidelidade no sim JAX + oponente forte destilado) — pós-torneio |

## Nota de método (o meta-insight da sessão)
Forma estática é ótimo local duro (4 famílias de mudança falharam); os ganhos vieram de
PAPÉIS EM JANELAS (kickoff, segunda bola, válvula) e de GATES com física correta
(slack vs GK forte). O backlog acima segue essa gramática: A1/A2 são janelas+gates
adaptativos, não formas novas.
