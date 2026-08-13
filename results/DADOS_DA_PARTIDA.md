# Dados da partida — SUPERSEDIDO

Este rascunho foi substituído pela referência definitiva e verificada:
**[results/REFERENCIA_LUGO.md](REFERENCIA_LUGO.md)** (mineração do lugo4py + medição
contra 221 replays reais).

Motivo: este rascunho afirmava "deslocamento por turno = velocidade atual", que a
medição REFUTOU — o correto é o modelo trapezoidal `deslocamento = velocidade − 5`
(metade da deceleração), já usado em `geometry.py:ball_step`.
