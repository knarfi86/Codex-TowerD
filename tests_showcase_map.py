from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from game.app import GameApp
from game.maps import MAPS, TRANSIT_NEXUS, TRANSIT_NEXUS_V3_JSON, path_cells
from game.state import GameState


def test_transit_nexus_v3_is_a_single_valid_spiral() -> None:
    data = json.loads(TRANSIT_NEXUS_V3_JSON.read_text(encoding="utf-8"))
    assert TRANSIT_NEXUS.key == "transit_nexus_v3"
    assert TRANSIT_NEXUS.grid_size == (30, 18)
    assert len(TRANSIT_NEXUS.paths) == 1
    route = TRANSIT_NEXUS.paths[0]
    assert len(route) == 120
    assert route[0] == (15, 1)
    assert route[-1] == (14, 9)
    assert len(route) == len(set(route))
    assert set(route) == path_cells(TRANSIT_NEXUS)
    assert len(data["route"]["turn_cells"]) >= 10


def test_transit_nexus_v3_has_no_side_shortcuts() -> None:
    route = TRANSIT_NEXUS.paths[0]
    positions = {cell: index for index, cell in enumerate(route)}
    side_contacts = set()
    for index, (x, y) in enumerate(route):
        for neighbour in ((x + 1, y), (x, y + 1)):
            if neighbour in positions and abs(positions[neighbour] - index) != 1:
                side_contacts.add(tuple(sorted(((x, y), neighbour))))
    assert not side_contacts


def test_transit_nexus_v3_uses_fixed_path_build_validation() -> None:
    map_index = MAPS.index(TRANSIT_NEXUS)
    state = GameState(map_index=map_index)
    state.gold = 5000
    route_cell = list(TRANSIT_NEXUS.paths[0][20])
    ok, message = state.action({"type": "build", "tower": "archer", "cell": list(route_cell)})
    assert not ok and "Bauplatz" in message
    pad = TRANSIT_NEXUS.pads[0]
    ok, message = state.action({"type": "build", "tower": "archer", "cell": list(pad)})
    assert ok, message
    state.wave = 1
    state._spawn("scout")
    enemy = next(iter(state.enemies.values()))
    assert tuple(enemy.route) == TRANSIT_NEXUS.paths[0]


def test_transit_nexus_v3_renders_background_and_resizes() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18787)
    try:
        assert app.state is not None
        app.state.reset_map(MAPS.index(TRANSIT_NEXUS))
        app._update_state(1 / 30)
        app.draw()
        assert app.active_grid_size == (30, 18)
        assert "transit_nexus_v3" in app.map_backgrounds
        app._resize_window((1024, 680), persist=False)
        app.draw()
        assert app.layout.grid_cols == 30 and app.layout.grid_rows == 18
        assert app._grid_at(app._rect_for_cell((29, 17)).center) == (29, 17)
        assert app._creep_sprite("scout") is not None
    finally:
        app.close()


def test_transit_nexus_v3_blender_outputs_exist() -> None:
    output_dir = Path("designs/transit_nexus_v3")
    for name in ("transit_nexus_v3.blend", "transit_nexus_v3_gameplay.png", "transit_nexus_v3_showcase.png", "transit_nexus_v3_layout.png"):
        path = output_dir / name
        assert path.exists() and path.stat().st_size > 0
