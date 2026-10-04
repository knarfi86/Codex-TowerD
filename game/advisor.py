"""Presentation-only state for the Mr. Evil advisor dock.

The class deliberately owns neither game events nor dialogue selection.  That
keeps future portrait frames or local TTS adapters independent of the local
commentary rules.
"""

from __future__ import annotations

from enum import Enum
import math
from pathlib import Path
import time
from typing import Dict, Optional, Tuple

import pygame


class CharacterState(str, Enum):
    IDLE = "IDLE"
    TALKING = "TALKING"
    REACTING = "REACTING"
    ENTERING = "ENTERING"
    LEAVING = "LEAVING"


EMOTIONS: Dict[int, str] = {
    1: "Selbstgefällig",
    2: "Schadenfroh",
    3: "Gereizt",
    4: "Panisch",
    5: "Kontrollverlust",
}

EMOTION_COLORS: Dict[int, Tuple[int, int, int]] = {
    1: (205, 134, 255),
    2: (255, 178, 73),
    3: (255, 119, 79),
    4: (255, 91, 142),
    5: (255, 65, 65),
}


class CharacterView:
    """Asset-backed, animation-ready character view for the advisor UI."""

    def __init__(self, portrait_path: Path) -> None:
        self.portrait_path = portrait_path
        self.portrait: Optional[pygame.Surface] = None
        self.asset_error: Optional[str] = None
        self.state = CharacterState.ENTERING
        self.emotion_stage = 1
        self.state_started = time.monotonic()
        self._portrait_cache: Dict[Tuple[int, int], pygame.Surface] = {}

    @property
    def emotion(self) -> str:
        return EMOTIONS.get(self.emotion_stage, EMOTIONS[1])

    @property
    def color(self) -> Tuple[int, int, int]:
        return EMOTION_COLORS.get(self.emotion_stage, EMOTION_COLORS[1])

    def load_portrait(self) -> None:
        try:
            if not self.portrait_path.exists():
                raise FileNotFoundError(self.portrait_path)
            portrait = pygame.image.load(str(self.portrait_path))
            # convert_alpha needs an active display; unit tests and future
            # offline asset validation intentionally do not always have one.
            portrait = portrait.convert_alpha() if pygame.display.get_surface() else portrait.copy()
            if portrait.get_bounding_rect(min_alpha=1).width <= 0:
                raise ValueError("portrait has no visible pixels")
            self.portrait = portrait
            self.asset_error = None
        except (OSError, ValueError, pygame.error) as exc:
            self.portrait = None
            self.asset_error = str(exc)
        self._portrait_cache.clear()

    def present(self, stage: int, priority: int, now: Optional[float] = None) -> None:
        self.emotion_stage = max(1, min(5, int(stage)))
        self.state = CharacterState.REACTING if priority >= 85 else CharacterState.TALKING
        self.state_started = time.monotonic() if now is None else now

    def update(self, active: bool, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        if active:
            return
        if self.state not in (CharacterState.IDLE, CharacterState.LEAVING):
            self.state = CharacterState.LEAVING
            self.state_started = now
        elif self.state == CharacterState.LEAVING and now - self.state_started >= 0.28:
            self.state = CharacterState.IDLE
            self.state_started = now

    def portrait_for(self, max_size: Tuple[int, int]) -> Optional[pygame.Surface]:
        if self.portrait is None:
            return None
        key = (max(1, int(max_size[0])), max(1, int(max_size[1])))
        if key not in self._portrait_cache:
            scale = min(key[0] / self.portrait.get_width(), key[1] / self.portrait.get_height())
            target = (
                max(1, int(round(self.portrait.get_width() * scale))),
                max(1, int(round(self.portrait.get_height() * scale))),
            )
            self._portrait_cache[key] = pygame.transform.smoothscale(self.portrait, target)
        return self._portrait_cache[key]

    def visual_style(self, now: Optional[float], animations: bool) -> Tuple[int, int, Tuple[int, int, int]]:
        """Return alpha, vertical offset and accent color without altering artwork."""
        now = time.monotonic() if now is None else now
        if not animations:
            return 255, 0, self.color
        age = max(0.0, now - self.state_started)
        alpha = 255
        if self.state == CharacterState.ENTERING:
            alpha = int(255 * min(1.0, age / 0.32))
        elif self.state == CharacterState.LEAVING:
            alpha = int(255 * max(0.35, 1.0 - age / 0.30))
        bounce = 0
        if self.state in (CharacterState.TALKING, CharacterState.REACTING):
            amplitude = 3 if self.state == CharacterState.REACTING else 2
            bounce = int(round(math.sin(age * 10.0) * amplitude))
        return alpha, bounce, self.color
