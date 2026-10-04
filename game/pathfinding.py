from __future__ import annotations

from collections import deque
from functools import lru_cache
from typing import Iterable, Optional, Sequence, Tuple

from .constants import GRID_COLS, GRID_ROWS

Grid = Tuple[int, int]


def _neighbours(cell: Grid, grid_size: Tuple[int, int] = (GRID_COLS, GRID_ROWS)) -> Iterable[Grid]:
    x, y = cell
    cols, rows = grid_size
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < cols and 0 <= ny < rows:
            yield nx, ny


@lru_cache(maxsize=256)
def _cached_path(
    start: Grid,
    goal: Grid,
    blocked: Tuple[Grid, ...],
    cols: int,
    rows: int,
) -> Optional[Tuple[Grid, ...]]:
    walls = set(blocked)
    if start in walls or goal in walls:
        return None
    queue = deque([start])
    previous: dict[Grid, Optional[Grid]] = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            path = []
            while current is not None:
                path.append(current)
                current = previous[current]
            return tuple(reversed(path))
        for neighbour in _neighbours(current, (cols, rows)):
            if neighbour in walls or neighbour in previous:
                continue
            previous[neighbour] = current
            queue.append(neighbour)
    return None


def find_path(
    start: Grid,
    goal: Grid,
    blocked: Iterable[Grid] = (),
    grid_size: Tuple[int, int] = (GRID_COLS, GRID_ROWS),
) -> Optional[Tuple[Grid, ...]]:
    """Return a deterministic shortest ground route, or None when blocked."""
    walls = tuple(sorted(set(blocked)))
    cols, rows = grid_size
    return _cached_path(start, goal, walls, int(cols), int(rows))


def clear_path_cache() -> None:
    _cached_path.cache_clear()


def route_for_position(
    position: Tuple[float, float],
    goal: Grid,
    blocked: Iterable[Grid] = (),
    grid_size: Tuple[int, int] = (GRID_COLS, GRID_ROWS),
) -> Optional[Tuple[Grid, ...]]:
    """Re-route an active ground unit from its nearest grid cell to the goal."""
    cols, rows = grid_size
    start = (round(position[0]), round(position[1]))
    start = (max(0, min(int(cols) - 1, start[0])), max(0, min(int(rows) - 1, start[1])))
    path = find_path(start, goal, blocked, grid_size)
    if path is not None:
        return path
    # A unit may be visually between cells; try the four neighbours before declaring it stuck.
    for candidate in _neighbours(start, grid_size):
        path = find_path(candidate, goal, blocked, grid_size)
        if path is not None:
            return (start,) + path
    return None
