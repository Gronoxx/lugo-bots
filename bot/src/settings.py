"""Configuração do mapper e posições iniciais.

As posições iniciais derivam de BASE_FORMATION (tactics.py) para que a
formação inicial e a formação em jogo sejam consistentes.
"""

MAPPER_COLS = 20
MAPPER_ROWS = 10

# Convertido de tactics.BASE_FORMATION (frações) para a grade 20x10.
#
# ATENÇÃO: o servidor rejeita o registro ("invalid initial position") em
# dois casos, ambos descobertos na prática:
#   1. posição na metade adversária do campo (com 20 colunas: Col <= 9)
#   2. posição dentro do círculo neutro central (raio 1000 em torno de
#      10000,5000) — por isso Col 9/Row 4 falha: seu centro é (9500,4500),
#      a apenas 707d do meio do campo
# A formação em jogo (tactics.formation_position) pode avançar livremente;
# só o ponto de partida é restrito.
PLAYER_INITIAL_POSITIONS = {
    1:  {'Col': 1, 'Row': 4},   # goleiro
    2:  {'Col': 3, 'Row': 2},
    3:  {'Col': 3, 'Row': 4},
    4:  {'Col': 3, 'Row': 5},
    5:  {'Col': 3, 'Row': 7},
    6:  {'Col': 6, 'Row': 3},
    7:  {'Col': 5, 'Row': 4},
    8:  {'Col': 6, 'Row': 6},
    9:  {'Col': 9, 'Row': 2},
    10: {'Col': 8, 'Row': 4},
    11: {'Col': 9, 'Row': 7},
}
