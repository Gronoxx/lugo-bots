import os
import socket
import time

from lugo4py import Mapper, NewDefaultStarter

from bot import CloneBot

MAPPER_COLS, MAPPER_ROWS = 20, 10
# posições iniciais válidas (o servidor rejeita metade adversária / círculo
# central); reusa a formação-base do nosso bot, que é aceita.
INITIAL = {
    1: (1, 4), 2: (3, 2), 3: (3, 4), 4: (3, 5), 5: (3, 7), 6: (6, 3),
    7: (5, 4), 8: (6, 6), 9: (9, 2), 10: (8, 4), 11: (9, 7),
}


def wait_for_server(address, timeout=120.0):
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
    col, row = INITIAL[config.get_bot_number()]
    region = mapper.get_region(col, row)
    starter.set_initial_position(region.get_center())
    starter.set_mapper(mapper)

    def on_join():
        pass

    starter.run(CloneBot(
        config.get_bot_team_side(),
        config.get_bot_number(),
        starter.get_initial_position(),
        starter.get_mapper(),
    ), on_join)
