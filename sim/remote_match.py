"""
Partida determinística contra o servidor REAL, em um único processo.

Por que existe
--------------
O ruído de medição vem da ORDEM DE CHEGADA das ordens dos 22 clientes: o
servidor as processa na sequência em que chegam, e disputas de bola se resolvem
por essa sequência. Medido: em `rush` duas partidas idênticas divergem já no
turno 2 (100d); em `wait`, no turno ~30 (33d). Nenhum modo padrão resolve.

A solução tem duas partes:
  1. `--timer-mode=remote`: o servidor só avança o turno quando NÓS mandamos
     (`Remote.ResumeListeningPhase`). Elimina turno perdido por lentidão.
  2. Este controlador SERIALIZA o envio: cada bot calcula suas ordens mas NÃO
     as envia; o controlador as envia em sequência fixa e só então avança.
Com as duas, mesmos parâmetros produzem o mesmo resultado — a seleção da
evolução passa a medir qualidade em vez de sorte.

Regra de uso: TREINAR aqui (determinístico), VALIDAR em `wait` (o modo que o
campeonato usa; `remote` é "only in dev mode" e não roda em partida oficial).

Armadilhas da lugo4py 1.0.5 contornadas aqui
--------------------------------------------
- `LugoClient.stop()` chama `exit(0)`: derruba o processo inteiro. Nunca usar;
  fechamos o canal diretamente.
- A camada `lugo4py.rl` está quebrada: `_response_watcher` chama
  `processor(inspector)` com 1 argumento esperando `List[Order]`, mas o Gym
  passa callbacks de 2 argumentos — as ordens nunca são enviadas.
- `GameSnapshotInspector.__init__` levanta ValueError se o próprio jogador não
  está no snapshot (acontece durante WAITING). Tratado por turno.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import grpc
import lugo4py
from lugo4py.protos import server_pb2, server_pb2_grpc
from lugo4py.rl import RemoteControl

HOME = lugo4py.TeamSide.HOME
AWAY = lugo4py.TeamSide.AWAY

# Ordem fixa de envio das ordens. Qualquer sequência serve, desde que seja
# SEMPRE a mesma — é isso que torna o resultado reprodutível.
SEND_ORDER = [(side, n) for side in (HOME, AWAY) for n in range(1, 12)]


class DeterministicMatch:
    """Roda uma partida completa com ordem de envio fixa.

    `policy(side, number, inspector) -> list[Order]` é chamada para cada um dos
    22 jogadores a cada turno.
    """

    def __init__(self, address, policy, formation, turns=6000, debug=False):
        self.address = address
        self.policy = policy
        self.formation = formation      # {(side, number): Point}
        self.turns = turns
        self.debug = debug

        self.clients = {}
        self.pending = {}               # (side, number) -> list[Order]
        self.snapshots = {}             # (side, number) -> último snapshot
        self.lock = threading.Condition()
        self.current_turn = 0
        self.finished = threading.Event()
        self.remote = RemoteControl()

    # ------------------------------------------------------------------ setup
    def _make_processor(self, side, number):
        def processor(inspector):
            # Calcula as ordens e as GUARDA — não envia. O envio é feito pelo
            # controlador, em sequência fixa, para eliminar a variação de
            # ordem de chegada que é a fonte do ruído.
            try:
                orders = self.policy(side, number, inspector) or []
            except Exception as e:
                if self.debug:
                    print(f"  política falhou em {side}-{number}: {e}")
                orders = []
            with self.lock:
                self.pending[(side, number)] = orders
                self.snapshots[(side, number)] = inspector.get_snapshot()
                self.lock.notify_all()
            return []      # lista vazia => o cliente não envia sozinho
        return processor

    def connect_all(self, executor):
        for side, number in SEND_ORDER:
            pos = self.formation[(side, number)]
            client = lugo4py.LugoClient(
                self.address, True, "", side, number, pos)
            self.clients[(side, number)] = client
            client.play(executor, self._make_processor(side, number),
                        lambda: None)
            time.sleep(0.02)     # o servidor recusa registros simultâneos demais
        self.remote.connect(self.address)

    # ------------------------------------------------------------------- laço
    def _all_ready(self):
        return len(self.pending) == len(SEND_ORDER)

    def run(self):
        """Executa a partida e devolve (gols_home, gols_away, turnos)."""
        last_snapshot = None
        for turn in range(self.turns):
            with self.lock:
                ok = self.lock.wait_for(self._all_ready, timeout=10.0)
                if not ok:
                    faltando = [k for k in SEND_ORDER if k not in self.pending]
                    if self.debug:
                        print(f"turno {turn}: faltaram {len(faltando)} jogadores")
                    break
                batch = dict(self.pending)
                self.pending.clear()
                snaps = dict(self.snapshots)

            # envio SERIALIZADO, sempre na mesma sequência
            for key in SEND_ORDER:
                orders = batch.get(key)
                if not orders:
                    continue
                client = self.clients[key]
                snap = snaps.get(key)
                order_set = server_pb2.OrderSet()
                order_set.turn = snap.turn if snap else turn + 1
                order_set.orders.extend(orders)
                try:
                    client._client.SendOrders(order_set)
                except Exception as e:
                    if self.debug:
                        print(f"  envio falhou {key}: {e}")

            last_snapshot = snaps.get(SEND_ORDER[0]) or last_snapshot
            if last_snapshot is not None and \
                    last_snapshot.state == server_pb2.GameSnapshot.State.OVER:
                break

            waiter = threading.Event()
            self.remote.resume_listening(waiter)
            waiter.wait(timeout=5.0)

        h = last_snapshot.home_team.score if last_snapshot else 0
        a = last_snapshot.away_team.score if last_snapshot else 0
        t = last_snapshot.turn if last_snapshot else 0
        return h, a, t

    def close(self):
        # NUNCA chamar client.stop(): a lugo4py 1.0.5 faz exit(0) nele, o que
        # mataria o processo e impediria rodar a próxima partida da evolução.
        for client in self.clients.values():
            try:
                if getattr(client, "channel", None) is not None:
                    client.channel.close()
            except Exception:
                pass


def run_match(address, policy, formation, turns=6000, debug=False):
    """Atalho: conecta, joga, fecha. Devolve (gols_home, gols_away, turnos)."""
    executor = ThreadPoolExecutor(max_workers=len(SEND_ORDER) + 4)
    match = DeterministicMatch(address, policy, formation, turns, debug)
    try:
        match.connect_all(executor)
        return match.run()
    finally:
        match.close()
        executor.shutdown(wait=False)
