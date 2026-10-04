from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame


ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "transit_nexus_v3.json"
PNG_PATH = ROOT / "transit_nexus_v3_preview.png"
COLS, ROWS = 30, 18
CELL_SIZE = 40
WIDTH, HEIGHT = COLS * CELL_SIZE, ROWS * CELL_SIZE
SPAWN = [15, 1]
BASE = [14, 9]
WAYPOINTS = [(15, 1), (25, 1), (25, 16), (6, 16), (6, 4), (23, 4), (23, 13), (10, 13), (10, 7), (19, 7), (19, 10), (14, 10), (14, 9)]


def expand_segment(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    sx, sy = start
    ex, ey = end
    if sx != ex and sy != ey:
        raise ValueError(f"Spiral segment must be axis-aligned: {start}->{end}")
    if sx == ex:
        step = 1 if ey >= sy else -1
        return [(sx, y) for y in range(sy, ey + step, step)]
    step = 1 if ex >= sx else -1
    return [(x, sy) for x in range(sx, ex + step, step)]


def rect_cells(x0: int, y0: int, x1: int, y1: int) -> list[list[int]]:
    return [[x, y] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def build_route() -> tuple[list[list[int]], list[dict], list[list[int]]]:
    cells: list[list[int]] = []
    segments: list[dict] = []
    turns: list[list[int]] = []
    for index, (start, end) in enumerate(zip(WAYPOINTS, WAYPOINTS[1:]), start=1):
        segment = expand_segment(start, end)
        for point in segment:
            point_list = list(point)
            if not cells or cells[-1] != point_list:
                cells.append(point_list)
        segments.append({"id": f"spiral_segment_{index:02d}", "from": list(start), "to": list(end), "cells": [list(point) for point in segment]})
    for index in range(1, len(cells) - 1):
        before = (cells[index][0] - cells[index - 1][0], cells[index][1] - cells[index - 1][1])
        after = (cells[index + 1][0] - cells[index][0], cells[index + 1][1] - cells[index][1])
        if before != after:
            turns.append(cells[index])
    return cells, segments, turns


def build_plan() -> dict:
    route, segments, turns = build_route()
    route_set = {tuple(cell) for cell in route}
    blocked_zones = [
        {"id": "outer_security_ring", "label": "Äußerer Sicherheitsring", "style": "heavy_metal_barrier", "cells": rect_cells(0, 0, 29, 0) + rect_cells(0, 17, 29, 17) + rect_cells(0, 1, 0, 16) + rect_cells(29, 1, 29, 16)},
        {"id": "west_machine_buffer", "label": "Westliche Maschinenzone", "style": "machine_buffer", "cells": rect_cells(1, 8, 4, 12)},
        {"id": "east_machine_buffer", "label": "Östliche Maschinenzone", "style": "machine_buffer", "cells": rect_cells(26, 9, 28, 14)},
        {"id": "command_utility", "label": "Gesperrter Versorgungskern", "style": "utility_block", "cells": rect_cells(12, 5, 14, 6)},
    ]
    blocked = sorted({tuple(cell) for zone in blocked_zones for cell in zone["cells"]})
    blocked_set = set(blocked)
    buildable = [[x, y] for y in range(ROWS) for x in range(COLS) if (x, y) not in route_set and (x, y) not in blocked_set]

    return {
        "schema": "creepgrid.transit_nexus.design.v3",
        "id": "transit_nexus_v3",
        "name": "Transit Nexus – Insolvenzspirale",
        "status": "playable_showcase",
        "coordinate_system": {"origin": "top_left", "x_direction": "right", "y_direction": "down", "integer_cells": True, "resolution_independent": True},
        "grid": {"columns": COLS, "rows": ROWS, "cell_size_world": 2.0, "preview_cell_px": CELL_SIZE, "gameplay_render_px": [1800, 1080]},
        "spawn": {"cell": SPAWN, "label": "Outer Security Entry"},
        "base": {"cell": BASE, "label": "Central Corporate Core"},
        "route": {"id": "insolvency_spiral_lane", "label": "Eine einzige Insolvenzspirale", "cells": route, "segments": segments, "turn_cells": turns, "direction": "spawn_to_base", "route_length": len(route)},
        "areas": {"buildable_cells": buildable, "blocked_cells": [[x, y] for x, y in blocked], "blocked_zones": blocked_zones, "route_cells_are_non_buildable": True},
        "decorations": [
            {"id": "outer_security_ring", "zone": "outer", "style": "metal_plates_warning_stripes", "bounds": [0, 0, 29, 17]},
            {"id": "transport_sector", "zone": "transport", "style": "cable_channels_and_lane_lights", "bounds": [5, 3, 24, 14]},
            {"id": "machine_zone", "zone": "machines", "style": "cooling_aggregates_violet_frames", "bounds": [1, 8, 28, 15]},
            {"id": "inner_core", "zone": "core", "style": "corporate_platform_orange_warning", "bounds": [11, 6, 18, 12]},
        ],
        "base_platform": {"center": BASE, "cells": rect_cells(12, 7, 16, 11), "style": "central_corporate_platform", "route_entry": BASE},
        "construction_rules": {"single_route": True, "no_route_switching": True, "no_bridges": True, "no_underpasses": True, "no_maze_repathing": True},
        "preview": {"width_px": WIDTH, "height_px": HEIGHT, "cell_px": CELL_SIZE, "legend": ["Baufläche", "gesperrte Fläche", "Spiral-Lane", "Spawn", "Basis", "Richtungswechsel"]},
        "render_manifest": {},
    }


def render_preview(data: dict) -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    screen.fill((7, 14, 24))
    title = pygame.font.SysFont("dejavusans", 18, bold=True)
    font = pygame.font.SysFont("dejavusans", 13)
    small = pygame.font.SysFont("dejavusans", 10)
    route = [tuple(cell) for cell in data["route"]["cells"]]
    route_set = set(route)
    blocked = {tuple(cell) for cell in data["areas"]["blocked_cells"]}
    buildable = {tuple(cell) for cell in data["areas"]["buildable_cells"]}
    turns = {tuple(cell) for cell in data["route"]["turn_cells"]}
    for y in range(ROWS):
        for x in range(COLS):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if (x, y) in blocked:
                fill = (53, 58, 70)
            elif (x, y) in buildable:
                fill = (16, 38, 53) if (x + y) % 2 else (18, 45, 59)
            else:
                fill = (11, 24, 35)
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, (37, 71, 87), rect, 1)
            if (x, y) in blocked:
                pygame.draw.line(screen, (102, 101, 113), rect.topleft, rect.bottomright, 2)
                pygame.draw.line(screen, (102, 101, 113), rect.topright, rect.bottomleft, 2)

    points = [(x * CELL_SIZE + CELL_SIZE // 2, y * CELL_SIZE + CELL_SIZE // 2) for x, y in route]
    pygame.draw.lines(screen, (4, 11, 18), False, points, 18)
    pygame.draw.lines(screen, (36, 197, 218), False, points, 12)
    for x, y in route:
        center = (x * CELL_SIZE + CELL_SIZE // 2, y * CELL_SIZE + CELL_SIZE // 2)
        pygame.draw.circle(screen, (33, 153, 174), center, 8)
        pygame.draw.circle(screen, (154, 247, 249), center, 3)
    for x, y in turns:
        center = (x * CELL_SIZE + CELL_SIZE // 2, y * CELL_SIZE + CELL_SIZE // 2)
        pygame.draw.circle(screen, (255, 164, 70), center, 11, 2)

    spawn = tuple(data["spawn"]["cell"])
    base = tuple(data["base"]["cell"])
    for cell, label, color in ((spawn, "SPAWN", (107, 242, 196)), (base, "BASE", (255, 221, 93))):
        center = (cell[0] * CELL_SIZE + CELL_SIZE // 2, cell[1] * CELL_SIZE + CELL_SIZE // 2)
        pygame.draw.circle(screen, (7, 13, 20), center, 15)
        pygame.draw.circle(screen, color, center, 12, 3)
        screen.blit(font.render(label, True, color), (center[0] - 24, center[1] - 29))
    for x in range(COLS):
        screen.blit(small.render(str(x), True, (130, 174, 189)), (x * CELL_SIZE + 2, 2))
    for y in range(ROWS):
        screen.blit(small.render(str(y), True, (130, 174, 189)), (2, y * CELL_SIZE + 22))

    panel = pygame.Surface((430, 125), pygame.SRCALPHA)
    panel.fill((6, 13, 23, 235))
    pygame.draw.rect(panel, (128, 228, 238, 230), panel.get_rect(), 2, border_radius=8)
    screen.blit(panel, (15, 14))
    screen.blit(title.render("TRANSIT NEXUS · INSOLVENZSPIRALE", True, (177, 238, 245)), (28, 24))
    screen.blit(font.render("Eine Lane · 120 Wegzellen · 11 Richtungswechsel", True, (235, 238, 239)), (28, 53))
    legend = [("Baufläche", (31, 91, 112)), ("Gesperrt", (94, 95, 108)), ("Spiral-Lane", (36, 197, 218)), ("Wendepunkt", (255, 164, 70))]
    for index, (label, color) in enumerate(legend):
        x = 28 + (index % 2) * 190
        y = 78 + (index // 2) * 19
        pygame.draw.rect(screen, color, (x, y, 14, 14), border_radius=3)
        screen.blit(small.render(label, True, (229, 238, 241)), (x + 20, y + 2))
    pygame.image.save(screen, str(PNG_PATH))
    pygame.quit()


def main() -> None:
    data = build_plan()
    data["render_manifest"] = {"route_length": data["route"]["route_length"], "turn_count": len(data["route"]["turn_cells"]), "buildable_count": len(data["areas"]["buildable_cells"]), "blocked_count": len(data["areas"]["blocked_cells"]), "preview_grid": [COLS, ROWS], "route_checksum": sum(index * (x + 1) * (y + 1) for index, (x, y) in enumerate(data["route"]["cells"], start=1))}
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render_preview(json.loads(JSON_PATH.read_text(encoding="utf-8")))
    print(f"Created {JSON_PATH}")
    print(f"Created {PNG_PATH} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
