"""Extrai as consequências táticas da física do Lugo."""

from physics import *

print("=" * 68)
print("ANÁLISE FÍSICA DO LUGO — consequências táticas")
print("=" * 68)

print(f"\nCampo: {MAX_X} x {MAX_Y} | Gol: y de {GOAL_MIN_Y:.0f} a {GOAL_MAX_Y:.0f}")
print(f"Partida: {GAME_TURNS} turnos = {GAME_TURNS/FPS:.0f}s | Shot clock: {SHOT_CLOCK_TIME} turnos")

# 1. Alcance do chute
print("\n" + "-" * 68)
print("1. ALCANCE DO CHUTE")
print("-" * 68)
dist_max, turns_max = ball_travel(BALL_MAX_SPEED)
print(f"Chute máximo (v0={BALL_MAX_SPEED:.0f}): {dist_max:.0f}d em {turns_max} turnos")
print(f"  -> cobre {100*dist_max/MAX_X:.0f}% do comprimento do campo")
print(f"  -> do meio-campo (x=10000) ao gol são 10000d: {'ALCANÇA' if dist_max>=10000 else 'NÃO ALCANÇA'}")
print("\n  v0 | alcance | turnos")
for v0 in (100, 150, 200, 250, 300, 350, 400):
    d, t = ball_travel(v0)
    print(f"  {v0:>3} | {d:>7.0f} | {t:>3}")

# 2. Distância máxima de finalização
print("\n" + "-" * 68)
print("2. DE ONDE DÁ PARA FINALIZAR (bola chega ao gol com velocidade útil)")
print("-" * 68)
for min_arrival in (400, 300, 200, 100):
    # v0=400; queremos a distância na qual a bola ainda tem min_arrival de velocidade
    d = 0.0
    v = BALL_MAX_SPEED
    while v > min_arrival:
        d += v
        v -= BALL_DECELERATION
    print(f"  chegando a >= {min_arrival:>3} d/f de velocidade: distância máx {d:>6.0f}d")

# 3. Chute-e-persegue vs condução
print("\n" + "-" * 68)
print("3. CHUTE-E-PERSEGUE vs CONDUÇÃO  (condução = 100 d/f)")
print("-" * 68)
best_v = self_pass_max_speed()
print(f"Maior v0 auto-recuperável: {best_v:.0f} d/f")
print("\n  v0 | alcance | turnos p/ recuperar | avanço efetivo | ganho")
best = (0, 0)
for v0 in range(20, 260, 20):
    d, _ = ball_travel(v0)
    need = max(0.0, d - TOUCH_RADIUS)
    tr = math.ceil(need / PLAYER_MAX_SPEED)
    rate = effective_advance_rate(v0)
    if rate > best[1]:
        best = (v0, rate)
    flag = " <<<" if rate > PLAYER_MAX_SPEED else ""
    print(f"  {v0:>3} | {d:>7.0f} | {tr:>18} | {rate:>13.1f} | {rate/PLAYER_MAX_SPEED:>4.2f}x{flag}")
print(f"\n  ÓTIMO: v0={best[0]} -> {best[1]:.0f} d/f efetivo ({best[1]/PLAYER_MAX_SPEED:.2f}x a condução)")

# 4. Passe vs corrida
print("\n" + "-" * 68)
print("4. PASSE vs CORRIDA (quantos turnos para cobrir X)")
print("-" * 68)
print("  distância | bola (v0 ótimo) | jogador correndo | vantagem")
for dist in (1000, 2000, 3000, 5000, 8000):
    v0 = speed_to_reach(dist)
    if v0 is None:
        print(f"  {dist:>9} | inalcançável em 1 chute | {dist/PLAYER_MAX_SPEED:>16.0f} | -")
        continue
    tb = turns_for_ball(v0, dist)
    tp = dist / PLAYER_MAX_SPEED
    print(f"  {dist:>9} | {tb:>15} | {tp:>16.0f} | {tp/tb:>6.1f}x")

# 5. Goleiro
print("\n" + "-" * 68)
print("5. GOLEIRO")
print("-" * 68)
print(f"Gol tem {GOAL_WIDTH:.0f}d de largura. Goleiro cobre (corpo) {PLAYER_SIZE}d parado.")
jump_reach = GOALKEEPER_JUMP_SPEED * GOALKEEPER_JUMP_DURATION
print(f"Pulo: {GOALKEEPER_JUMP_SPEED:.0f} d/f x {GOALKEEPER_JUMP_DURATION} turnos = {jump_reach:.0f}d de alcance")
print(f"  -> com o pulo cobre {100*(jump_reach*2+PLAYER_SIZE)/GOAL_WIDTH:.0f}% do gol se antecipar o lado")
print(f"  -> MAS o pulo não pode ser interrompido ({GOALKEEPER_JUMP_DURATION} turnos): errar o lado = gol certo")
bola_cruza = GOAL_WIDTH / BALL_MAX_SPEED
print(f"Bola a {BALL_MAX_SPEED:.0f} d/f cruza a largura do gol em {bola_cruza:.1f} turnos")

# 6. Janela de reação
print("\n" + "-" * 68)
print("6. JANELA DE REAÇÃO DO DEFENSOR")
print("-" * 68)
print("  Um chute a 400 d/f vindo de distância D: turnos até chegar")
for D in (1000, 2000, 3000, 4000, 6000):
    t = turns_for_ball(BALL_MAX_SPEED, D)
    print(f"  D={D:>5}: {t:>2} turnos -> defensor corre no máx {t*PLAYER_MAX_SPEED:>5.0f}d nesse tempo")

# 7. Densidade
print("\n" + "-" * 68)
print("7. OCUPAÇÃO DO CAMPO")
print("-" * 68)
area = MAX_X * MAX_Y
per_player = area / 22
print(f"Área: {area/1e6:.0f}M d². Por jogador (22): {per_player/1e6:.1f}M d²")
print(f"Raio médio livre por jogador: {math.sqrt(per_player/math.pi):.0f}d")
print(f"Raio de contato com a bola: {TOUCH_RADIUS:.0f}d")
print(f"  -> o campo é ESPARSO: espaço livre é ~{math.sqrt(per_player/math.pi)/TOUCH_RADIUS:.0f}x o raio de contato")
print(f"Zona do gol (raio {GOAL_ZONE_RANGE}d): adversário não entra -> área franca para o goleiro")
