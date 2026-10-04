from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.app import GameApp
from game.config import load_config, save_config


def test_resize_keeps_board_square_and_hitboxes_aligned(tmp_path) -> None:
    config_path = tmp_path / "responsive.json"
    os.environ["CREEPGRID_CONFIG"] = str(config_path)
    app = GameApp(host_mode=True, show_menu=False, port=18779)
    try:
        for size in ((800, 600), (1024, 768), (1280, 720), (1600, 900), (1920, 1080)):
            app._resize_window(size)
            app._update_state(1 / 30)
            app.draw()
            board_x, board_y, board_w, board_h = app.layout.board_rect
            assert board_w == 20 * app.layout.cell
            assert board_h == 12 * app.layout.cell
            assert board_x >= 0 and board_y >= app.layout.header
            assert board_x + board_w <= app.layout.panel_x - app.layout.gap
            assert board_y + board_h <= app.layout.advisor_rect[1] - app.layout.margin
            advisor = app._draw_evil_commentary()
            assert advisor is not None
            assert advisor.top >= board_y + board_h
            assert advisor.bottom <= app.layout.height - app.layout.footer
            cell = (3, 2)
            rect = app._rect_for_cell(cell)
            assert app._grid_at(rect.center) == cell
            assert app.button_rects
            assert not app.main_menu_rect.colliderect(app.research_open_rect)
            assert all(not rect.colliderect(app.research_open_rect) for rect in app.speed_rects.values())
    finally:
        app.close()
        os.environ.pop("CREEPGRID_CONFIG", None)


def test_video_resize_event_updates_live_window_and_persists(tmp_path) -> None:
    config_path = tmp_path / "resize-event.json"
    os.environ["CREEPGRID_CONFIG"] = str(config_path)
    app = GameApp(host_mode=True, port=18780)
    try:
        app._handle_event(pygame.event.Event(pygame.VIDEORESIZE, size=(1366, 768), w=1366, h=768))
        assert app.layout.width == 1366 and app.layout.height == 768
        saved = load_config(config_path)
        assert saved["video"]["window_size"] == [1366, 768]
        assert saved["video"]["resolution"] == "1366x768"
    finally:
        app.close()
        os.environ.pop("CREEPGRID_CONFIG", None)


def test_invalid_window_settings_fall_back_safely(tmp_path) -> None:
    config_path = tmp_path / "invalid.json"
    config_path.write_text('{"video":{"resolution":"garbage","window_size":["x",-1],"ui_scale":"bad"}}', encoding="utf-8")
    config = load_config(config_path)
    assert config["video"]["resolution"] == "1280x760"
    assert config["video"]["window_size"] == [1280, 760]
    assert config["video"]["ui_scale"] == 1.0
    assert save_config(config, config_path)


def test_menu_start_button_is_visible_and_not_covered_by_the_advisor_dock(tmp_path) -> None:
    config_path = tmp_path / "menu.json"
    os.environ["CREEPGRID_CONFIG"] = str(config_path)
    app = GameApp(host_mode=True, port=18785)
    try:
        for size in ((800, 600), (1920, 1080)):
            app._resize_window(size)
            app.draw()
            start = app.menu_buttons["start"]
            assert start.width > 0 and start.height > 0
            assert start.left >= 0 and start.right <= app.layout.width
            assert start.top >= app.layout.header and start.bottom <= app.layout.height - app.layout.footer
    finally:
        app.close()
        os.environ.pop("CREEPGRID_CONFIG", None)

