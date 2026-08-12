"""
Parâmetros do bot, carregáveis em tempo de execução.

Motivo: a evolução precisa avaliar centenas de indivíduos. Reconstruir a imagem
Docker por indivíduo seria proibitivo, então UMA imagem lê seus parâmetros de
uma variável de ambiente (`BOT_PARAMS`, JSON) ou de um arquivo
(`BOT_PARAMS_FILE`). Sem nada definido, usa os valores atuais da v3.

Os valores abaixo são os que escolhi a olho ao escrever o bot — nenhum foi
otimizado. São exatamente o material que a evolução deve melhorar.

Uso:
    from params import P
    if d_goal <= P["dangerous_shot_range"]: ...
"""

import json
import os

# --- genes contínuos: valores da v3 (referência) ---------------------------
DEFAULTS = {
    # papéis
    "n_chasers": 2.0,              # quantos vão à bola (o baseline manda 11)
    "chase_margin": 5.0,          # folga (turnos) p/ soltar 1 chaser (chase_mode="adaptive")

    # finalização
    "dangerous_shot_range": 6000.0,   # além disto a bola chega fraca ao gol
    "shot_gk_penalty": 0.05,          # peso da distância no score do chute
    "shot_post_margin": 200.0,        # folga das traves ao mirar
    # afastamento lateral buscado antes de finalizar. Medido: chutes que
    # convertem 45% saem de |y-5000| ~1756; os que convertem 0%, de ~1050.
    "shot_lateral": 1750.0,
    # folga mínima do goleiro ao ponto de cruzamento para autorizar o chute.
    # Empírico: <1200 converteu 0% em 58 chutes; >1800 converteu 45%.
    "shot_min_gap": 1300.0,
    # xG mínimo para autorizar o chute quando shot_gate="xg" (modelo finishing.py)
    "shot_min_xg": 0.10,
    # gate TEMPORAL (shot_gate="slack"): slack = |alvo.y-gk.y| - (560+gk_reach_speed*t)
    "shot_min_slack": 0.0,     # autoriza o chute se slack > isto (calibrado: >0)
    "gk_reach_speed": 75.0,    # calibrado (AUC 0.87 vs gol). NÃO usar 200 (erro v6/v8)

    # passe
    "pass_min_dist": 800.0,
    "pass_speed_mult": 1.25,          # margem sobre a velocidade mínima
    "pass_w_clearance": 0.5,
    "pass_w_mate_pressure": 1.5,
    "pass_w_pressure_bonus": 900.0,
    "pass_margin": 500.0,
    # bônus de TROCA (switch): passar ao flanco OPOSTO em espaço, na área de
    # ataque, desloca o goleiro e abre ângulo. Default 0 = v9 (item 4 do plano).
    "pass_w_switch": 0.0,             # folga mínima da linha de passe

    # condução
    "carry_repulsion_radius": 2000.0,
    "carry_repulsion_weight": 1.2,
    "carry_step": 1500.0,

    # apoio (oferecer linha de passe)
    "support_near_holder": 2500.0,
    "support_radius_a": 900.0,
    "support_radius_b": 1600.0,
    "support_w_clearance": 2.0,
    "support_w_pressure": 2.0,

    # formação
    "shift_x": 0.30,                  # quanto a linha desliza com a bola
    "shift_y": 0.35,
    "aggression_support": 0.6,
    "aggression_defend": -0.4,
    "cover_mix": 0.30,                # quanto recuar em direção ao nosso gol

    # goleiro
    "gk_guard_out_far": 350.0,        # sair da linha p/ fechar ângulo
    "gk_guard_out_near": 200.0,
    "gk_threat_near": 1200.0,         # distância p/ considerar ameaça no gol
    "gk_y_range": 1100.0,
    "gk_jump_max_turns": 6.0,         # só pula se a bola chega em <= N turnos
    "gk_clearance_speed_mult": 1.3,

    # geral
    "pressure_radius": 2500.0,
}

# LIÇÃO (migração Linux, ago/2026): as versões (v3, v6, v8, v9) foram estados de
# CÓDIGO, e só a v9 ficou versionada no git — não dá para reproduzir a v3 a
# partir do repo, e a comparação v3×v9 vs level-1 dependeu de importar a imagem
# antiga do Mac. Daqui pra frente, toda mudança que DEFINE uma versão vira GENE
# aqui (como angle_seek e shot_min_gap), nunca código hardcoded — assim qualquer
# versão é reproduzível do repositório e a evolução pode explorá-la. Dívida
# concreta: o portão de finalização (física antiga da v3 → empírico da v9)
# deveria ser um gene shot_gate: "physics" | "empirical", não um if fixo em
# my_bot.py.
#
# Reforço (arquitetura, ago/2026): imagens Docker NÃO atravessam Mac (arm64) ↔
# Linux (amd64) — importar o mybot:v3 do Mac deu "exec format error". O canônico
# é SEMPRE o código no Git (reconstruível em qualquer arquitetura), nunca a
# imagem transferida. Mais uma razão para versão = gene, não código.
#
# --- genes discretos: qual implementação ocupa cada encaixe ----------------
# A evolução de ESTRUTURA muda estes. Cada valor é o nome de uma alternativa.
STRUCTURE_DEFAULTS = {
    # Busca de ângulo lateral antes de finalizar. DESLIGADA por padrão: a v8,
    # que a usava, perdeu 2,62 gols/partida para a v3 (n=16 cada, erro padrão
    # 0,59 — conclusivo). Fica como gene para a evolução reavaliar agora que o
    # portão de chute passou a abrir.
    "angle_seek": "off",                   # | on
    "holding_order": "shoot_pass_carry",   # | pass_shoot_carry
    "carry_mode": "hold",                  # | touch (chute soma à velocidade)
    "role_mode": "nearest_k",              # | zone
    "marking_mode": "cover",               # | man
    "keeper_mode": "line",                 # | sweeper
    # portão de finalização: limiar fixo na folga do goleiro (v9) ou modelo xG
    # de 4 features (bot/src/finishing.py, treinado vs level-1 amd64).
    "shot_gate": "threshold",              # | xg | slack
    # nº de chasers: fixo (v9) ou adaptativo (1 quando ganhamos com folga) — item 5
    "chase_mode": "fixed",                 # | adaptive
    # corrida ao poste oposto (movimentação sem bola): quando o portador está
    # avançado E aberto, UM atacante do flanco oposto corre ao 2º poste para
    # oferecer o alvo aberto que o funil mostra faltar (taxa good_chance ~0,42).
    # Determinístico sobre o estado compartilhado (não depende de comunicação, o
    # que inviabilizou o switch lateral do item 4). NÃO TESTADO — validar na proxy
    # antes de ligar. Default off = v9.
    "far_post_run": "off",                 # | on
}

