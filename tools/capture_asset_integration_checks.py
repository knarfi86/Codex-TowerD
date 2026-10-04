"""Render the supplied Mr. Evil and tower assets through the gameplay HUD."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.app import GameApp
from game.constants import TOWER_DEFS


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "visual_checks" / "asset_integration"


def tower_snapshot(kind: str, index: int) -> dict:
    spec = TOWER_DEFS[kind]
    return {
        "id": index + 1,
        "kind": kind,
        "cell": ((4 + index * 3) % 18 + 1, 4 + (index % 2) * 3),
        "level": index % 3 + 1,
        "range": spec["range"],
        "damage": spec["damage"],
        "priority": "first",
        "total_damage": 120 + index * 40,
        "kills": index,
        "fire_rate": round(1.0 / spec["cooldown"], 2),
        "invested": spec["cost"],
    }


def capture(size: tuple[int, int]) -> Path:
    app = GameApp(host_mode=True, show_menu=False, port=18820)
    try:
        app.config["video"]["fullscreen"] = False
        app._resize_window(size, persist=False)
        app._update_state(0.0)
        assert app.current is not None
        app.current["towers"] = [tower_snapshot(kind, index) for index, kind in enumerate(("mg", "artillery", "laser", "tesla", "support"))]
        app.current["effects"] = []
        app.current["enemies"] = []
        app.selected_tower = 1
        app.selected_build = "tesla"
        app._queue_evil_comment("boss_appeared", force=True, snapshot={"lives": 6, "max_lives": 20, "game_over": False})
        app.draw()
        target = OUTPUT / f"gameplay-assets-{size[0]}x{size[1]}.png"
        pygame.image.save(app.screen, target)
        return target
    finally:
        app.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for size in ((800, 600), (1280, 720), (1920, 1080)):
        print(capture(size))


if __name__ == "__main__":
    main()
