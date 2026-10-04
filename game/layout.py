from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class ResponsiveLayout:
    """Geometry shared by rendering and input for every window size."""

    width: int
    height: int
    header: int
    footer: int
    margin: int
    gap: int
    side_width: int
    board_x: int
    board_y: int
    cell: int
    board_width: int
    board_height: int
    grid_cols: int
    grid_rows: int
    panel_x: int
    panel_y: int
    panel_width: int
    panel_height: int
    compact: bool

    @classmethod
    def for_window(
        cls,
        width: int,
        height: int,
        grid_size: Tuple[int, int] = (20, 12),
    ) -> "ResponsiveLayout":
        width = max(800, int(width))
        height = max(600, int(height))
        grid_cols = max(1, int(grid_size[0]))
        grid_rows = max(1, int(grid_size[1]))
        header = clamp(round(height * 0.085), 68, 92)
        footer = clamp(round(height * 0.075), 48, 64)
        margin = clamp(round(min(width, height) * 0.022), 16, 32)
        gap = clamp(round(width * 0.014), 14, 28)
        compact = width < 1180 or height < 760
        side_width = clamp(round(width * (0.23 if compact else 0.205)), 246, 360)
        usable_height = max(360, height - header - footer - 2 * margin)
        usable_width = max(360, width - 2 * margin - gap - side_width)
        cell = max(24, min(92, usable_width // grid_cols, usable_height // grid_rows))
        board_width = cell * grid_cols
        board_height = cell * grid_rows
        board_x = margin + max(0, (usable_width - board_width) // 2)
        board_y = header + margin + max(0, (usable_height - board_height) // 2)
        panel_x = width - margin - side_width
        panel_y = header + margin
        panel_height = height - header - footer - 2 * margin
        return cls(
            width=width,
            height=height,
            header=header,
            footer=footer,
            margin=margin,
            gap=gap,
            side_width=side_width,
            board_x=board_x,
            board_y=board_y,
            cell=cell,
            board_width=board_width,
            board_height=board_height,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            panel_x=panel_x,
            panel_y=panel_y,
            panel_width=side_width,
            panel_height=panel_height,
            compact=compact,
        )

    @property
    def board_rect(self) -> Tuple[int, int, int, int]:
        return (self.board_x, self.board_y, self.board_width, self.board_height)

    @property
    def panel_rect(self) -> Tuple[int, int, int, int]:
        return (self.panel_x, self.panel_y, self.panel_width, self.panel_height)

