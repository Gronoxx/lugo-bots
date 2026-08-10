"""
Simulação de condução da bola: carregar vs. tocar à frente.

Ponto crítico das specs: "The kick velocity is SUMMED to the current ball
velocity". Tocar a bola enquanto se mantém contato acelera a bola.
O jogador PERSEGUE a bola (não a ultrapassa) — modelo 1D na direção do ataque.
"""

from physics import (BALL_DECELERATION, BALL_MAX_SPEED, BALL_MIN_SPEED,
                     PLAYER_MAX_SPEED, TOUCH_RADIUS)


def carry(turns: int) -> float:
    """Conduzir segurando a bola: a bola anda junto com o jogador."""
    return turns * PLAYER_MAX_SPEED


def touch_dribble(kick: float, turns: int, verbose=False):
    """Toca a bola à frente com força `kick` sempre que estiver em contato.

    - jogador persegue a bola a até PLAYER_MAX_SPEED (nunca a ultrapassa)
    - bola desacelera BALL_DECELERATION por turno
    - em contato (gap <= TOUCH_RADIUS) o jogador soma `kick` à velocidade da bola

    Retorna (avanço da bola, nº de turnos sem contato).
    """
    ball_x = ball_v = player_x = 0.0
    lost = 0
    for t in range(turns):
        gap = ball_x - player_x
        in_contact = gap <= TOUCH_RADIUS
        if in_contact:
            ball_v = min(ball_v + kick, BALL_MAX_SPEED)
        else:
            lost += 1
        if ball_v > BALL_MIN_SPEED:
            ball_x += ball_v
            ball_v = max(0.0, ball_v - BALL_DECELERATION)
        else:
            ball_v = 0.0
        # o jogador corre atrás da bola, sem ultrapassá-la
        player_x += min(PLAYER_MAX_SPEED, max(0.0, ball_x - player_x))
        if verbose and t < 15:
            print(f"    t={t:>2} bola={ball_x:>7.0f} v={ball_v:>6.1f} "
                  f"jog={player_x:>7.0f} gap={ball_x-player_x:>5.0f} "
                  f"{'contato' if in_contact else 'perseguindo'}")
    return ball_x, lost


print("=" * 70)
print("CONDUÇÃO: CARREGAR vs TOCAR À FRENTE")
print("=" * 70)
print(f"\nRaio de contato: {TOUCH_RADIUS:.0f}d | Jogador: {PLAYER_MAX_SPEED:.0f} d/f")
print("Regra-chave: o chute SOMA à velocidade atual da bola.\n")

for HORIZON in (20, 40, 60):
    print(f"--- Horizonte de {HORIZON} turnos (carregar = {carry(HORIZON):.0f}d) ---")
    print("  toque | avanço | s/ contato | vs carregar")
    rows = []
    for kick in (20, 30, 40, 50, 60, 70, 80, 100, 120, 150, 200, 400):
        adv, lost = touch_dribble(kick, HORIZON)
        rows.append((kick, adv, lost))
        print(f"  {kick:>5} | {adv:>6.0f} | {lost:>10} | {adv/carry(HORIZON):>6.2f}x")
    best = max(rows, key=lambda r: r[1])
    print(f"  => melhor: toque={best[0]} -> {best[1]:.0f}d "
          f"({best[1]/carry(HORIZON):.2f}x carregar), {best[2]} turnos sem contato\n")

print("Detalhe (toque=40, 15 primeiros turnos):")
touch_dribble(40, 40, verbose=True)

print("\n" + "=" * 70)
print("CONCLUSÃO")
print("=" * 70)
adv40, lost40 = touch_dribble(40, 40)
adv_carry = carry(40)
print(f"""
Em 40 turnos: carregar avança {adv_carry:.0f}d; tocar a 40 d/f avança {adv40:.0f}d
({adv40/adv_carry:.2f}x), com {lost40} turnos em que a bola está solta à frente.

Trade-off real: a bola solta é interceptável. O toque é vantajoso em campo
aberto (sem adversário na trajetória) e perigoso sob pressão. A decisão
"carregar vs tocar" deve depender da distância do adversário mais próximo
à linha de condução — é exatamente aí que um modelo aprendido supera
regras fixas.
""")
