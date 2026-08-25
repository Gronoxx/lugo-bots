## Problem

`GOALKEEPER_SIZE` is defined with a trailing comma, which makes it a **tuple** instead of
a number. Any arithmetic on it raises `TypeError`, so the constant cannot be used for
anything.

```python
# pip install lugo4py==1.0.5
from lugo4py import specs

print(repr(specs.GOALKEEPER_SIZE))   # (919.9999999999999,)   <- tuple
print(repr(specs.PLAYER_SIZE))       # 400                    <- int, as expected

specs.GOALKEEPER_SIZE / 2
# TypeError: unsupported operand type(s) for /: 'tuple' and 'int'
```

Source, `src/lugo4py/src/specs.py`:

```python
GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,
#                                  ^ this comma
```

## Why it went unnoticed

Nothing inside the package uses `GOALKEEPER_SIZE` — it is only consumed by bot authors,
so the import never fails and no internal test exercises it.

## Cross-check with the sibling clients

Both other clients define the same constant correctly, which suggests the Python version
was transliterated from the JS object literal, where the trailing comma is a harmless
property separator:

| client | definition | correct? |
|---|---|---|
| Go — `lugo4go/specs/specs.go` | `GoalkeeperSize = PlayerSize * 2.3` | yes |
| JS — `lugo4node/src/specs.ts` | `GOALKEEPER_SIZE: player_size * 2.3,` | yes (object literal) |
| Python — `lugo4py/src/lugo4py/src/specs.py` | `GOALKEEPER_SIZE = PLAYER_SIZE * 2.3,` | **no — tuple** |

The constant was added in #31 / #32.

## Fix

Removes the trailing comma. After the change:

```python
print(repr(specs.GOALKEEPER_SIZE))   # 919.9999999999999
print(specs.GOALKEEPER_SIZE / 2)     # 459.99999999999994
```

I kept the expression `PLAYER_SIZE * 2.3` untouched so the value stays identical to the
Go and JS clients (including the `919.9999999999999` float artifact). Happy to change it
to a literal `920` instead if you prefer, but that would make the three clients differ.
