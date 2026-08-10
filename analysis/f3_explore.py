"""FRENTE 3 - exploracao: dinamica da bola, deteccao de chute."""
import numpy as np, os
D = "<cache local>"

d = np.load(os.path.join(D, "var_1.npz"))
bsp, hs = d["bsp"], d["hold_side"]
sh = d["sh"]
gols = np.where(np.diff(sh) > 0)[0] + 1
print("gols HOME nos turnos:", d["turn"][gols])

for g in gols[:3]:
    a, b = g - 25, g + 3
    print(f"\n--- gol turno {d['turn'][g]} ---")
    for i in range(a, b):
        print(f"t={d['turn'][i]:4d} ball=({d['bx'][i]:6.0f},{d['by'][i]:5.0f}) "
              f"sp={bsp[i]:6.1f} dir=({d['bdx'][i]:5.2f},{d['bdy'][i]:5.2f}) "
              f"hold={hs[i]}/{d['hold_num'][i]}")

print("\ndistribuicao de delta-speed (turnos com bola solta):")
ds = np.diff(bsp)
print("percentis:", np.percentile(ds, [1, 5, 25, 50, 75, 95, 99]))
print("n com ds > +5:", (ds > 5).sum(), " > +30:", (ds > 30).sum(), " > +100:", (ds > 100).sum())
print("n turnos com holder:", (hs >= 0).sum(), "solta:", (hs < 0).sum())
print("speed quando holder existe:", np.percentile(bsp[hs >= 0], [5, 50, 95]))
