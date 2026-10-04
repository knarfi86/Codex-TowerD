from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from game.app import GameApp
from game.config import load_config
from game.evil_commentary import DIALOGUES, EvilCommentary, dialogue_count


def test_comment_archive_has_many_variants_and_unique_ids() -> None:
    dialogues = [item for items in DIALOGUES.values() for item in items]
    assert dialogue_count() >= 100
    assert len({item.id for item in dialogues}) == len(dialogues)
    assert all(len(DIALOGUES[event]) >= 3 for event in ("game_start", "tower_built", "game_over"))


def test_selector_avoids_recent_repeats_and_keeps_priority_warnings_when_off() -> None:
    commentary = EvilCommentary(frequency="off", seed=7)
    snapshot = {"lives": 20, "max_lives": 20, "game_over": False}
    assert commentary.trigger("tower_built", snapshot, now=0.0) is None
    warning = commentary.trigger("enemy_breakthrough", {"lives": 4, "max_lives": 20}, force=True, now=1.0)
    assert warning is not None
    previous = warning["id"]
    for index in range(1, 8):
        item = commentary.trigger("game_start", snapshot, force=True, now=10.0 + index)
        if item:
            assert item["id"] != previous
            previous = item["id"]


def test_personality_stage_comes_from_actual_lives() -> None:
    assert EvilCommentary.stage({"lives": 20, "max_lives": 20}) == 1
    assert EvilCommentary.stage({"lives": 12, "max_lives": 20}) == 2
    assert EvilCommentary.stage({"lives": 6, "max_lives": 20}) == 3
    assert EvilCommentary.stage({"lives": 2, "max_lives": 20}) == 4
    assert EvilCommentary.stage({"lives": 0, "max_lives": 20, "game_over": True}) == 5


def test_commentary_box_and_settings_follow_resize(tmp_path) -> None:
    config_path = tmp_path / "evil-settings.json"
    os.environ["CREEPGRID_CONFIG"] = str(config_path)
    app = GameApp(host_mode=True, show_menu=False, port=18783)
    try:
        app.draw()
        first = app._draw_evil_commentary()
        assert first is not None
        assert first.bottom <= app.layout.height
        app._resize_window((1920, 1080))
        app.draw()
        second = app._draw_evil_commentary()
        assert second is not None
        assert second.bottom <= app.layout.height
        app._change_option("opt:evil_frequency")
        app._change_option("opt:evil_animations")
        saved = load_config(config_path)
        assert saved["gameplay"]["evil_frequency"] in {"off", "rare", "normal", "frequent"}
        assert isinstance(saved["gameplay"]["evil_animations"], bool)
    finally:
        app.close()
        os.environ.pop("CREEPGRID_CONFIG", None)

