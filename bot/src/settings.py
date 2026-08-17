"""Configuração do mapper e posições iniciais.

As posições iniciais derivam de BASE_FORMATION (tactics.py) para que a
formação inicial e a formação em jogo sejam consistentes.

P2 (2026-08-16): o REINÍCIO é 100% determinístico — os 22 teleportam para a
init_position exata e o 1º toque acontece em reset+13 (quem tem o jogador mais
perto do centro ganha a bola em TODO reinício; empate vs bots da nossa classe).
Por isso a tabela virou GENE (`init_variant`):
  - "v3"    (default): tabela original, grade 20×10; #10 a 1581 do centro.
  - "kick9": #9 vai a (9500,3500) — MESMA distância do centro que o #10 →
             dois homens chegam juntos = tabela imediata no kickoff.
  - "fine":  grade 200×100 (células de 100) — kick9 + #10 a (9950,3950),
             a 1051 do centro → toca em reset+8, 5 turnos antes de qualquer
             grade 20×10. Precisa de SONDA (o servidor valida o PONTO; regras
             conhecidas abaixo valem, mas a plataforma pode divergir do local).

ATENÇÃO: o servidor rejeita o registro ("invalid initial position") em
dois casos, ambos descobertos na prática:
  1. posição na metade adversária do campo
  2. posição dentro do círculo neutro central (raio 1000 em torno de
     10000,5000)
A formação em jogo (tactics.formation_position) pode avançar livremente;
só o ponto de partida é restrito.
"""
from params import P

# Coordenadas ABSOLUTAS (lado HOME; o mapper espelha para AWAY) por variante.
# v3 = a tabela histórica (grade 20×10, centros de célula).
_COORDS_V3 = {
    1:  (1500, 4500),    # goleiro (o servidor o força para (0,5000))
    2:  (3500, 2500),
    3:  (3500, 4500),
    4:  (3500, 5500),
    5:  (3500, 7500),
    6:  (6500, 3500),
    7:  (5500, 4500),
    8:  (6500, 6500),
    9:  (9500, 2500),
    10: (8500, 4500),
    11: (9500, 7500),
}

_VARIANT = P.get("init_variant", "v3")

_COORDS = dict(_COORDS_V3)
if _VARIANT in ("kick9", "fine"):
    _COORDS[9] = (9500, 3500)        # d=1581 do centro (legal; >1000 do círculo)
if _VARIANT == "fine":
    # SONDA 2026-08-16: (9950,3950) d=1051 foi REJEITADO pelo servidor (o raio
    # de exclusão real é >1051, não os 1000 documentados) e a partida inteira
    # virou W.O. — o risco de beirar o limite é a PARTIDA, não só o jogador.
    _COORDS[10] = (9950, 3550)       # d=1451 do centro (testa fronteira ~1400)
if _VARIANT == "sym":
    # Conserto do BUG de quantização (achado do usuário, 2026-08-16): a
    # BASE_FORMATION centra #7 e #10 em y=0,50 (=5000), mas a grade 20×10 não
    # expressa 5000 e arredondou ambos p/ 4500 — a assimetria nos resets nunca
    # foi escolha. Grade 20×25 (células 1000×400): #7/#10 centrados; #10 a
    # (8500,5000) = 1500 do centro (< 1581 do espelho ⇒ ganha o kickoff de
    # QUALQUER clone da classe; 1500>1451 já provado legal); #9 aproximado
    # (9500,3400). Demais y re-quantizados (±100, irrelevante).
    _COORDS.update({
        1:  (1500, 4600),
        2:  (3500, 2600),
        3:  (3500, 4600),
        4:  (3500, 5400),
        5:  (3500, 7400),
        6:  (6500, 3400),
        7:  (5500, 5000),
        8:  (6500, 6600),
        9:  (9500, 3400),
        10: (8500, 5000),
        11: (9500, 7400),
    })

if _VARIANT == "fine":
    MAPPER_COLS = 200
    MAPPER_ROWS = 100
elif _VARIANT == "sym":
    MAPPER_COLS = 20
    MAPPER_ROWS = 25
else:
    MAPPER_COLS = 20
    MAPPER_ROWS = 10

_CW = 20000.0 / MAPPER_COLS
_RH = 10000.0 / MAPPER_ROWS

# Converte coordenada absoluta → célula da grade (o centro da célula reproduz
# a coordenada quando ela é múltiplo de meia-célula, caso de todas as tabelas).
PLAYER_INITIAL_POSITIONS = {
    n: {'Col': int(x // _CW), 'Row': int(y // _RH)}
    for n, (x, y) in _COORDS.items()
}
