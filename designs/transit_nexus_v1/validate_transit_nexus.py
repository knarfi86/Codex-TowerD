from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "transit_nexus.json"
PNG_PATH = ROOT / "transit_nexus_preview.png"


def png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Preview is not a PNG file")
    width, height = struct.unpack(">II", raw[16:24])
    return width, height


def validate(data: dict, preview_path: Path) -> list[str]:
    checks: list[str] = []
    cols = int(data["grid"]["columns"])
    rows = int(data["grid"]["rows"])
    assert (cols, rows) == (30, 18), "Expected a 30x18 draft grid"
    checks.append("30x18 grid")

    def coord(raw: list[int]) -> tuple[int, int]:
        assert isinstance(raw, list) and len(raw) == 2
        value = (int(raw[0]), int(raw[1]))
        assert 0 <= value[0] < cols and 0 <= value[1] < rows, f"Out-of-bounds coordinate: {value}"
        return value

    spawn = coord(data["spawn"]["cell"])
    base = coord(data["base"]["cell"])
    assert spawn != base
    checks.append("spawn/base coordinates")

    route_cells: dict[str, list[dict]] = {}
    route_positions: dict[str, set[tuple[int, int]]] = {}
    for route in data["routes"]:
        assert route["spawn"] == list(spawn) and route["goal"] == list(base)
        cells = route["cells"]
        assert cells, f"Route {route['id']} is empty"
        route_cells[route["id"]] = cells
        positions: set[tuple[int, int]] = set()
        for index, cell in enumerate(cells):
            position = coord([cell["x"], cell["y"]])
            assert cell["level"] in data["height_levels"], f"Unknown height level on {route['id']}"
            assert position not in positions, f"Duplicate route cell on {route['id']}: {position}"
            positions.add(position)
            if index:
                previous = cells[index - 1]
                previous_position = (previous["x"], previous["y"])
                distance = abs(position[0] - previous_position[0]) + abs(position[1] - previous_position[1])
                assert distance == 1, f"Route jump on {route['id']}: {previous_position} -> {position}"
                if previous["level"] != cell["level"]:
                    transition_cells = {tuple(item) for item in data["bridge_underpass"]["transition_cells"]}
                    assert position in transition_cells or previous_position in transition_cells, f"Unmarked level transition on {route['id']}"
        assert (cells[0]["x"], cells[0]["y"]) == spawn
        assert (cells[-1]["x"], cells[-1]["y"]) == base
        route_positions[route["id"]] = positions
    checks.append("route bounds and continuity")

    crossing = {tuple(cell) for cell in data["bridge_underpass"]["crossing_cells"]}
    assert crossing
    alpha = {tuple((cell["x"], cell["y"])): cell for cell in route_cells["route_alpha"]}
    beta = {tuple((cell["x"], cell["y"])): cell for cell in route_cells["route_beta"]}
    overlaps = route_positions["route_alpha"] & route_positions["route_beta"]
    allowed_overlaps = {spawn, base} | crossing
    assert overlaps <= allowed_overlaps, f"Unexpected route overlap: {sorted(overlaps - allowed_overlaps)}"
    for cell in crossing:
        if cell in alpha and cell in beta:
            assert alpha[cell]["level"] == "ground"
            assert beta[cell]["level"] == "elevated"
    checks.append("explicit bridge-only route overlap")

    blocked = {coord(cell) for cell in data["areas"]["blocked_cells"]}
    buildable = {coord(cell) for cell in data["areas"]["buildable_cells"]}
    footprint = route_positions["route_alpha"] | route_positions["route_beta"]
    assert not blocked & footprint, "Blocked cells overlap a route"
    assert not buildable & footprint, "Buildable cells overlap a route"
    assert not buildable & blocked, "Buildable cells overlap blocked cells"
    assert buildable and blocked
    checks.append("buildable/blocked exclusivity")

    expected_width = cols * int(data["grid"]["cell_size_preview_px"])
    expected_height = rows * int(data["grid"]["cell_size_preview_px"])
    assert data["preview"]["width_px"] == expected_width
    assert data["preview"]["height_px"] == expected_height
    assert png_dimensions(preview_path) == (expected_width, expected_height)
    manifest = data["render_manifest"]
    assert manifest["route_cell_counts"] == {key: len(value) for key, value in route_cells.items()}
    assert manifest["route_footprint_count"] == len(footprint)
    assert manifest["buildable_count"] == len(buildable)
    assert manifest["blocked_count"] == len(blocked)
    assert {tuple(cell) for cell in manifest["bridge_crossing_cells"]} == crossing
    checks.append("JSON/PNG dimensions and render manifest")
    return checks


def main() -> int:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    checks = validate(data, PNG_PATH)
    for check in checks:
        print(f"PASS: {check}")
    print(f"Transit Nexus draft valid: {JSON_PATH}")
    print(f"Preview valid: {PNG_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
