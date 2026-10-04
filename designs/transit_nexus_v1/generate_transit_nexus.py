from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame


ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "transit_nexus.json"
PNG_PATH = ROOT / "transit_nexus_preview.png"
COLS, ROWS = 30, 18
CELL_SIZE = 40
WIDTH, HEIGHT = COLS * CELL_SIZE, ROWS * CELL_SIZE


def expand_segment(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Expand one axis-aligned segment into inclusive grid cells."""
    sx, sy = start
    ex, ey = end
    if sx != ex and sy != ey:
        raise ValueError(f"Non-axis-aligned segment: {start} -> {end}")
    if sx == ex:
        step = 1 if ey >= sy else -1
        return [(sx, y) for y in range(sy, ey + step, step)]
    step = 1 if ex >= sx else -1
    return [(x, sy) for x in range(sx, ex + step, step)]


def rectangle(x0: int, y0: int, x1: int, y1: int) -> list[list[int]]:
    return [[x, y] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def route_definition(route_id: str, label: str, color: str, segments: list[dict]) -> dict:
    cells: list[dict] = []
    rendered_segments: list[dict] = []
    for segment in segments:
        start = tuple(segment["from"])
        end = tuple(segment["to"])
        segment_cells = expand_segment(start, end)
        for x, y in segment_cells:
            if cells and (cells[-1]["x"], cells[-1]["y"]) == (x, y):
                continue
            cells.append(
                {
                    "x": x,
                    "y": y,
                    "level": segment["level"],
                    "surface": segment["surface"],
                }
            )
        rendered_segments.append(
            {
                "id": segment["id"],
                "from": list(start),
                "to": list(end),
                "level": segment["level"],
                "surface": segment["surface"],
                "cells": [[x, y] for x, y in segment_cells],
            }
        )
    return {
        "id": route_id,
        "label": label,
        "color": color,
        "spawn": [1, 8],
        "goal": [28, 8],
        "segments": rendered_segments,
        "cells": cells,
    }


def build_plan() -> dict:
    route_alpha = route_definition(
        "route_alpha",
        "Alpha Freight Loop · ebenerdige Haupttrasse",
        "#31D7E8",
        [
            {"id": "alpha_spawn_ramp", "from": [1, 8], "to": [1, 5], "level": "ground", "surface": "road"},
            {"id": "alpha_north_lane", "from": [1, 5], "to": [4, 5], "level": "ground", "surface": "road"},
            {"id": "alpha_north_turn", "from": [4, 5], "to": [4, 4], "level": "ground", "surface": "road"},
            {"id": "alpha_north_parallel", "from": [4, 4], "to": [20, 4], "level": "ground", "surface": "road"},
            {"id": "alpha_down_link", "from": [20, 4], "to": [20, 14], "level": "ground", "surface": "road"},
            {"id": "alpha_south_parallel", "from": [20, 14], "to": [12, 14], "level": "ground", "surface": "road"},
            {"id": "alpha_south_turn", "from": [12, 14], "to": [12, 16], "level": "ground", "surface": "road"},
            {"id": "alpha_lower_parallel", "from": [12, 16], "to": [22, 16], "level": "ground", "surface": "road"},
            {"id": "alpha_return_link", "from": [22, 16], "to": [22, 8], "level": "ground", "surface": "road"},
            {"id": "alpha_lower_crossing", "from": [22, 8], "to": [26, 8], "level": "ground", "surface": "road"},
            {"id": "alpha_base_turn", "from": [26, 8], "to": [26, 6], "level": "ground", "surface": "road"},
            {"id": "alpha_base_lane", "from": [26, 6], "to": [28, 6], "level": "ground", "surface": "road"},
            {"id": "alpha_base_ramp", "from": [28, 6], "to": [28, 8], "level": "ground", "surface": "road"},
        ],
    )
    route_beta = route_definition(
        "route_beta",
        "Beta Express · zentrale Überführung",
        "#FF9F43",
        [
            {"id": "beta_spawn_lane", "from": [1, 8], "to": [7, 8], "level": "ground", "surface": "road"},
            {"id": "beta_south_turn", "from": [7, 8], "to": [7, 12], "level": "ground", "surface": "road"},
            {"id": "beta_south_parallel", "from": [7, 12], "to": [18, 12], "level": "ground", "surface": "road"},
            {"id": "beta_up_link", "from": [18, 12], "to": [18, 8], "level": "ground", "surface": "road"},
            {"id": "beta_bridge_ramp_up", "from": [18, 8], "to": [19, 8], "level": "elevated", "surface": "bridge_ramp"},
            {"id": "beta_bridge_deck", "from": [19, 8], "to": [25, 8], "level": "elevated", "surface": "bridge_deck"},
            {"id": "beta_bridge_ramp_down", "from": [25, 8], "to": [25, 9], "level": "ground", "surface": "bridge_ramp"},
            {"id": "beta_lower_return", "from": [25, 9], "to": [25, 10], "level": "ground", "surface": "road"},
            {"id": "beta_base_lane", "from": [25, 10], "to": [28, 10], "level": "ground", "surface": "road"},
            {"id": "beta_base_ramp", "from": [28, 10], "to": [28, 8], "level": "ground", "surface": "road"},
        ],
    )

    blocked_zones = [
        {"id": "security_perimeter", "label": "Sicherheitsperimeter", "cells": rectangle(0, 0, 29, 1) + rectangle(0, 17, 29, 17) + rectangle(0, 2, 0, 16) + rectangle(29, 2, 29, 16)},
        {"id": "command_core", "label": "Gesperrter Command Core", "cells": rectangle(9, 6, 11, 10)},
        {"id": "freight_yard", "label": "Gesperrter Freight Yard", "cells": rectangle(24, 11, 26, 15)},
        {"id": "reactor_buffer", "label": "Reaktor-Sicherheitszone", "cells": rectangle(2, 13, 3, 15)},
    ]
    blocked = sorted({tuple(cell) for zone in blocked_zones for cell in zone["cells"]})
    route_footprint = {
        (cell["x"], cell["y"])
        for route in (route_alpha, route_beta)
        for cell in route["cells"]
    }
    blocked_set = set(blocked)
    buildable = [
        [x, y]
        for y in range(ROWS)
        for x in range(COLS)
        if (x, y) not in route_footprint and (x, y) not in blocked_set
    ]

    return {
        "schema": "creepgrid.transit_nexus.design.v1",
        "name": "Transit Nexus",
        "id": "transit_nexus_draft_v1",
        "status": "design_only",
        "coordinate_system": {
            "origin": "top_left",
            "x_direction": "right",
            "y_direction": "down",
            "cell_coordinates": "integer",
            "screen_resolution_independent": True,
        },
        "grid": {"columns": COLS, "rows": ROWS, "cell_size_preview_px": CELL_SIZE},
        "spawn": {"id": "spawn_alpha_beta", "cell": [1, 8], "label": "Inbound Spawn"},
        "base": {"id": "base_alpha_beta", "cell": [28, 8], "label": "Corporate Core"},
        "height_levels": {
            "ground": {"index": 0, "label": "Bodenebene", "z_units": 0},
            "elevated": {"index": 1, "label": "Überführungsebene", "z_units": 1},
        },
        "routes": [route_alpha, route_beta],
        "parallel_sections": [
            {"id": "parallel_south", "route_a": "route_alpha", "route_b": "route_beta", "route_a_cells": [[12, 14], [20, 14]], "route_b_cells": [[7, 12], [18, 12]], "separation_cells": 2, "strategy_note": "Support- und AoE-Fenster zwischen zwei langen Südtrassen."},
            {"id": "parallel_overpass", "route_a": "route_alpha", "route_b": "route_beta", "route_a_cells": [[22, 8], [25, 8]], "route_b_cells": [[22, 8], [25, 8]], "separation_cells": 0, "strategy_note": "Gleiche XY-Projektion, aber getrennte Höhenebenen."},
        ],
        "bridge_underpass": {
            "id": "central_overpass_01",
            "type": "route_beta_over_route_alpha",
            "lower_route": "route_alpha",
            "upper_route": "route_beta",
            "lower_level": "ground",
            "upper_level": "elevated",
            "crossing_cells": [[20, 8], [21, 8], [22, 8], [23, 8], [24, 8], [25, 8]],
            "transition_cells": [[18, 8], [19, 8], [25, 8], [25, 9]],
            "connection_policy": "optical_crossing_only_no_route_switch",
            "blender_notes": "Route Alpha receives lower deck and Route Beta a raised bridge deck with supports on the side; never merge nav meshes at the crossing.",
        },
        "areas": {
            "buildable_cells": buildable,
            "blocked_cells": [[x, y] for x, y in blocked],
            "blocked_zones": blocked_zones,
            "route_cells_are_blocked_for_building": True,
        },
        "preview": {
            "width_px": WIDTH,
            "height_px": HEIGHT,
            "cell_px": CELL_SIZE,
            "legend": ["Baufläche", "gesperrte Fläche", "Route Alpha · Boden", "Route Beta · Boden", "Route Beta · Überführung", "Spawn", "Basis"],
        },
        "render_manifest": {},
    }


def png_size(path: Path) -> tuple[int, int]:
    return WIDTH, HEIGHT


def render_preview(data: dict, output: Path) -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    screen.fill((8, 17, 27))
    font = pygame.font.SysFont("dejavusans", 14)
    small = pygame.font.SysFont("dejavusans", 11)
    title = pygame.font.SysFont("dejavusans", 22, bold=True)
    routes = {route["id"]: route for route in data["routes"]}
    blocked = {tuple(cell) for cell in data["areas"]["blocked_cells"]}
    buildable = {tuple(cell) for cell in data["areas"]["buildable_cells"]}
    bridge = {tuple(cell) for cell in data["bridge_underpass"]["crossing_cells"]}
    alpha_cells = {(cell["x"], cell["y"]): cell for cell in routes["route_alpha"]["cells"]}
    beta_cells = {(cell["x"], cell["y"]): cell for cell in routes["route_beta"]["cells"]}

    for y in range(ROWS):
        for x in range(COLS):
            rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if (x, y) in blocked:
                fill = (48, 54, 64)
            elif (x, y) in buildable:
                fill = (17, 39, 53) if (x + y) % 2 else (19, 45, 58)
            else:
                fill = (19, 31, 42)
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, (39, 72, 87), rect, 1)
            if (x, y) in blocked:
                pygame.draw.line(screen, (89, 92, 104), rect.topleft, rect.bottomright, 2)
                pygame.draw.line(screen, (89, 92, 104), rect.topright, rect.bottomleft, 2)

    def draw_route_cell(cell: dict, color: tuple[int, int, int], elevated: bool = False) -> None:
        rect = pygame.Rect(cell["x"] * CELL_SIZE, cell["y"] * CELL_SIZE, CELL_SIZE, CELL_SIZE).inflate(-8, -8)
        if elevated:
            shadow = rect.move(0, 7)
            pygame.draw.rect(screen, (3, 8, 13), shadow, border_radius=5)
            rect = rect.move(0, -5)
        pygame.draw.rect(screen, color, rect, border_radius=5)
        pygame.draw.rect(screen, (218, 242, 246) if elevated else (7, 22, 30), rect, 2, border_radius=5)
        if elevated:
            pygame.draw.line(screen, (180, 184, 192), (rect.left + 6, rect.bottom + 5), (rect.left + 6, rect.bottom + 13), 2)
            pygame.draw.line(screen, (180, 184, 192), (rect.right - 6, rect.bottom + 5), (rect.right - 6, rect.bottom + 13), 2)

    for cell in routes["route_alpha"]["cells"]:
        draw_route_cell(cell, (35, 174, 193), elevated=False)
    for cell in routes["route_beta"]["cells"]:
        elevated = cell["level"] == "elevated"
        draw_route_cell(cell, (255, 145, 55) if not elevated else (255, 194, 76), elevated=elevated)

    for x, y in bridge:
        rect = pygame.Rect(x * CELL_SIZE + 5, y * CELL_SIZE + 4, CELL_SIZE - 10, CELL_SIZE - 8)
        pygame.draw.rect(screen, (255, 232, 121), rect, 2, border_radius=6)

    spawn = tuple(data["spawn"]["cell"])
    base = tuple(data["base"]["cell"])
    for cell, label, color in ((spawn, "SPAWN", (112, 245, 198)), (base, "BASE", (255, 231, 116))):
        center = (cell[0] * CELL_SIZE + CELL_SIZE // 2, cell[1] * CELL_SIZE + CELL_SIZE // 2)
        pygame.draw.circle(screen, (9, 14, 20), center, 15)
        pygame.draw.circle(screen, color, center, 12, 3)
        screen.blit(font.render(label, True, color), (center[0] - 26, center[1] - 29))

    for x in range(COLS):
        screen.blit(small.render(str(x), True, (138, 180, 192)), (x * CELL_SIZE + 3, 2))
    for y in range(ROWS):
        screen.blit(small.render(str(y), True, (138, 180, 192)), (2, y * CELL_SIZE + 22))

    overlay = pygame.Surface((405, 142), pygame.SRCALPHA)
    overlay.fill((7, 14, 23, 232))
    pygame.draw.rect(overlay, (111, 187, 204, 230), overlay.get_rect(), 2, border_radius=8)
    screen.blit(overlay, (15, 14))
    screen.blit(title.render("TRANSIT NEXUS · TECHNICAL PREVIEW", True, (178, 239, 247)), (28, 25))
    legend = [("Baufläche", (39, 105, 127)), ("Gesperrt", (89, 92, 104)), ("Alpha · Boden", (35, 174, 193)), ("Beta · Boden", (255, 145, 55)), ("Beta · Überführung", (255, 194, 76))]
    for index, (label, color) in enumerate(legend):
        x = 28 + (index % 2) * 190
        y = 61 + (index // 2) * 19
        pygame.draw.rect(screen, color, (x, y, 14, 14), border_radius=3)
        screen.blit(small.render(label, True, (226, 237, 240)), (x + 20, y + 1))
    screen.blit(small.render("Zentrale Überführung: Beta bleibt logisch getrennt", True, (255, 231, 116)), (28, 119))

    bridge_label = small.render("BRIDGE / UNDERPASS", True, (255, 231, 116))
    screen.blit(bridge_label, (19 * CELL_SIZE, 8 * CELL_SIZE - 17))
    pygame.image.save(screen, str(output))
    pygame.quit()


def main() -> None:
    data = build_plan()
    data["render_manifest"] = {
        "route_cell_counts": {route["id"]: len(route["cells"]) for route in data["routes"]},
        "route_footprint_count": len({(cell["x"], cell["y"]) for route in data["routes"] for cell in route["cells"]}),
        "buildable_count": len(data["areas"]["buildable_cells"]),
        "blocked_count": len(data["areas"]["blocked_cells"]),
        "bridge_crossing_cells": data["bridge_underpass"]["crossing_cells"],
    }
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    loaded = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    render_preview(loaded, PNG_PATH)
    print(f"Created {JSON_PATH}")
    print(f"Created {PNG_PATH} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
