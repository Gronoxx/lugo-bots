#!/usr/bin/env python3
"""Ranking dos experimentos por SALDO (a função-objetivo do usuário, 18/08).

Fase 1: máximo de gols com DEFESA ABSOLUTA (ga ~ 0).
Fase 2: máximo de SALDO (gf - ga), aceitando trocar defesa por ataque.

Lê os logs de bench/ab_transition.py em results/screen/ e ordena.
Uso: python bench/ranking.py [padrão-glob ...]
"""
import glob
import os
import re
import statistics
import sys


def parse(log):
    rows = [l for l in open(log) if l.startswith('[')]
    arms = {'base': [], 'test': []}
    for l in rows:
        m = re.search(r'(base|test) (HOME|AWAY): (\d+)x(\d+)', l)
        if m:
            arms[m.group(1)].append((int(m.group(3)), int(m.group(4))))
    out = {}
    for arm, arr in arms.items():
        if not arr:
            continue
        gf = statistics.mean(a for a, _ in arr)
        ga = statistics.mean(b for _, b in arr)
        out[arm] = dict(n=len(arr), gf=gf, ga=ga, saldo=gf - ga,
                        maxgf=max(a for a, _ in arr),
                        V=sum(1 for a, b in arr if a > b),
                        E=sum(1 for a, b in arr if a == b),
                        D=sum(1 for a, b in arr if a < b))
    # genes testados
    test_genes = ''
    for l in open(log):
        if l.strip().startswith('test = '):
            test_genes = l.strip()[7:]
            break
    return out, test_genes


def main():
    pats = sys.argv[1:] or ['results/screen/*.log']
    files = []
    for p in pats:
        files += sorted(glob.glob(p))
    rows = []
    for f in files:
        try:
            arms, genes = parse(f)
        except Exception:
            continue
        if 'base' not in arms or 'test' not in arms:
            continue
        b, t = arms['base'], arms['test']
        rows.append((t['saldo'] - b['saldo'], os.path.basename(f)[:-4], b, t, genes))
    rows.sort(reverse=True)
    print(f"{'experimento':22s} {'base saldo':>10s} {'test saldo':>10s} "
          f"{'Δsaldo':>8s} {'test gf':>8s} {'test ga':>8s} {'V/E/D':>9s}")
    print('-' * 82)
    for d, name, b, t, genes in rows:
        print(f"{name:22s} {b['saldo']:+10.2f} {t['saldo']:+10.2f} {d:+8.2f} "
              f"{t['gf']:8.2f} {t['ga']:8.2f} "
              f"{t['V']}/{t['E']}/{t['D']:<5}")
    print()
    print("DEFESA ABSOLUTA (fase 1) = candidatos com test ga <= 0.10:")
    for d, name, b, t, genes in rows:
        if t['ga'] <= 0.10:
            print(f"  {name:22s} gf={t['gf']:.2f} ga={t['ga']:.2f} "
                  f"saldo={t['saldo']:+.2f} max={t['maxgf']}")


if __name__ == "__main__":
    main()
