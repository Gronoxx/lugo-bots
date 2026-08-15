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
    # PISO de potência de CHEGADA usando a velocidade REAL de saída do chute
    # (achievable_shot_speed). 0 = inerte (=v9); 200 <=> alcance efetivo 6000
    # (= dangerous_shot_range). Problema 2 (chute fraco / em cima do goleiro).
    "shot_arrival_min": 0.0,

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
    # --- posse objetiva (Problema 1) + interceptação velocity-aware. Todos =v9. ---
    "pass_w_intercept": 0.0,        # peso da folga de interceptação no score (0=v9)
    "pass_min_score": 0.0,          # limiar de aceitação do passe (v9: best_score=0.0)
    "pass_w_overmark": 0.0,         # penalidade por marcação do receptor ACIMA do limiar
    "pass_mark_threshold": 0.0,     # limiar de marcação (_pressure_on) do receptor
    "pass_backward_floor": 20000.0, # recuo acima disto só passa sob pressão (20000=nunca=v9)
    "pass_retain_pressure": 1.2,    # pressão sobre o portador p/ ativar retenção
    "pass_retain_turns": 3.0,       # turnos até um oponente alcançar o portador (gatilho)
    "pass_retain_advance_w": 0.8,   # peso do avanço no score do passe de retenção
    "pass_retain_backmax": 3000.0,  # recuo MÁXIMO de retenção E teto p/ o bônus de segurança
    # corrida no destino (gene pass_endpoint_race): margem em TURNOS que o
    # receptor pode chegar DEPOIS de um adversário ao ponto de recepção antes de
    # a linha ser descartada. 0 = o receptor precisa ganhar a corrida; >0 tolera.
    "pass_endpoint_margin": 0.0,

    # --- status por jogador / "quando passar" (Componente 1). Inertes com
    # pass_status_mode="off" (=v9). turns_for_player(D)=(D-300)/100 => bandas:
    # perigo t<=2 (D<=500), atencao t<=3 (D<=600), livre acima. ---
    "status_danger_turns": 2.0,       # t<=isto => perigo (escape prioritario)
    "status_attention_turns": 3.0,    # t<=isto => atencao (liga retencao)
    "pass_min_score_free": 0.0,       # barra de aceite quando LIVRE (v9=0.0)
    "pass_min_score_attention": 0.0,  # barra quando ATENCAO (v9=0.0)
    "pass_min_score_danger": -3000.0, # barra quando PERIGO (aceita passe seguro)
    "pass_w_recv_free": 0.0,          # bonus/penal. por status do receptor (0=v9)

    # --- planejador nao-guloso (Componente 2). Inertes com pass_lookahead="off". ---
    "plan_beam": 6.0,                 # largura do feixe
    "plan_w_progress": 1.0,           # peso do progresso ao gol (unid. distancia)
    "plan_w_shot": 3.0,               # peso do bonus de chute com folga do goleiro
    "plan_w_livre": 1500.0,           # bonus por terminar em posicao livre
    "plan_leg_penalty": 40.0,         # custo por turno global da cadeia (anti-cadeia-longa)
    "plan_margin_turns": 0.0,         # folga minima de interceptacao por perna (turnos)
    "plan_margin_value": 500.0,       # ganho minimo sobre segurar p/ acionar o passe
    "plan_control_turns": 1.0,        # turnos p/ assentar a bola antes do passe pleno
    "plan_trigger_turns": 3.0,        # so planeja se o portador esta MARCADO (adv de linha <= isto); livre => dribla

    # --- tatica por estado de jogo (Componente 3, PRIORIDADE BAIXA). Inerte com
    # game_state_mode="off". Calibrado: real ~2,9 gols/jogo, Lugo ~4,7-6,9 =>
    # 'vantagem confortavel' ~3-4 gols. ---
    "lead_comfortable": 3.0,          # margem (gols) = vantagem confortavel
    "late_game_turns": 1200.0,        # ultimos N turnos contam como "fim de jogo"
    "game_aggr_scale": 300.0,         # deslocamento da barra de passe por unid. de aggr

    # --- conducao/marcacao por AREA (hold_logic="caso"). Inertes com defaults v9. ---
    "mark_t_max": 5.0,                # horizonte (turnos) da area de conducao segura
    "mark_n_dirs": 24.0,             # direcoes amostradas na area
    "mark_free_frac": 0.5,            # fwd>isto => livre rumo ao gol
    "mark_trapped_frac": 0.15,        # area total < isto => PRESO (precisa passar)

    # --- FINALIZACAO (finish_mode="on"). Inertes com finish_mode off (=v9). ---
    "finish_sure_slack": 0.0,         # Caso 1: chuta se slack do goleiro > isto (0=vence)
    "finish_run_range": 2000.0,       # Caso 2: raio do goleiro p/ iniciar a manobra/corridas
    "finish_w_cover": 1.0,            # peso da liberdade (cobertura) no ponto de corrida
    "finish_w_slack": 1.0,            # peso do angulo de chute (slack) no ponto de corrida

    # --- COBERTURA anti-banheira (cover_mode="on"). Inertes com off (=v9). ---
    "cover_count": 2.0,               # quantos zagueiros ficam marcando os parados
    "cover_range": 8000.0,            # adversario a <=isto do NOSSO gol = "no nosso campo"
    "cover_dist": 600.0,              # ficar isto goal-side do atacante coberto

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
    # apoio ATIVO (support_mode="offer"): recebedores que sobem oferecendo linha.
    # Inertes com support_mode="v9" (default) — não afetam a v9.
    "support_n_forward": 2.0,        # quantos apoiadores viram recebedores (FUSÍVEL)
    "support_advance": 2500.0,       # distância à frente do portador (rumo ao gol)
    "support_channel_width": 1800.0, # afastamento lateral dos canais (LARGURA)
    "support_off_w_advance": 1.0,
    "support_off_w_clear": 2.0,
    "support_off_w_press": 1500.0,
    "support_off_w_crowd": 1.0,      # anti-amontoamento (A/B inicial: setar 0)
    "support_crowd_radius": 2200.0,
    "support_off_search_r": 800.0,

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
    # veto/risco de interceptação sensível à velocidade do oponente e à
    # velocidade de CHEGADA da bola. off = física v9 (opponent_can_intercept).
    # on = SÓ ACRESCENTA ameaça (min(pos_atual,pos_extrapolada)+dwell+densa) —
    # nunca libera veto (jogador Lugo não tem inércia). Default off = v9.
    "use_velocity": "off",                 # | on
    # retenção de posse sob pressão (passe lateral/trás LIMITADO). off = v9.
    "pass_retain": "off",                  # | on
    # C3 corrida no destino: descarta o passe se um adversário chega ao ponto de
    # recepção antes do receptor (+pass_endpoint_margin). Tapa a recepção
    # disputada que a linha "limpa em trânsito" não enxerga. off = v9.
    "pass_endpoint_race": "off",           # | on
    # segurança do passe com a velocidade REALMENTE executada por kick_to (a
    # redução por ângulo + soma à velocidade da bola pode entregar menos que a
    # planejada, dando tempo ao adversário). off = v9 (checa com a planejada).
    "pass_exec_speed": "off",              # | on
    # tempo de chegada do passe pela distância de CONTATO (d - TOUCH_RADIUS): a
    # bola completa o passe ao TOCAR o receptor (spec), não no centro. Corrige o
    # lead (projeção do receptor) por ~raio jogador+bola. off = v9 (usa o centro).
    "pass_touch_lead": "off",              # | on
    # status por jogador / "quando passar" (Componente 1). off = v9 byte-a-byte.
    "pass_status_mode": "off",             # | on  (chave-mestra do Componente 1)
    "status_count_gk": "off",              # | on  (conta GK adversario, reach 560)
    "status_measure": "player",            # | ball (mede ~200 a frente, rumo ao gol)
    # planejador nao-guloso (Componente 2). off = v9 (nunca chamado).
    "pass_lookahead": "off",               # | depth2 | depth3
    "pass_control": "off",                 # | on (aresta de controle/first-touch)
    "game_state_mode": "off",              # | on (tatica por placar/tempo, Comp 3)
    # conducao/marcacao por AREA + hierarquia de Casos (spec do usuario). v9 = cascata antiga.
    "hold_logic": "v9",                    # | caso  (Caso 1/2.a/2.b em on_holding)
    "status_metric": "radius",             # | area  (marcacao por raio [Comp1] ou por area)
    "pass_recv_gate": "off",               # | on    (receptor marcado = rele/abre-angulo, nao destino)
    "caso_pass_priority": "pass_first",    # | dribble_first (passe p/ frente antes ou depois do drible seguro)
    "finish_mode": "off",                  # | on  (Caso 1/2/3 de finalizacao: manobrar o goleiro)
    "cover_mode": "off",                   # | on  (cobertura anti-banheira: zagueiros atras dos parados)
    # movimentação sem bola ativa (recebedores sobem oferecendo linha).
    # "v9" = _support_offer em anel ao redor do apoiador. Default v9 = idêntico.
    "support_mode": "v9",                  # | offer
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
    "shot_arrival_min": (0.0, 400.0),
    "pass_w_intercept": (0.0, 3.0),
    "pass_min_score": (-3000.0, 3000.0),
    "pass_w_overmark": (0.0, 6.0),
    "pass_mark_threshold": (0.0, 5.0),
    "pass_backward_floor": (500.0, 20000.0),
    "pass_retain_pressure": (0.0, 5.0),
    "pass_retain_turns": (0.0, 15.0),
    "pass_retain_advance_w": (0.0, 2.0),
    "pass_retain_backmax": (500.0, 8000.0),
    "pass_endpoint_margin": (0.0, 6.0),
    "status_danger_turns": (0.0, 4.0),
    "status_attention_turns": (0.0, 8.0),
    "pass_min_score_free": (-3000.0, 3000.0),
    "pass_min_score_attention": (-3000.0, 3000.0),
    "pass_min_score_danger": (-3000.0, 3000.0),
    "pass_w_recv_free": (0.0, 3000.0),
    "plan_beam": (2.0, 16.0),
    "plan_w_progress": (0.0, 5.0),
    "plan_w_shot": (0.0, 20.0),
    "plan_w_livre": (0.0, 6000.0),
    "plan_leg_penalty": (0.0, 500.0),
    "plan_margin_turns": (0.0, 4.0),
    "plan_margin_value": (0.0, 6000.0),
    "plan_control_turns": (0.0, 3.0),
    "plan_trigger_turns": (0.0, 20.0),
    "lead_comfortable": (1.0, 8.0),
    "late_game_turns": (0.0, 3000.0),
    "game_aggr_scale": (0.0, 3000.0),
    "mark_t_max": (2.0, 10.0),
    "mark_n_dirs": (8.0, 48.0),
    "mark_free_frac": (0.0, 1.0),
    "mark_trapped_frac": (0.0, 0.5),
    "finish_sure_slack": (-500.0, 1500.0),
    "finish_run_range": (500.0, 4000.0),
    "finish_w_cover": (0.0, 4.0),
    "finish_w_slack": (0.0, 4.0),
    "cover_count": (0.0, 4.0),
    "cover_range": (3000.0, 12000.0),
    "cover_dist": (200.0, 1500.0),
    "support_n_forward": (0.0, 5.0),
    "support_advance": (800.0, 5000.0),
    "support_channel_width": (0.0, 3500.0),
    "support_off_w_advance": (0.0, 4.0),
    "support_off_w_clear": (0.0, 6.0),
    "support_off_w_press": (0.0, 5000.0),
    "support_off_w_crowd": (0.0, 5.0),
    "support_crowd_radius": (500.0, 4000.0),
    "support_off_search_r": (300.0, 2000.0),
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
    "use_velocity": ["off", "on"],
    "pass_retain": ["off", "on"],
    "pass_endpoint_race": ["off", "on"],
    "pass_exec_speed": ["off", "on"],
    "pass_touch_lead": ["off", "on"],
    "pass_status_mode": ["off", "on"],
    "status_count_gk": ["off", "on"],
    "status_measure": ["player", "ball"],
    "pass_lookahead": ["off", "depth2", "depth3"],
    "pass_control": ["off", "on"],
    "game_state_mode": ["off", "on"],
    "hold_logic": ["v9", "caso"],
    "status_metric": ["radius", "area"],
    "pass_recv_gate": ["off", "on"],
    "caso_pass_priority": ["pass_first", "dribble_first"],
    "finish_mode": ["off", "on"],
    "cover_mode": ["off", "on"],
    "support_mode": ["v9", "offer"],
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
