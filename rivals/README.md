# rivals/ — painel de adversários reais

Durante o projeto, bots públicos de outros participantes foram clonados para cá e
transformados em imagens Docker (`bench/build_rivals.sh`), formando um painel de
adversários para medir o nosso bot contra algo que não fosse o baseline oficial.

**O código deles foi removido deste repositório — inclusive do histórico — e os
nomes não são citados.** São trabalhos de outras pessoas, a maioria sem licença
declarada (o default legal é "todos os direitos reservados"), e não cabe
redistribuí-los nem expô-los aqui. Nos scripts e relatórios eles aparecem apenas
como `rival_p1`…`rival_p4` / `Participante1`…`Participante9`.

Para reconstruir um painel equivalente, clone bots públicos de participantes para
dentro deste diretório (um subdiretório por bot) e rode:

```bash
bash bench/build_rivals.sh
```

O script **não** usa o Dockerfile de cada bot: vários dependem de um contexto de
build fora do diretório e nenhum espera o servidor aceitar conexões antes de subir.
Ele gera um Dockerfile comum com um entrypoint que aguarda a porta do servidor — sem
isso parte do time não conecta e a partida é perdida por W.O.

## Observação sobre o `clones/`

O diretório `clones/muralha_vertical/` **não** é código de terceiro: é uma
reimplementação nossa, escrita a partir da observação do vídeo de uma partida, para
servir de sparring local. O cabeçalho do arquivo descreve o comportamento observado
que ela reproduz.