# faixas admissíveis para mutação (min, max) — evita indivíduos absurdos
BOUNDS = {
    "n_chasers": (1.0, 5.0),
    "chase_margin": (1.0, 20.0),
    "dangerous_shot_range": (2000.0, 8000.0),
    "shot_gk_penalty": (0.0, 0.5),
    "shot_post_margin": (50.0, 700.0),
    "shot_lateral": (0.0, 3500.0),
    "shot_min_gap": (0.0, 2600.0),
    "shot_min_xg": (0.0, 0.6),
    "shot_min_slack": (-500.0, 1500.0),
    "gk_reach_speed": (0.0, 200.0),
    "pass_min_dist": (300.0, 3000.0),
    "pass_speed_mult": (1.0, 2.0),
    "pass_w_clearance": (0.0, 3.0),
    "pass_w_mate_pressure": (0.0, 6.0),
    "pass_w_pressure_bonus": (0.0, 4000.0),
    "pass_margin": (150.0, 1500.0),
    "pass_w_switch": (0.0, 5.0),
    "carry_repulsion_radius": (500.0, 5000.0),
    "carry_repulsion_weight": (0.0, 4.0),
    "carry_step": (400.0, 4000.0),
    "support_near_holder": (800.0, 5000.0),
    "support_radius_a": (300.0, 2500.0),
    "support_radius_b": (600.0, 4000.0),
    "support_w_clearance": (0.0, 6.0),
    "support_w_pressure": (0.0, 6.0),
    "shift_x": (0.0, 0.8),
    "shift_y": (0.0, 0.8),
    "aggression_support": (-1.0, 1.5),
    "aggression_defend": (-1.5, 1.0),
    "cover_mix": (0.0, 0.9),
    "gk_guard_out_far": (0.0, 1300.0),
    "gk_guard_out_near": (0.0, 1300.0),
    "gk_threat_near": (400.0, 4000.0),
    "gk_y_range": (200.0, 1450.0),
    "gk_jump_max_turns": (1.0, 20.0),
    "gk_clearance_speed_mult": (1.0, 2.0),
    "pressure_radius": (800.0, 6000.0),
}

STRUCTURE_OPTIONS = {
    "holding_order": ["shoot_pass_carry", "pass_shoot_carry"],
    "carry_mode": ["hold", "touch"],
    "role_mode": ["nearest_k", "zone"],
    "marking_mode": ["cover", "man"],
    "keeper_mode": ["line", "sweeper"],
    "angle_seek": ["off", "on"],
    "shot_gate": ["threshold", "xg", "slack"],
    "chase_mode": ["fixed", "adaptive"],
    "far_post_run": ["off", "on"],
}


def _load() -> dict:
    p = dict(DEFAULTS)
    p.update(STRUCTURE_DEFAULTS)

    raw = os.environ.get("BOT_PARAMS")
    if not raw:
        path = os.environ.get("BOT_PARAMS_FILE")
        if path and os.path.exists(path):
            with open(path) as f:
                raw = f.read()
    if raw:
        try:
            override = json.loads(raw)
            unknown = set(override) - set(p)
            if unknown:
                print(f"params: chaves ignoradas (desconhecidas): {sorted(unknown)}")
            p.update({k: v for k, v in override.items() if k in p})
        except Exception as e:
            # nunca deixar um genoma malformado derrubar o bot: cai no padrão
            print(f"params: BOT_PARAMS inválido ({e}); usando padrões")

    # respeitar as faixas mesmo se o genoma vier fora delas
    for k, (lo, hi) in BOUNDS.items():
        if k in p and isinstance(p[k], (int, float)):
            p[k] = max(lo, min(hi, float(p[k])))
    return p


P = _load()


def genome_id() -> str:
    """Identificador curto do genoma, para rastrear qual indivíduo jogou."""
    import hashlib
    blob = json.dumps({k: P[k] for k in sorted(P)}, sort_keys=True)
    return hashlib.sha1(blob.encode()).hexdigest()[:8]
