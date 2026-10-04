from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.app import CREEP_ASSET_FILES, GameApp
from game.constants import GRID_COLS, GRID_ROWS
from game.maps import get_map, path_cells


def test_all_creep_assets_are_rgba_loaded_and_mapped_to_real_enemy_kinds() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18781)
    try:
        expected = {"scout", "raider", "brute", "wisp", "healer", "shield"}
        assert set(CREEP_ASSET_FILES) == expected
        assert set(app.creep_assets) == expected
        for kind, surface in app.creep_assets.items():
            assert surface.get_flags() & pygame.SRCALPHA
            assert surface.get_bounding_rect(min_alpha=1).w > 0
            assert surface.get_bounding_rect(min_alpha=1).h > 0
            assert surface.get_at((0, 0)).a == 0
            assert app._creep_sprite(kind) is not None
        assert app._creep_sprite("brute").get_height() > app._creep_sprite("scout").get_height()
        assert app.arena_background is not None
    finally:
        app.close()


def test_arena_background_is_cached_and_resize_keeps_game_grid_geometry() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18782)
    try:
        assert app.state is not None and app.state.map_index == 0
        original_path = path_cells(get_map(0))
        assert len(original_path) > 0
        assert app._draw_arena_background() is True
        assert app.arena_background_cache
        old_cell = app.layout.cell
        app._resize_window((1024, 680), persist=False)
        assert app.layout.cell != old_cell or app.layout.width == 1024
        assert app._draw_arena_background() is True
        assert path_cells(get_map(0)) == original_path
        assert GRID_COLS == 20 and GRID_ROWS == 12
    finally:
        app.close()
