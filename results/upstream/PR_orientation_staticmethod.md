## Problem

`get_orientation_by_direction` is missing `self`, so calling it on an inspector instance raises:

```python
inspector.get_orientation_by_direction(DIRECTION.FORWARD, TeamSide.HOME)
# TypeError: GameSnapshotInspector.get_orientation_by_direction() takes 2 positional arguments but 3 were given
```

## Fix

Marks it as `@staticmethod`. The method does not touch instance state, and this keeps the existing class level call working:

```python
GameSnapshotInspector.get_orientation_by_direction(DIRECTION.FORWARD, TeamSide.HOME)  # already works today
```

Adding `self` would fix the instance call but break that one.

Fixes #33
