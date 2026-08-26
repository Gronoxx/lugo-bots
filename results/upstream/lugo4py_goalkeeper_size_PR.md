Oi! Esbarrei nisso escrevendo um bot para a competição.

## O problema

`GOALKEEPER_SIZE` está definida com uma vírgula no fim, então a constante é uma
tupla de um elemento em vez de um número. Qualquer conta com ela levanta
`TypeError`:

```python
from lugo4py import specs

repr(specs.GOALKEEPER_SIZE)   # '(919.9999999999999,)'
specs.GOALKEEPER_SIZE / 2     # TypeError: unsupported operand type(s) for /: 'tuple' and 'int'
```

Em `src/lugo4py/src/specs.py`:

```python
GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,
#                                  ^ esta vírgula
```

Como o `__init__.py` faz `from .src.specs import *`, ela também chega como
`lugo4py.GOALKEEPER_SIZE`, ao lado de `lugo4py.PLAYER_SIZE`, que funciona
normalmente. Nada dentro do pacote consome a constante — só quem escreve bot —,
por isso o import nunca falha.

Os clientes Go e JS definem o mesmo valor corretamente; no literal de objeto do
JS a vírgula é só um separador de propriedades, e a versão Python parece ter
vindo dali na transliteração.

## A correção

Remove a vírgula. Depois da mudança:

```python
repr(specs.GOALKEEPER_SIZE)   # '919.9999999999999'
specs.GOALKEEPER_SIZE / 2     # 459.99999999999994
```

Mantive a expressão `PLAYER_SIZE * 2.3` em vez de escrever `920` para o valor
continuar idêntico ao do cliente JS e para a constante acompanhar `PLAYER_SIZE`
caso ele mude.
