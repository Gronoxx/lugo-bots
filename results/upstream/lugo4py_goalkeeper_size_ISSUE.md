> **OBSOLETO** — decidido em 26/08/2026 abrir apenas o PR, sem issue separada.
> Mantido só como registro do caminho descartado. Ver `COMO_DISPARAR.md`.

`GOALKEEPER_SIZE` is a tuple, not a number, because of a trailing comma in
`src/lugo4py/src/specs.py`. Any arithmetic on it raises `TypeError`:

```python
# pip install lugo4py==1.0.5
from lugo4py import specs
print(repr(specs.GOALKEEPER_SIZE))   # (919.9999999999999,)
specs.GOALKEEPER_SIZE / 2            # TypeError: unsupported operand type(s) for /: 'tuple' and 'int'
```

The Go (`GoalkeeperSize = PlayerSize * 2.3`) and JS (`GOALKEEPER_SIZE: player_size * 2.3,`,
where the comma is an object separator) clients define it correctly, so this looks like a
transliteration slip. Nothing inside the package uses the constant, which is probably why
it went unnoticed.

One-character fix in PR #<NUM>.
