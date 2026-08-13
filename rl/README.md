# rl/ — ponte fastsim ↔ my_bot e caminho para o treinador de RL

Ver o plano completo em `results/PLANO_RL_FASTSIM.md` e o vault (`lugo-rl-plan`,
`lugo-fastsim`, `lugo-env-reference`).

## Estado (Etapa 1 — fundação)

**Ponte pronta e validada** (`rl/bridge/`): roda o `my_bot` EXATO dentro do
`sim/fastsim.py` via `GameSnapshotInspector` real (sem gRPC/Docker).
- `snapshot.py` — `State → server_pb2.GameSnapshot`.
- `orders.py` — `Order` protobuf → dict do fastsim.
- `heuristic_policy.py` — `make_heuristic_policy() → policy(state, side)`.
- `smoke_test.py` — `.venv/bin/python rl/bridge/smoke_test.py`.
- Velocidade: ~13-15 s por partida de 6000 turnos (~4× o docker; os "43×" do
  plano eram só física com políticas de brinquedo, sem a decisão do bot no loop).

**Fidelidade do sim corrigida contra replays reais** (`sim/fastsim.py`, commit
e5008c6): goleiro preso à linha; bola 200d à frente do dono; roubo por
proximidade → troca de posse ~34% dos turnos (IGUAL ao servidor real); raio de
pegada do goleiro 560; empurrão de 1400 do gol confirmado fiel. Física de
voo-livre intacta.

## Dois bloqueios do "backend rápido de evolução" (honesto)

O plano previa plugar o fastsim como backend do `bench/evolve.py` para A/B de
genes ~4× mais rápido. Isso esbarra em dois pontos de design:

1. **O level-1 não existe no sim.** A fitness da evolução é `saldo vs
   lugobots/level-1`, que é uma **imagem docker** sem código/política acessível.
   O fastsim só sabe pôr heurísticas/redes umas contra as outras (dummy, my_bot,
   ou nets treinadas). Logo **eval vs level-1 SEMPRE precisa do docker** — o
   fastsim serve para **self-play / vs my_bot**, que é exatamente o regime de
   treino do RL (não é limitação para o RL; é uma correção ao que o backend de
   evolução podia fazer).

2. **`params.P` é global, carregado uma vez** (`bot/src/params.py: P = _load()`
   lê `BOT_PARAMS` no import). Dois genomas diferentes NÃO podem jogar no mesmo
   processo (ambos os lados compartilham o mesmo `P`). Um A/B genoma-vs-genoma
   in-process exigiria params **por instância** de bot (um refactor pequeno e
   limpo em `params.py`/`my_bot.py`). Enquanto isso, cada genoma roda num
   processo isolado com seu `BOT_PARAMS` (como o docker), sem jogar contra o outro.

**Conclusão:** para o RL (o objetivo), a ponte já cumpre seu papel — fornece o
`my_bot` (v9 default) como oponente roteirizado no sim e valida a fidelidade.
O A/B heurístico genoma-vs-genoma rápido fica pendente do refactor de params
por-instância (em arquivos que o usuário está editando).

## Próximo (conforme o plano)
- Validação distribucional sim-vs-docker quando o `my_bot.py` estabilizar (Etapa 1, portão).
- Etapa 2: reescrever `step` em JAX (jit+vmap+scan) para GPU; gate JAX↔escalar.
