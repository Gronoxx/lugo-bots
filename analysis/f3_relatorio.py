"""
FRENTE 3 - roda tudo e imprime o relatorio.

  ../.venv/bin/python analysis/f3_extract.py    (uma vez: replays -> npz)
  ../.venv/bin/python analysis/f3_relatorio.py

Ordem: modelo de gol -> bateria de metricas -> ruido -> escolha final.
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(os.path.dirname(HERE), ".venv", "bin", "python")

ETAPAS = [
    ("f3_check.py", "1. sanidade: chutes e gols detectados batem com o placar"),
    ("f3_gk.py", "2. o goleiro: folga lateral decide o gol"),
    ("f3_xg2.py", "3. modelo xG (logistica sobre features fisicas)"),
    ("f3_result.py", "4. bateria de 17 metricas: sinal/ruido"),
    ("f3_valid.py", "5. validade: a metrica mede forca ou volume?"),
    ("f3_noise.py", "6. estimadores de ruido do xG"),
    ("f3_best.py", "7. escolha final entre variantes de xG"),
    ("f3_origem_ruido.py", "8. de onde vem o ruido"),
]

for script, titulo in ETAPAS:
    print("\n" + "#" * 100)
    print("#", titulo)
    print("#" * 100)
    r = subprocess.run([PY, os.path.join(HERE, script)], cwd=HERE,
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stdout.write(r.stderr)
