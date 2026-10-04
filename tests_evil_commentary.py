from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.advisor import CharacterState, CharacterView
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


def test_loss_memory_counts_normal_and_all_in_once_and_resets_round_state() -> None:
    commentary = EvilCommentary(seed=13)
    game_over = {"lives": 0, "max_lives": 20, "game_over": True}
    commentary.trigger("all_investment", {"lives": 20, "max_lives": 20}, {"percent": 100}, force=True, now=1.0)
    assert commentary.memory["all_in"] is True
    commentary.trigger("game_over_after_all_in", game_over, force=True, now=2.0)
    commentary.trigger("game_over_after_all_in", game_over, force=True, now=3.0)
    assert commentary.memory["losses"] == 1
    commentary.trigger("restart", {"lives": 20, "max_lives": 20}, force=True, now=4.0)
    assert commentary.memory["all_in"] is False
    assert commentary.memory["sold_towers"] == 0
    assert commentary.memory["losses"] == 1
    commentary.trigger("game_over", game_over, force=True, now=5.0)
    assert commentary.memory["losses"] == 2


def test_third_loss_dialogue_is_available_after_three_separate_runs() -> None:
    commentary = EvilCommentary(seed=3)
    game_over = {"lives": 0, "max_lives": 20, "game_over": True}
    for index in range(3):
        commentary.trigger("game_over", game_over, force=True, now=10.0 + index * 4)
        if index < 2:
            commentary.trigger("restart", {"lives": 20, "max_lives": 20}, force=True, now=12.0 + index * 4)
    assert commentary.memory["losses"] == 3
    line = commentary.trigger("three_losses", game_over, force=True, now=30.0)
    assert line is not None
    assert line["stage"] == 5


def test_critical_third_loss_is_queued_behind_game_over(tmp_path) -> None:
    config_path = tmp_path / "priority.json"
    os.environ["CREEPGRID_CONFIG"] = str(config_path)
    app = GameApp(host_mode=True, show_menu=False, port=18784)
    try:
        snapshot = {"lives": 0, "max_lives": 20, "game_over": True}
        app.evil.memory["losses"] = 3
        app._queue_evil_comment("game_over", force=True, snapshot=snapshot)
        assert app.evil_comment is not None and app.evil_comment["event"] == "game_over"
        app._queue_evil_comment("three_losses", force=True, snapshot=snapshot)
        assert app.evil_comment["event"] == "game_over"
        assert any(item["event"] == "three_losses" for item in app._evil_pending)
    finally:
        app.close()
        os.environ.pop("CREEPGRID_CONFIG", None)


def test_character_view_loads_transparent_portrait_and_static_animation_mode(tmp_path) -> None:
    path = tmp_path / "mr_evil.png"
    source = pygame.Surface((18, 20), pygame.SRCALPHA)
    pygame.draw.rect(source, (90, 50, 130, 255), pygame.Rect(4, 3, 10, 15), border_radius=2)
    pygame.image.save(source, path)
    view = CharacterView(path)
    view.load_portrait()
    assert view.portrait is not None
    assert view.portrait.get_at((0, 0)).a == 0
    view.present(4, 90, now=10.0)
    alpha, offset, _ = view.visual_style(10.1, animations=False)
    assert (alpha, offset, view.state) == (255, 0, CharacterState.REACTING)
    assert view.emotion == "Panisch"


def test_character_view_exposes_all_five_stage_emotions() -> None:
    view = CharacterView(__file__)
    emotions = []
    for stage in range(1, 6):
        view.present(stage, 40, now=float(stage))
        emotions.append(view.emotion)
    assert emotions == ["Selbstgefällig", "Schadenfroh", "Gereizt", "Panisch", "Kontrollverlust"]


def test_memory_updates_even_when_a_normal_comment_is_suppressed() -> None:
    commentary = EvilCommentary(frequency="off", seed=5)
    assert commentary.trigger("all_investment", {"lives": 20, "max_lives": 20}, {"percent": 100}, now=1.0) is None
    assert commentary.memory["all_in"] is True

