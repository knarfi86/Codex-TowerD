"""Render the seven Robo-Creeps and representative unique boss assets headlessly."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.app import GameApp
from game.constants import BOSS_WAVE_DEFS, ENEMY_DEFS


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "visual_checks" / "boss_asset_integration"


def enemy_snapshot(kind: str, index: int, boss_wave: int = 0) -> dict:
    spec = ENEMY_DEFS[kind]
    return {
        "id": index + 1,
        "kind": kind,
        "boss_wave": boss_wave,
        "boss_name": BOSS_WAVE_DEFS[boss_wave]["name"] if boss_wave else "",
        "x": 3.0 + index * 2.15,
        "y": 5.25 if index % 2 else 7.2,
        "hp": spec["hp"] * 0.72,
        "max_hp": spec["hp"],
        "slow": False,
        "flash": False,
        "shielded": bool(spec.get("shield")),
    }


def capture(label: str, boss_wave: int | None = None) -> Path:
    app = GameApp(host_mode=True, show_menu=False, port=18830)
    try:
        app.config["video"]["fullscreen"] = False
        app._resize_window((1280, 720), persist=False)
        app._update_state(0.0)
        assert app.current is not None
        app.current["effects"] = []
        app.current["towers"] = []
        app.current["wave"] = boss_wave or 9
        if boss_wave:
            app.current["enemies"] = [enemy_snapshot("boss", 2, boss_wave)]
            app._queue_evil_comment(
                f"boss_wave_{boss_wave}",
                force=True,
                snapshot={"lives": 12, "max_lives": 20, "game_over": False},
            )
        else:
            app.current["enemies"] = [
                enemy_snapshot(kind, index)
                for index, kind in enumerate(("scout", "raider", "brute", "wisp", "healer", "shield", "siege"))
            ]
        app.draw()
        target = OUTPUT / f"{label}.png"
        pygame.image.save(app.screen, target)
        return target
    finally:
        app.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for label, wave in (
        ("robo-creeps-and-siege", None),
        ("boss-wave-10", 10),
        ("boss-wave-30", 30),
        ("boss-wave-50", 50),
        ("boss-wave-100", 100),
    ):
        print(capture(label, wave))


if __name__ == "__main__":
    main()
