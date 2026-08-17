# RL — encerramento para o torneio e condições de reabertura

> Decisão ratificada pelo usuário (2026-08-16), após o relatório final da sessão de RL
> (results/RL_RESULTADOS_2026-08-14.md): teto estrutural do RL-em-JAX provado nos dois
> caminhos (do zero E módulo sobre o v9). Este arquivo registra o estado e as condições
> objetivas de reabertura. (A nota pertence conceitualmente a rl/README.md em ~/lugo-bots;
> está aqui porque o rl/ vive no branch da sessão de RL — mesclar no próximo merge.)

## Decisão
1. **Encerrado o treino RL-em-JAX para este torneio.** EV de novas runs ≈ 0 (comprovado):
   o sim JAX não tem oponente forte fiel (v9 não roda no batch; o melhor oponente JAX
   perde 0×12/0×19 do v9) nem goleiro/zona corretos — sem sinal válido para superar o v9
   nem para aprender finalização.
2. **Infra preservada (mothball)**: sim vetorizado (45M steps/s), MAPPO/CTDE, eval/duel,
   adaptador de deploy, checkpoints (`rl/checkpoints/policy_rl_best.pkl` etc.). Nada é
   apagado; nada roda.
3. **Esforço de aprendizado redirecionado** para o P6 do programa tático (opcional):
   modelo-de-oponente OFFLINE sobre replays reais (padrão finishing.py; gene
   `veto_model=learned` relaxando o pior-caso dos vetos — gap medido de até 27pp).

## Condições de reabertura (objetivas, AMBAS necessárias)
- **(a) Fidelidade do sim JAX**: portar a `rl/jax/step.py` os fixes que o sim escalar já
  recebeu — goleiro travado em x na linha (provado por sonda no servidor real) com alcance
  560 e pulo 200×3; zona-1400 nos DOIS gols; catch por PROXIMIDADE (~300) em vez de argmin
  — e passar o gate JAX↔escalar (física idêntica em partidas completas).
- **(b) Oponente forte fiel no loop JAX**: v9 destilado com mecânica casada (DAgger — BC
  puro já falhou por distribution shift) OU corpus de fricção real gerado pela ponte
  escalar (v9 real vs política exportada), validado: o clone segura ≥ empate vs v9 no
  fastsim escalar.
- **Gate final antes de reinvestir**: política treinada no JAX mantém o desempenho ao ser
  avaliada no sim ESCALAR (rl/eval/eval_vs_v9.py) — sem isso, qualquer ganho é artefato.

## O que o RL já entregou e o programa tático USA
- Diagnóstico convergente com a heurística: o gargalo competitivo é criação+finalização
  vs defesas fortes (~75% dos chutes salvos) → P1 do programa (manobra de goleiro na
  régua certa).
- Ferramentas reutilizáveis fora do treino: ponte escalar my_bot↔fastsim, duel.py,
  diag.py, lições de reward (esforço-based, não-farmável).
