"""Create repeatable SDL-dummy visual checks for the Mr. Evil advisor dock."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game.app import GameApp


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "visual_checks" / "mr_evil_v2"


def capture(name: str, size: tuple[int, int], event: str, snapshot: dict, text: str | None = None) -> Path:
    app = GameApp(host_mode=True, show_menu=False, port=18810)
    try:
        app._resize_window(size, persist=False)
        app._update_state(0.0)
        if text is None:
            app._queue_evil_comment(event, force=True, snapshot=snapshot)
        else:
            app._activate_evil_comment({
                "id": name,
                "event": event,
                "text": text,
                "priority": 90,
                "stage": app.evil.stage(snapshot),
            })
        app.draw()
        target = OUTPUT / f"{name}-{size[0]}x{size[1]}.png"
        pygame.image.save(app.screen, target)
        return target
    finally:
        app.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scenarios = (
        ("selbstgefaellig", (1280, 720), "corporate", {"lives": 20, "max_lives": 20, "game_over": False}, None),
        ("gereizt", (1280, 720), "boss_appeared", {"lives": 6, "max_lives": 20, "game_over": False}, None),
        ("panisch", (1280, 720), "last_life", {"lives": 2, "max_lives": 20, "game_over": False}, None),
        ("game_over", (1280, 720), "game_over", {"lives": 0, "max_lives": 20, "game_over": True}, None),
        (
            "langer_dialog",
            (800, 600),
            "visual_check",
            {"lives": 6, "max_lives": 20, "game_over": False},
            "Dieser absichtlich lange Kontrolltext prüft den automatischen Zeilenumbruch und die mehrseitige Darstellung des Advisor-Docks bei 800 mal 600 Pixeln. Keine Zeile darf abgeschnitten werden; nach einer ruhigen Lesepause wechselt die Anzeige automatisch zur nächsten Seite.",
        ),
    )
    for scenario in scenarios:
        print(capture(*scenario))


if __name__ == "__main__":
    main()
