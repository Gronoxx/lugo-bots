## Problem

`GAME_DURATION` and `EXTRA_OVERTIME_DURATION` exist in the Go and JS clients but are missing from the Python one. There is no way to read the match length from `lugo4py`, so bot authors end up hardcoding 6000.

The value is easy to get wrong. The website docs say 1200 turns while the server runs 6000.

## Fix

Adds both constants with the same values and comments used in the other clients.

```python
import lugo4py

lugo4py.GAME_DURATION            # 6000
lugo4py.EXTRA_OVERTIME_DURATION  # 2400
```

The JS client got these in 2a72774 (adding missing specs). This brings the Python client to parity.
