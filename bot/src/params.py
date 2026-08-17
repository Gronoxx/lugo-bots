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
    # 75 = empírico vs level-1 (AUC 0.87; GK fraco reage mal). Contra GK-ELITE
    # usar 100 no genoma = CAP físico do deslocamento do goleiro no servidor
    # (retro 17/08: 100 nega 53/74 longes estéreis vs GK-forte e mantém 9/11
    # gols de longe vs L1; 120+ dobra o custo). NÃO usar 200 (erro v6/v8).
    "gk_reach_speed": 75.0,
    # gate HÍBRIDO (shot_gate="hybrid"): d<=isto usa threshold (volume perto —
    # t_bola<=9 => GK cobre +-1235, batível), d>isto usa slack (longe contra GK
    # posicionado é morto: t_bola 16-20 => cobre +-2360; v4 doou ~40 chutes vs L3).
    "hybrid_close_range": 3200.0,
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
    # B2: mistura o ponto goal-side com o ponto na LINHA bola->camper (negacao
    # de passe). 0 = goal-side puro (=v2). So age com cover_mode="on".
    "cover_lane_mix": 0.0,

    # --- TRANSICAO DEFENSIVA (pos 0-3 BotAdversario1). Todos inertes por default. ---
    # A1: barra de area frontal segura abaixo da qual a conducao vira "melhor
    # direcao livre" (carry_gate="on").
    "carry_gate_fwd_min": 0.2,
    # A2: margem (turnos) do veto por fronteiras de turno (pass_veto_mode).
    "veto_margin_turns": 0.0,
    # a3.2: piso de distancia de passe quando o portador esta marcado/no terco
    # defensivo (0 = inerte; v2 exige 800 sempre).
    "pass_min_dist_danger": 0.0,
    # a3.3: goleiro-valvula so com o portador aquem desta fracao de avanco.
    "gk_outlet_maxfrac": 0.34,
    # a3.4: barra de aceite de passe no TERCO DEFENSIVO (zone_escape="on") —
    # aceita lateral/recuo que sai da pressao. 0.0 = igual a barra normal.
    "pass_min_score_defthird": 0.0,
    # A4: quantos companheiros viram valvulas de escape e o raio da busca.
    "def_outlet_count": 2.0,
    "def_outlet_radius": 1600.0,
    # D1: crashers de rebote apos NOSSO chute.
    "rebound_crashers": 2.0,
    "rebound_zone_frac": 0.60,
    # P2 (kickoff_play): janela da jogada ensaiada pos-reset e profundidade da
    # corrida do recebedor (alem do meio-campo, no sentido de ataque).
    "kickoff_window": 40.0,
    "kickoff_run_depth": 3500.0,
    # v7/METAMORFO (kickoff_blitz): janela estendida da blitz do NOSSO
    # kickoff (bloco de 5 ao terço final em <=kb_window turnos), profundidade
    # do canal e fração de avanço da bola que RELEASE o bloco ao fluxo normal
    # (nunca sequestrar Jog1/Jog2 do finish_mode). BotAdversario2: gol aos 7s.
    "kb_window": 100.0,
    "kb_depth": 6500.0,
    "kb_release": 0.62,
    # v7/METAMORFO (kickoff_race): corrida do reinicio PERDIDA -> arco de
    # kr_ring_count MIDS/FWDS ao redor do circulo central (lado defensivo,
    # raio kr_ring_radius, abertura ±kr_arc_deg) por kr_window turnos, p/
    # interceptar o 1º passe do vencedor (anel do BotAdversario1/BotAdversario4).
    "kr_window": 40.0,
    "kr_ring_count": 4.0,
    "kr_ring_radius": 1600.0,
    "kr_arc_deg": 55.0,
    # P3 (second_ball): apos NOSSO chute sem gol, a reposse da limpeza do GK
    # deles acontece a ~2300-3000 do gol em ~25 turnos e ELES ganham 61-83%
    # (deficit ~789d na corrida). Os sb_count ATACANTES nao-chasers mais
    # proximos ocupam a zona de limpeza durante sb_window turnos.
    "sb_count": 2.0,
    "sb_window": 25.0,
    "sb_dist": 2600.0,
    "sb_y_spread": 800.0,
    # P3 (attack_width): com posse no campo deles, os ATACANTES trocam a
    # compressao lateral fixa (shift_y=0.35 rumo a bola) por attack_width_shift
    # (0 = largura neutra; negativo = abre para o lado OPOSTO a bola).
    "attack_width_shift": 0.0,
    "attack_width_minfrac": 0.5,
    # v7/METAMORFO (swarm_rebound): generaliza o second_ball — sw_count
    # atacantes em SLOTS num arco a sw_radius do gol deles (angulos 0/±sw_angle
    # da frontal), pré E pós chute. Fonte: cerco do BotAdversario2 (12×2: 39 defesas
    # do GK caindo onde ele tem 2-3 corpos → 51 finalizações). O arco nunca
    # entra no disco 1400+sw_margin (servidor empurra jogador de linha).
    "sw_count": 2.0,
    "sw_radius": 2100.0,
    "sw_angle": 35.0,
    "sw_margin": 150.0,
    # P4: piso radial da ancora defensiva (p10 medido = 1400 = abracado ao anel
    # intocavel; ~0,6-0,8 corpo desperdicado). 0 = inerte (=v3).
    "def_min_depth": 0.0,
    # P5 (placar/tempo, consumidores novos do _game_aggr existente):
    # perdendo tarde -> gate de chute mais frouxo (reduz shot_min_gap em ate
    # gs_shot_scale) e +1 crasher de segunda bola; vencendo/empatando tarde com
    # gs_retain_late=on -> retencao forcada (o mata-mata da o EMPATE ao melhor
    # seed: proteger 0-0 e' vitoria pratica). 0/off = inerte (=v3).
    "gs_shot_scale": 0.0,
    # Gate adaptativo: limiares da deteccao de goleiro-elite em-jogo.
    "ag_min_shots": 8.0,
    "ag_max_goals": 1.0,
    # PRORROGACAO (medido no video 17/08): apos o turno 6000 o goleiro ENCOLHE
    # p/ ~40-45% (920->~400; alcance ~560->~260) e vale gol de ouro — chutes
    # que o GK normal pega ENTRAM. Alivio no gate de chute em OT (0 = inerte;
    # ~260 = o encolhimento medido). So dispara na plataforma (local nao tem OT).
    "ot_gate_relief": 0.0,
    # P4 (counterpress): ao PERDER a posse fora do nosso terco, cp_extra
    # chasers a mais por cp_window turnos (corta o 1o passe deles — a fisica
    # do nosso gol 3, invertida).
    "cp_window": 25.0,
    "cp_extra": 1.0,
    "cp_min_frac": 0.33,
    # v7/METAMORFO (ot_press): elevacao da linha de apoio na prorrogacao
    # (aggression_support + isto, teto 1.5). Reusa cp_extra p/ o chaser extra.
    "ot_aggr_boost": 0.4,

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
    # C1: coleta de bola solta na zona-1400 (gk_collect="on"): so bola mais
    # lenta que isto (rapida e' caso do _goal_line_threat), e alarme do relogio
    # da zona (40 turnos -> auto-chute ao CENTRO) a partir deste valor.
    "gk_collect_speed_max": 60.0,
    "gk_collect_margin": 2.0,
    "gk_zone_alarm": 28.0,
    # C3: saturacao do rastreio do Y do PORTADOR (gk_guard_mode="track").
    "gk_track_div": 3000.0,
    # C4: margem do endpoint-race e bonus de flanco do clearance seguro.
    "gk_clear_margin": 0.0,
    "gk_clear_w_flank": 0.0,

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
    "shot_gate": "threshold",              # | xg | slack | hybrid
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
    # --- TRANSICAO DEFENSIVA + GOLEIRO + REBOTE (pos 0-3 BotAdversario1, ago/2026).
    # Todos default = v2 (a imagem que jogou o 0-3). ---
    # A1: gate de risco na conducao — rota frontal bloqueada => melhor direcao
    # LIVRE (carry.dribble_freedom) em vez de driblar para o desarme (gol 2).
    "carry_gate": "off",                   # | on
    # A2: veto de passe por FRONTEIRAS DE TURNO da bola, origem = bola, sem o
    # carve-out de 700d (o presser colado na linha de saida conta — gol 3).
    "pass_veto_mode": "v9",                # | turnwise
    # a3.3: goleiro como receptor de reciclo no nosso terco (adversario nao
    # entra na zona-1400 => recuo seguro por construcao).
    "gk_outlet": "off",                    # | on
    # a3.4: no TERCO DEFENSIVO o objetivo do passe vira SAIR da pressao:
    # barra propria + retencao sempre habilitada.
    "zone_escape": "off",                  # | on
    # A4: companheiros proximos viram valvulas de escape quando o portador
    # segura no nosso terco (abrem linha lateral/diagonal recebivel).
    "def_outlet": "off",                   # | on
    # B1: cobertura anti-banheira tambem em DEFENDING/DISPUTING (v2 so cobre
    # em SUPPORTING — o camper fica solto justamente na bola livre).
    "cover_states": "sup",                 # | all
    # F1: bola livre no NOSSO campo => recuar como em DEFENDING (a linha da v2
    # SOBE no instante do chute adversario — momento do rebote).
    "disputing_mode": "v9",                # | defend
    # C0 (sonda de laboratorio, NUNCA submeter): manda o GK a x=1200 p/
    # falsificar "preso a linha".
    "gk_probe": "off",                     # | on
    # C1 v2: GK coleta bola solta lenta que ele ALCANCA (x<=560 da linha, y na
    # boca estendida; sonda C0: preso a linha) + alarme do auto-chute.
    "gk_collect": "off",                   # | on
    # C1-b ARQUIVADO (screening: piorou 0,75->1,33 sofridos): 1o chaser embosca
    # a ejecao automatica da zona. Reavaliar so vs adversario sem press.
    "zone_ambush": "off",                  # | on
    # C2: pulo disciplinado — so pula se o pulo ALCANCA (lockout 3 turnos).
    "gk_jump_mode": "v9",                  # | strict
    # C3: guard rastreia o Y do PORTADOR adversario em zona perigosa.
    "gk_guard_mode": "v9",                 # | track
    # C4: clearance do GK com endpoint-race + veto turnwise + preferencia de
    # flanco + chutao imediato sob alarme da zona.
    "gk_clear_mode": "v9",                 # | safe
    # D1: crashers convergem ao ponto de queda apos NOSSO chute (rebote).
    "rebound_crash": "off",                # | on
    # L11: apoiadores tambem emitem catch (disputa da bola perdida no turno).
    "support_catch": "off",                # | on
    # --- PROGRAMA TATICO (2026-08-16). Default = v3. ---
    # P2: variante das posicoes iniciais (settings.py). O reinicio e' 100%
    # deterministico (1o toque em reset+13; empate vs classe igual) — kick9
    # poe o #9 na MESMA distancia do centro que o #10 (tabela imediata);
    # fine (grade 200x100) poe o #10 a ~1051 do centro (toca em reset+8).
    "init_variant": "v3",                  # | kick9 | fine
    # P2: playbook do kickoff (setplays.py): TAKER pega -> tabela ensaiada p/
    # RECV -> toque pro espaco -> cascata; RECV/onda-2 correm rotas. off = v3.
    "kickoff_play": "off",                 # | on
    # v7/METAMORFO (kickoff_blitz): apos ganhar a corrida do reinicio, bloco
    # de 5 (RECV+WAVE2+8/10) aprofunda ao terco final em <=kb_window, com
    # release por avanco da bola/alcance de finalizacao. Par natural do
    # init_variant="race" + kickoff_play. off = v6.
    "kickoff_blitz": "off",                # | on
    # v7/METAMORFO (kickoff_race): quando a corrida do reinicio e' PERDIDA,
    # arco de MIDS/FWDS nao-chasers em volta do circulo p/ roubar o 1º passe
    # (DEFENDERS nunca; chasers seguem à bola — agressividade preservada).
    # off = v6.
    "kickoff_race": "off",                 # | on
    # P3: ocupar a zona de limpeza do GK deles apos nosso chute sem gol.
    "second_ball": "off",                  # | on
    # v7/METAMORFO (swarm_rebound): 2-3 atacantes no ARCO de rebote do GK
    # deles, ANTES do chute (gancho em on_supporting quando o portador entra
    # em alcance) e DEPOIS (generaliza a zona única do second_ball em slots).
    # Mecanismo do cerco do BotAdversario2 (cada defesa vira novo chute). Eleição
    # DISJUNTA de finish_mode (Jog1/Jog2) e far_post_run. Torna rebound_crash
    # amplamente redundante — não ligar os dois no mesmo genoma.
    "swarm_rebound": "off",                # | on
    # P3: largura dos atacantes com posse no campo deles (deslocar o GK).
    "attack_width": "off",                 # | on
    # P4: contrapressao em janela apos perder a posse (agressiva — adiciona
    # corpos NA bola, compativel com a licao anti-passividade).
    "counterpress": "off",                 # | on
    # P5: crasher extra de segunda bola quando PERDENDO tarde (game_aggr>0.5).
    "gs_sb_boost": "off",                  # | on
    # P5: retencao forcada quando NAO-perdendo tarde (game_aggr<-0.5 via
    # lead_comfortable, ou empate tardio se gs_draw_ok=on): aceita reciclo
    # seguro em vez de risco — para jogos de chave onde o EMPATE nos basta.
    # SEM afundar formacao (licao anti-passividade): so muda a decisao de passe.
    "gs_retain_late": "off",               # | on
    # P5: tratar EMPATE como resultado bom (vantagem do melhor seed na chave).
    # Liga-se POR VERSAO antes de um jogo de mata-mata especifico.
    "gs_draw_ok": "off",                   # | on
    # Sombra do camper (pedido do usuario, 2026-08-16): UM unico zagueiro (o
    # mais proximo) faz sombra goal-side APENAS no camper adversario MAIS FUNDO,
    # so com a bola no nosso campo (DEFENDING/DISPUTING) — a versao minima da
    # cobertura no cerco (a de 2 zagueiros em todos os estados foi rejeitada
    # por passividade).
    "camper_shadow": "off",                # | on
    # GATE ADAPTATIVO (backlog A1, 2026-08-17): no dia das chaves UMA versao
    # enfrenta L1+L2+L3, e o gate certo difere (L1 fraco=volume/threshold;
    # L3-elite com 97,7% de defesas=slack — a v4 converteu 2,3% em 44 chutes).
    # Com on: comeca em threshold e APERTA para slack EM-JOGO ao detectar
    # goleiro-elite (>= ag_min_shots nossos on-goal e <= ag_max_goals gols).
    "shot_gate_adaptive": "off",           # | on
    # v7/METAMORFO (ot_press): na prorrogacao (turn>6000), pressao maxima —
    # chaser extra (cp_extra) sempre ativo + linha de apoio elevada
    # (ot_aggr_boost). O BotAdversario1 do 1×1 (17/08) circulou PASSIVO a OT inteira;
    # gol de ouro = jogo de uma chance, quem cria primeiro ganha. Par do
    # ot_gate_relief. Localmente invisivel (sem OT). off = v6.
    "ot_press": "off",                     # | on
    # CB_STAGGER (v6, gol de ouro BotAdversario1 17/08): com a bola funda no nosso
    # terco, tac.chasers elege os 2 mais proximos = frequentemente OS DOIS
    # zagueiros centrais -> corredor central vazio -> passe milimetrico acha o
    # camper (#9) no centro da area. Com on: se TODOS os eleitos sao DEFENDERS,
    # troca o ULTIMO pelo melhor nao-zagueiro do ranking (mantem o MESMO numero
    # de pressionadores — agressividade preservada, zaga nunca esvazia).
    "cb_stagger": "off",                   # | on
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
    "cover_lane_mix": (0.0, 1.0),
    "carry_gate_fwd_min": (0.0, 1.0),
    "veto_margin_turns": (0.0, 3.0),
    "pass_min_dist_danger": (0.0, 3000.0),
    "gk_outlet_maxfrac": (0.10, 0.60),
    "pass_min_score_defthird": (-4000.0, 1000.0),
    "def_outlet_count": (0.0, 4.0),
    "def_outlet_radius": (600.0, 3000.0),
    "rebound_crashers": (0.0, 3.0),
    "rebound_zone_frac": (0.4, 0.9),
    "gk_collect_speed_max": (0.0, 150.0),
    "gk_collect_margin": (0.0, 6.0),
    "gk_zone_alarm": (5.0, 39.0),
    "gk_track_div": (800.0, 4000.0),
    "gk_clear_margin": (0.0, 4.0),
    "gk_clear_w_flank": (0.0, 3.0),
    "kickoff_window": (10.0, 80.0),
    "kickoff_run_depth": (1500.0, 6000.0),
    "kb_window": (40.0, 160.0),
    "kb_depth": (3000.0, 8500.0),
    "kb_release": (0.45, 0.85),
    "kr_window": (10.0, 80.0),
    "kr_ring_count": (2.0, 5.0),
    "kr_ring_radius": (1150.0, 2600.0),
    "kr_arc_deg": (20.0, 90.0),
    "sb_count": (0.0, 3.0),
    "sb_window": (5.0, 40.0),
    "sb_dist": (1500.0, 4000.0),
    "sb_y_spread": (0.0, 2000.0),
    "attack_width_shift": (-0.35, 0.35),
    "attack_width_minfrac": (0.3, 0.8),
    "sw_count": (0.0, 3.0),
    "sw_radius": (1500.0, 2600.0),
    "sw_angle": (15.0, 55.0),
    "sw_margin": (50.0, 400.0),
    "def_min_depth": (0.0, 3000.0),
    "cp_window": (5.0, 60.0),
    "cp_extra": (0.0, 3.0),
    "cp_min_frac": (0.0, 0.7),
    "gs_shot_scale": (0.0, 800.0),
    "ag_min_shots": (3.0, 20.0),
    "ag_max_goals": (0.0, 3.0),
    "ot_gate_relief": (0.0, 600.0),
    "ot_aggr_boost": (0.0, 1.0),
    "hybrid_close_range": (2000.0, 4500.0),
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
    "shot_gate": ["threshold", "xg", "slack", "hybrid"],
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
    "carry_gate": ["off", "on"],
    "pass_veto_mode": ["v9", "turnwise"],
    "gk_outlet": ["off", "on"],
    "zone_escape": ["off", "on"],
    "def_outlet": ["off", "on"],
    "cover_states": ["sup", "all"],
    "disputing_mode": ["v9", "defend"],
    "gk_probe": ["off", "on"],
    "gk_collect": ["off", "on"],
    "zone_ambush": ["off", "on"],
    "gk_jump_mode": ["v9", "strict"],
    "gk_guard_mode": ["v9", "track"],
    "gk_clear_mode": ["v9", "safe"],
    "rebound_crash": ["off", "on"],
    "support_catch": ["off", "on"],
    "init_variant": ["v3", "kick9", "fine", "sym", "race"],
    "kickoff_play": ["off", "on"],
    "kickoff_blitz": ["off", "on"],
    "kickoff_race": ["off", "on"],
    "second_ball": ["off", "on"],
    "swarm_rebound": ["off", "on"],
    "attack_width": ["off", "on"],
    "counterpress": ["off", "on"],
    "gs_sb_boost": ["off", "on"],
    "gs_retain_late": ["off", "on"],
    "gs_draw_ok": ["off", "on"],
    "camper_shadow": ["off", "on"],
    "shot_gate_adaptive": ["off", "on"],
    "cb_stagger": ["off", "on"],
    "ot_press": ["off", "on"],
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
