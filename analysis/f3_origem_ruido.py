"""FRENTE 3 - de onde vem o ruido: modo do servidor e divergencia inicial."""
import os, sys, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import replay as R
REC = os.path.join(os.path.dirname(HERE), "bench", "recordings")

for f in ["dummies_vs_dummies", "t1", "eval_0_norm", "var_1", "var_2", "swap",
          "v6_check", "smoke_rival", "p_rival_p2_home_1"]:
    with open(os.path.join(REC, f + ".json")) as fh:
        lines = [l for l in fh.read().strip().split("\n") if l][:3]
    cfg = [R.decode_line(l) for l in lines]
    c = next(x for x in cfg if "protocol_version" in x)
    print(f"{f:30s} modo={c.get('listening_mode'):8s} "
          f"listening={c.get('listening_duration')} dur={c.get('game_duration')}")

D = "<cache local>"
a = np.load(os.path.join(D, "var_1.npz"))
b = np.load(os.path.join(D, "var_2.npz"))
print("\nvar_1 x var_2 (mesmo bot v3, mesmo adversario):")
print(f"  posicoes iniciais dos nossos jogadores iguais? "
      f"{np.allclose(a['px'][0,0], b['px'][0,0]) and np.allclose(a['py'][0,0], b['py'][0,0])}")
d = np.hypot(a["bx"] - b["bx"], a["by"] - b["by"])
first = int(np.argmax(d > 1)) if (d > 1).any() else -1
print(f"  primeiro turno em que a bola difere >1d: turno {a['turn'][first]}")
dp = np.hypot(a["px"][:, 0] - b["px"][:, 0], a["py"][:, 0] - b["py"][:, 0]).max(1)
fp = int(np.argmax(dp > 1)) if (dp > 1).any() else -1
print(f"  primeiro turno em que algum jogador nosso difere >1d: turno {a['turn'][fp]}")
print(f"  distancia media da bola entre as duas partidas apos turno 100: {d[100:].mean():.0f}d")
