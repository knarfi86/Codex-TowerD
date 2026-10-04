from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.app import BOSS_ASSET_FILES, CREEP_ASSET_FILES, TOWER_ASSET_FILES, TOWER_ICON_FILES, GameApp
from game.constants import BOSS_WAVE_DEFS, GRID_COLS, GRID_ROWS
from game.maps import get_map, path_cells


def test_all_creep_assets_are_rgba_loaded_and_mapped_to_real_enemy_kinds() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18781)
    try:
        expected = {"scout", "raider", "brute", "wisp", "healer", "shield", "siege"}
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


def test_mr_evil_and_all_five_tower_assets_load_with_transparency_and_caches() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18786)
    try:
        expected = {"mg", "artillery", "laser", "tesla", "support"}
        assert set(TOWER_ASSET_FILES) == expected
        assert set(TOWER_ICON_FILES) == expected
        assert set(app.tower_assets) == expected
        assert set(app.tower_icons) == expected
        assert app.advisor.portrait is not None
        assert app.advisor.portrait.get_flags() & pygame.SRCALPHA
        assert app.advisor.portrait.get_at((0, 0)).a == 0
        for kind in expected:
            surface = app.tower_assets[kind]
            assert surface.get_flags() & pygame.SRCALPHA
            assert surface.get_bounding_rect(min_alpha=1).size != (0, 0)
            assert surface.get_at((0, 0)).a == 0
            sprite = app._tower_sprite(kind)
            icon = app._tower_icon(kind, 39)
            assert sprite is not None and max(sprite.size) <= round(app.layout.cell * 0.84) + 1
            assert icon is not None and max(icon.size) <= 28
        assert app.tower_sprite_cache
        app.config["video"]["fullscreen"] = False
        app._resize_window((1024, 768), persist=False)
        assert not app.tower_sprite_cache
        assert not app.tower_icon_cache
    finally:
        app.close()


def test_missing_new_tower_asset_uses_existing_geometric_fallback() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18787)
    try:
        app._update_state(0.0)
        assert app.current is not None
        app.current["effects"] = []
        app.current["enemies"] = []
        app.current["towers"] = [{"id": 1, "kind": "mg", "cell": (4, 4), "level": 1, "range": 3.0}]
        original = app.tower_assets.pop("mg")
        app.tower_sprite_cache.clear()
        assert app._tower_sprite("mg") is None
        app._draw_towers_and_enemies()  # Existing geometric mg drawing must still work.
        app.tower_assets["mg"] = original
    finally:
        app.close()


def test_ten_boss_assets_are_transparent_cached_and_have_a_safe_fallback() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18788)
    try:
        expected = set(range(10, 101, 10))
        assert set(BOSS_ASSET_FILES) == expected
        assert set(app.boss_assets) == expected
        for wave in expected:
            surface = app.boss_assets[wave]
            assert surface.get_flags() & pygame.SRCALPHA
            assert surface.get_bounding_rect(min_alpha=1).size != (0, 0)
            assert surface.get_at((0, 0)).a == 0
            sprite = app._boss_sprite(wave)
            assert sprite is not None and max(sprite.size) <= round(app.layout.cell * 2.05) + 1
        assert app._boss_sprite(110) is app._boss_sprite(10)
        assert app.boss_sprite_cache
        app.config["video"]["fullscreen"] = False
        app._resize_window((1024, 768), persist=False)
        assert not app.boss_sprite_cache

        app._update_state(0.0)
        assert app.current is not None
        app.current["effects"] = []
        app.current["enemies"] = [{
            "id": 1, "kind": "boss", "boss_wave": 10, "boss_name": BOSS_WAVE_DEFS[10]["name"],
            "x": 4.5, "y": 4.5, "hp": 800, "max_hp": 900, "slow": False, "flash": False,
        }]
        original = app.boss_assets.pop(10)
        app.boss_sprite_cache.clear()
        assert app._boss_sprite(10) is None
        app._draw_towers_and_enemies()  # Existing geometric boss fallback remains drawable.
        app.boss_assets[10] = original
    finally:
        app.close()


def test_missing_boss_file_is_logged_and_uses_the_geometric_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(BOSS_ASSET_FILES, 10, tmp_path / "boss_wave_10.png")
    app = GameApp(host_mode=True, show_menu=False, port=18789)
    try:
        assert 10 in app.boss_asset_errors
        assert "boss_wave_10.png" in app.boss_asset_errors[10]
        app._update_state(0.0)
        assert app.current is not None
        app.current["effects"] = []
        app.current["enemies"] = [{
            "id": 1, "kind": "boss", "boss_wave": 10, "boss_name": BOSS_WAVE_DEFS[10]["name"],
            "x": 4.5, "y": 4.5, "hp": 800, "max_hp": 900, "slow": False, "flash": False,
        }]
        assert app._boss_sprite(10) is None
        app._draw_towers_and_enemies()
    finally:
        app.close()
