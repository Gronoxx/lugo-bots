import os
import socket
import time

from lugo4py import Mapper, NewDefaultStarter

from my_bot import MyBot
from settings import MAPPER_COLS, MAPPER_ROWS, PLAYER_INITIAL_POSITIONS


def wait_for_server(address: str, timeout: float = 120.0):
    """Espera o servidor aceitar conexões.

    O cliente lugo4py tem um timeout curto e desiste se o servidor ainda
    não estiver ouvindo — o que acontece sempre que os bots sobem junto com
    o servidor (docker compose). Sem isto, parte do time não conecta e a
    partida é perdida por W.O.
    """
    host, _, port = address.partition(":")
    port = int(port.split("?")[0]) if port else 5000
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


if __name__ == "__main__":
    wait_for_server(os.environ.get("BOT_GRPC_URL", "localhost:5000"))

    starter = NewDefaultStarter()

    config = starter.get_config()
    mapper = Mapper(MAPPER_COLS, MAPPER_ROWS, config.get_bot_team_side())

    position = PLAYER_INITIAL_POSITIONS[config.get_bot_number()]
    initial_region = mapper.get_region(position['Col'], position['Row'])

    starter.set_initial_position(initial_region.get_center())
    starter.set_mapper(mapper)

    def on_join():
        pass

    starter.run(MyBot(
        config.get_bot_team_side(),
        config.get_bot_number(),
        starter.get_initial_position(),
        starter.get_mapper(),
    ), on_join)
