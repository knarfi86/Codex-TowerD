from __future__ import annotations
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from game.config import load_config, save_config

from game.app import GameApp
from game.constants import BOARD_X, BOARD_Y, CELL
from game.network import HostServer, NetworkClient


def test_big_combo_mode_can_be_started_from_menu() -> None:
    app = GameApp(host_mode=True, port=18768)
    try:
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app._update_state(1 / 30)
        assert app.current is not None
        assert app.current["mode"] == "big_combo"
    finally:
        app.close()


def test_megalomania_investment_slider_has_apply_button() -> None:
    app = GameApp(host_mode=True, port=18771)
    try:
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app._update_state(1 / 30)
        app.draw()
        slider = app.savings_slider_rect
        apply_button = app.savings_apply_rect
        assert slider.w > 0 and apply_button.w > 0
        x = slider.left + slider.w // 2
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, slider.centery), button=1))
        app._update_state(1 / 30)
        assert 49 <= app.investment_percent_draft <= 51
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, slider.centery), button=1))
        app._update_state(1 / 30)
        assert 49 <= app.investment_percent_draft <= 51
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=apply_button.center, button=1))
        assert app.state is not None and app.state.investment_percent == 50
    finally:
        app.close()


def test_options_and_manual_are_reachable_and_config_persists(tmp_path) -> None:
    config_path = tmp_path / "creepgrid-config.json"
    config = load_config(config_path)
    config["gameplay"]["evil_comments"] = False
    assert save_config(config, config_path)
    assert load_config(config_path)["gameplay"]["evil_comments"] is False
    config_path.write_text("{broken", encoding="utf-8")
    assert load_config(config_path)["video"]["resolution"] == "1280x760"

    app = GameApp(host_mode=True, port=18775)
    try:
        app.draw()
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.menu_buttons["options"].center, button=1))
        app.draw()
        assert app.menu_screen == "options" and "opt:fullscreen" in app.option_rects
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.menu_buttons["options_tab:manual"].center, button=1))
        app.draw()
        assert app.options_tab == "manual" and "manual_page:9" in app.menu_buttons
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.menu_buttons["manual_page:6"].center, button=1))
        app.draw()
        assert app.manual_page == 6
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert app.menu_screen == "options"
    finally:
        app.close()


def test_multiplayer_join_dialog_accepts_ip_and_connects_to_host() -> None:
    host_server = HostServer(0)
    app = GameApp(host_mode=True, port=5000)
    try:
        app.draw()
        assert "join" in app.menu_buttons
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.menu_buttons["join"].center, button=1))
        app.draw()
        assert app.menu_screen == "join" and "join_connect" in app.menu_buttons
        for char in f"127.0.0.1:{host_server.port}":
            app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=char))
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
        assert app.menu_active is False and app.host_mode is False
        assert app.client is not None and app.client.connected
    finally:
        app.close()
        host_server.close()


def test_host_scales_shared_resources_when_a_client_connects() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=0)
    peer = NetworkClient("127.0.0.1", app.server.port)
    try:
        deadline = time.monotonic() + 1.0
        while app.state is not None and app.state.player_count != 2 and time.monotonic() < deadline:
            app._update_state(1 / 30)
            time.sleep(0.02)
        assert app.state is not None and app.state.player_count == 2
        assert app.state.gold == 140 and app.state.round_income == 50
        assert app.current is not None and app.current["resource_share_percent"] == 50.0
    finally:
        peer.close()
        app.close()


def test_maze_map_family_can_be_selected_from_menu() -> None:
    app = GameApp(host_mode=True, port=18772)
    try:
        app.draw()
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.menu_buttons["maps_maze"].center, button=1))
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app._update_state(1 / 30)
        assert app.current is not None
        assert app.current["layout_mode"] == "maze"
    finally:
        app.close()


def test_in_game_main_menu_button_returns_to_menu() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18773)
    try:
        app._update_state(1 / 30)
        app.draw()
        assert app.main_menu_rect.w > 0
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.main_menu_rect.center, button=1))
        assert app.menu_active is True and app.current is None and app.state is None
    finally:
        app.close()


def test_in_game_research_button_opens_research_screen() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18776)
    try:
        app._update_state(1 / 30)
        app.draw()
        assert app.research_open_rect.w > 0
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.research_open_rect.center, button=1))
        assert app.show_research is True
    finally:
        app.close()


def test_right_click_deselects_selected_tower() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18777)
    try:
        app._update_state(1 / 30)
        pad = list(app.state.map.pads)[0]
        ok, _ = app.state.action({"type": "build", "tower": "archer", "cell": list(pad)})
        assert ok
        app._update_state(1 / 30)
        app.selected_tower = next(iter(app.current["towers"]))["id"]
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=3))
        assert app.selected_tower is None
    finally:
        app.close()


def test_research_selection_and_atomic_build_planning_are_interactive() -> None:
    app = GameApp(host_mode=True, show_menu=False, port=18774)
    try:
        assert app.state is not None
        app.state.wave = 3
        app.state.gold = 1000
        app._update_state(1 / 30)
        app.show_research = True
        app.draw()
        laser = app.research_rects["tech_laser"]
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=laser.center, button=1))
        app.draw()
        assert app.selected_research == "tech_laser"
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.research_buy_rect.center, button=1))
        assert "tech_laser" in app.state.research
        app.show_research = False
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y))
        app.draw()
        cells = list(app.state.map.pads)[:2]
        for cell in cells:
            center = (BOARD_X + cell[0] * CELL + CELL // 2, BOARD_Y + cell[1] * CELL + CELL // 2)
            app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=center, button=1))
        app.draw()
        app._handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=app.planning_confirm_rect.center, button=1))
        assert len(app.state.towers) == 2
    finally:
        app.close()


if __name__ == "__main__":
    app = GameApp(host_mode=True, port=18766, show_menu=False)
    try:
        for _ in range(3):
            app._update_state(1 / 30)
            app.draw()
        assert app.current is not None
        assert app.current["map_title"]
        assert app.show_tower_range is True
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        assert app.show_tower_range is False
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        assert app.show_tower_range is True
        print("UI smoke test passed: Pygame host rendered a frame.")
    finally:
        app.close()

    app = GameApp(host_mode=True, port=18767)
    try:
        app.draw()
        assert app.menu_active is True
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3))
        app._handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        app._update_state(1 / 30)
        assert app.menu_active is False
        assert app.current is not None
        assert app.current["map_index"] == 1
        assert app.current["difficulty"] == "hard"
        assert app.server is None
        print("Menu smoke test passed: start settings were applied.")
    finally:
        app.close()
