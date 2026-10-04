from __future__ import annotations

import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "transit_nexus_v3.json"
PNG_PATH = ROOT / "transit_nexus_v3_preview.png"


def png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "Preview is not PNG"
    return struct.unpack(">II", raw[16:24])


def main() -> int:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    cols = int(data["grid"]["columns"])
    rows = int(data["grid"]["rows"])
    assert (cols, rows) == (30, 18)
    spawn = tuple(data["spawn"]["cell"])
    base = tuple(data["base"]["cell"])
    route = [tuple(cell) for cell in data["route"]["cells"]]
    assert len(route) == data["route"]["route_length"]
    assert len(route) == 120, f"Unexpected route length: {len(route)}"
    assert route[0] == spawn and route[-1] == base
    assert len(route) == len(set(route)), "Duplicate route cell"
    assert all(0 <= x < cols and 0 <= y < rows for x, y in route)
    for previous, current in zip(route, route[1:]):
        assert abs(previous[0] - current[0]) + abs(previous[1] - current[1]) == 1, f"Route jump: {previous}->{current}"

    route_set = set(route)
    blocked = {tuple(cell) for cell in data["areas"]["blocked_cells"]}
    buildable = {tuple(cell) for cell in data["areas"]["buildable_cells"]}
    assert not route_set & blocked
    assert not route_set & buildable
    assert not blocked & buildable
    assert len(buildable) >= 200

    side_contacts = set()
    route_indices = {cell: index for index, cell in enumerate(route)}
    for index, (x, y) in enumerate(route):
        for neighbour in ((x + 1, y), (x, y + 1)):
            if neighbour in route_indices and abs(route_indices[neighbour] - index) != 1:
                side_contacts.add(tuple(sorted(((x, y), neighbour))))
    assert not side_contacts, f"Unintended side connections: {sorted(side_contacts)}"

    turns = data["route"]["turn_cells"]
    assert len(turns) >= 10
    assert data["construction_rules"]["single_route"] is True
    assert data["construction_rules"]["no_bridges"] is True
    assert data["construction_rules"]["no_underpasses"] is True
    assert png_dimensions(PNG_PATH) == (cols * data["grid"]["preview_cell_px"], rows * data["grid"]["preview_cell_px"])
    manifest = data["render_manifest"]
    assert manifest["route_length"] == len(route)
    assert manifest["buildable_count"] == len(buildable)
    assert manifest["blocked_count"] == len(blocked)
    assert manifest["route_checksum"] == sum(index * (x + 1) * (y + 1) for index, (x, y) in enumerate(route, start=1))
    print("PASS: 30x18 grid")
    print("PASS: one connected route from spawn to base")
    print(f"PASS: {len(route)} unique route cells")
    print(f"PASS: {len(turns)} marked 90-degree turns")
    print("PASS: no unintended orthogonal side connections")
    print(f"PASS: {len(buildable)} buildable and {len(blocked)} blocked cells")
    print("PASS: JSON/preview dimensions and render manifest")
    print(f"Transit Nexus V3 valid: {JSON_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
