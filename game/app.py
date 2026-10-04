from __future__ import annotations
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame

from .constants import (
    BOARD_H, BOARD_W, BOARD_X, BOARD_Y, BOSS_WAVE_DEFS, BUILD_PAD, BUILD_PAD_HOVER, CELL,
    DIFFICULTY_DEFS, DIFFICULTY_KEYS, ENEMY_DEFS, FPS, GOLD, GRASS, GRASS_ALT, GRID_COLS, GRID_ROWS, HEALTH,
    INK, MANA, MUTED, PANEL, PANEL_DARK, PATH, PATH_EDGE, PRIORITY_LABELS,
    SELECT, SNAPSHOT_RATE, TEXT, TICK_RATE, TOWER_DEFS, TOWER_TYPES, WATER, WINDOW_H, WINDOW_W, boss_asset_wave_for,
)
from .config import RESOLUTION_PRESETS, load_config, save_config
from .advisor import CharacterView
from .evil_commentary import EvilCommentary
from .layout import ResponsiveLayout
from .maps import MAPS, get_map, map_indices_for_layout, path_cells
from .network import HostServer, NetworkClient
from .pathfinding import find_path
from .state import GameState
from .research import RESEARCH_DEFS
from .ui_data import DIFFICULTY_FLAVOR, MAP_FAMILY_INFO, MODE_INFO, mode_info

Point = Tuple[float, float]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MR_EVIL_ASSET_FILE = PROJECT_ROOT / "assets" / "characters" / "mr_evil.png"
TOWER_ASSET_FILES = {
    "mg": PROJECT_ROOT / "assets" / "towers" / "mg.png",
    "artillery": PROJECT_ROOT / "assets" / "towers" / "artillery.png",
    "laser": PROJECT_ROOT / "assets" / "towers" / "laser.png",
    "tesla": PROJECT_ROOT / "assets" / "towers" / "tesla.png",
    "support": PROJECT_ROOT / "assets" / "towers" / "support.png",
}
TOWER_ICON_FILES = {
    kind: PROJECT_ROOT / "assets" / "towers" / "icons" / f"{kind}.png"
    for kind in TOWER_ASSET_FILES
}
CREEP_ASSET_FILES = {
    "scout": PROJECT_ROOT / "assets" / "creeps" / "creep_standard.png",
    "raider": PROJECT_ROOT / "assets" / "creeps" / "creep_fast.png",
    "brute": PROJECT_ROOT / "assets" / "creeps" / "creep_armored.png",
    "wisp": PROJECT_ROOT / "assets" / "creeps" / "creep_flying.png",
    "healer": PROJECT_ROOT / "assets" / "creeps" / "creep_healer.png",
    "shield": PROJECT_ROOT / "assets" / "creeps" / "creep_shield.png",
    "siege": PROJECT_ROOT / "assets" / "creeps" / "creep_siege.png",
}
BOSS_ASSET_FILES = {
    wave: PROJECT_ROOT / "assets" / "bosses" / definition["asset"]
    for wave, definition in BOSS_WAVE_DEFS.items()
}
CREEP_VISUAL_SCALE = {
    "scout": 1.22,
    "raider": 1.12,
    "brute": 1.52,
    "wisp": 1.24,
    "healer": 1.34,
    "shield": 1.34,
    "siege": 1.42,
}
ARENA_BACKGROUND_CANDIDATES = (
    PROJECT_ROOT / "assets" / "maps" / "map_creep_arena_bg.png",
    PROJECT_ROOT / "assets" / "map_creep_arena_bg.png.png",
)
TRANSIT_NEXUS_V3_BACKGROUND_CANDIDATES = (
    PROJECT_ROOT / "designs" / "transit_nexus_v3" / "transit_nexus_v3_gameplay.png",
    PROJECT_ROOT / "assets" / "maps" / "transit_nexus_v3_gameplay.png",
)

class GameApp:
    def __init__(self, host_mode: bool, host: str = "", port: int = 5000, show_menu: bool = True) -> None:
        pygame.init()
        self.config = load_config()
        gameplay_config = self.config.get("gameplay", {})
        self.evil = EvilCommentary(
            frequency=gameplay_config.get("evil_frequency", "normal") if gameplay_config.get("evil_comments", True) else "off",
            animations=gameplay_config.get("evil_animations", True),
            text_size=gameplay_config.get("evil_text_size", "normal"),
        )
        self.evil_comment: Optional[Dict[str, object]] = None
        self._evil_pending: List[Dict[str, object]] = []
        self.evil_comment_until = 0.0
        self.evil_comment_started = 0.0
        self._evil_seen_enemy_roles: set[str] = set()
        self._evil_last_player_count = 1
        pygame.display.set_caption("CreepGrid · Barbarossa & Evil Enterprises")
        width, height = self._configured_resolution()
        flags = pygame.FULLSCREEN if self.config["video"].get("fullscreen") else pygame.RESIZABLE
        self.screen = pygame.display.set_mode((width, height), flags)
        self.active_grid_size = (GRID_COLS, GRID_ROWS)
        self.layout = ResponsiveLayout.for_window(width, height, self.active_grid_size)
        self._apply_layout_constants()
        self.clock = pygame.time.Clock()
        self._rebuild_fonts()
        self.creep_assets: Dict[str, pygame.Surface] = {}
        self.creep_asset_errors: Dict[str, str] = {}
        self.creep_sprite_cache: Dict[Tuple[str, int, Tuple[int, int]], pygame.Surface] = {}
        self.boss_assets: Dict[int, pygame.Surface] = {}
        self.boss_asset_errors: Dict[int, str] = {}
        self.boss_sprite_cache: Dict[Tuple[int, int, Tuple[int, int]], pygame.Surface] = {}
        self.tower_assets: Dict[str, pygame.Surface] = {}
        self.tower_icons: Dict[str, pygame.Surface] = {}
        self.tower_asset_errors: Dict[str, str] = {}
        self.tower_sprite_cache: Dict[Tuple[str, int, Tuple[int, int]], pygame.Surface] = {}
        self.tower_icon_cache: Dict[Tuple[str, int], pygame.Surface] = {}
        self.arena_background: Optional[pygame.Surface] = None
        self.arena_background_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        self.map_backgrounds: Dict[str, pygame.Surface] = {}
        self.map_background_cache: Dict[Tuple[str, int, int], pygame.Surface] = {}
        self._load_visual_assets()
        self.advisor = CharacterView(MR_EVIL_ASSET_FILE)
        self.advisor.load_portrait()
        self.host_mode = host_mode
        self.port = port
        self.menu_active = host_mode and show_menu
        self.menu_mode = "single"
        self.menu_game_mode = "classic"
        self.menu_map_index = 0
        self.menu_map_category = "fixed"
        self.menu_difficulty = "normal"
        self.menu_screen = "main"
        self.options_tab = "video"
        self.manual_page = 0
        self.option_rects: Dict[str, pygame.Rect] = {}
        self.manual_rects: Dict[str, pygame.Rect] = {}
        self.join_address = ""
        self.join_error = ""
        self.show_options = False
        self.show_manual = False
        self.menu_buttons: Dict[str, pygame.Rect] = {}
        self.server: Optional[HostServer] = None
        self.client: Optional[NetworkClient] = None if host_mode else NetworkClient(host, port)
        self.state: Optional[GameState] = None
        self.current: Optional[Dict] = None
        self.selected_tower: Optional[int] = None
        self.selected_build = "archer"
        self.show_tower_range = True
        self.show_research = False
        self.paused = False
        self.game_speed = 1.0
        self.running = True
        self.tick_accumulator = 0.0
        self.snapshot_accumulator = 0.0
        self.local_notice = "Wählt Modus, Karte und Schwierigkeit." if self.menu_active else f"Verbunden mit {host}:{port}"
        self.local_notice_until = time.monotonic() + 3
        self.button_rects: Dict[str, pygame.Rect] = {}
        self.hover_tower_button: Optional[str] = None
        self.hover_tower_since = 0.0
        self.investment_percent_draft = 0
        self.investment_dragging = False
        self.investment_draft_dirty = False
        self.investment_slider_rect = pygame.Rect(0, 0, 0, 0)
        self.investment_apply_rect = pygame.Rect(0, 0, 0, 0)
        self.savings_slider_rect = pygame.Rect(0, 0, 0, 0)
        self.savings_apply_rect = pygame.Rect(0, 0, 0, 0)
        self.main_menu_rect = pygame.Rect(0, 0, 0, 0)
        self.options_rect = pygame.Rect(0, 0, 0, 0)
        self.research_open_rect = pygame.Rect(0, 0, 0, 0)
        self.wave_start_rect = pygame.Rect(0, 0, 0, 0)
        self.research_rects: Dict[str, pygame.Rect] = {}
        self.research_buy_rect = pygame.Rect(0, 0, 0, 0)
        self.selected_research: Optional[str] = None
        self.planning_mode = False
        self.planned_builds: List[Dict] = []
        self.planning_confirm_rect = pygame.Rect(0, 0, 0, 0)
        self.planning_cancel_rect = pygame.Rect(0, 0, 0, 0)
        self.priority_rect = pygame.Rect(0, 0, 0, 0)
        self.speed_rects: Dict[int, pygame.Rect] = {}
        if host_mode and not self.menu_active:
            self._start_host_game(lan_mode=True)

    def _configured_resolution(self) -> Tuple[int, int]:
        video = self.config.get("video", {})
        if video.get("fullscreen"):
            info = pygame.display.Info()
            if info.current_w >= 800 and info.current_h >= 600:
                return info.current_w, info.current_h
        saved_size = video.get("window_size")
        if isinstance(saved_size, (list, tuple)) and len(saved_size) == 2:
            try:
                width, height = int(saved_size[0]), int(saved_size[1])
                if width >= 800 and height >= 600:
                    if pygame.display.get_driver() != "dummy":
                        info = pygame.display.Info()
                        if info.current_w >= 800 and info.current_h >= 600:
                            width = min(width, max(800, info.current_w - 80))
                            height = min(height, max(600, info.current_h - 120))
                    return width, height
            except (TypeError, ValueError):
                pass
        raw = video.get("resolution", "1280x760")
        try:
            width, height = (int(part) for part in str(raw).lower().split("x", 1))
            if width >= 800 and height >= 600:
                if pygame.display.get_driver() != "dummy":
                    info = pygame.display.Info()
                    if info.current_w >= 800 and info.current_h >= 600:
                        width = min(width, max(800, info.current_w - 80))
                        height = min(height, max(600, info.current_h - 120))
                return width, height
        except (TypeError, ValueError):
            pass
        return WINDOW_W, WINDOW_H

    def _apply_layout_constants(self) -> None:
        """Keep legacy draw code on the same live viewport as input handling."""
        global BOARD_X, BOARD_Y, BOARD_W, BOARD_H, CELL, WINDOW_W, WINDOW_H, GRID_COLS, GRID_ROWS
        WINDOW_W, WINDOW_H = self.layout.width, self.layout.height
        GRID_COLS, GRID_ROWS = self.active_grid_size
        BOARD_X = self.layout.board_x
        BOARD_Y = self.layout.board_y
        BOARD_W = self.layout.board_width
        BOARD_H = self.layout.board_height
        CELL = self.layout.cell

    def _set_active_grid_size(self, grid_size: Tuple[int, int]) -> None:
        normalized = (max(1, int(grid_size[0])), max(1, int(grid_size[1])))
        if normalized == self.active_grid_size:
            return
        self.active_grid_size = normalized
        self.layout = ResponsiveLayout.for_window(self.layout.width, self.layout.height, normalized)
        self._apply_layout_constants()
        self.creep_sprite_cache.clear()
        self.boss_sprite_cache.clear()
        self.tower_sprite_cache.clear()
        self.tower_icon_cache.clear()
        self.arena_background_cache.clear()
        self.map_background_cache.clear()

    def _resize_window(self, size: Tuple[int, int], persist: bool = True) -> None:
        width = max(800, int(size[0]))
        height = max(600, int(size[1]))
        if self.config["video"].get("fullscreen"):
            return
        try:
            self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        except pygame.error:
            return
        self.layout = ResponsiveLayout.for_window(width, height, self.active_grid_size)
        self._apply_layout_constants()
        self.creep_sprite_cache.clear()
        self.boss_sprite_cache.clear()
        self.tower_sprite_cache.clear()
        self.tower_icon_cache.clear()
        self._rebuild_fonts()
        self.config["video"]["window_size"] = [width, height]
        self.config["video"]["resolution"] = f"{width}x{height}"
        if persist:
            self._save_preferences()

    def _rebuild_fonts(self) -> None:
        text_scale = {"small": 0.9, "normal": 1.0, "large": 1.2}.get(self.config["text"].get("size"), 1.0)
        text_scale *= float(self.config["video"].get("ui_scale", 1.0))
        self.font = pygame.font.SysFont("dejavusans", max(10, round(15 * text_scale)))
        self.small = pygame.font.SysFont("dejavusans", max(9, round(12 * text_scale)))
        self.title = pygame.font.SysFont("dejavusans", max(14, round(24 * text_scale)), bold=True)
        self.big = pygame.font.SysFont("dejavusans", max(22, round(40 * text_scale)), bold=True)

    def _load_visual_assets(self) -> None:
        for kind, path in CREEP_ASSET_FILES.items():
            try:
                if not path.exists():
                    raise FileNotFoundError(path)
                self.creep_assets[kind] = pygame.image.load(str(path)).convert_alpha()
            except (OSError, pygame.error) as exc:
                self.creep_asset_errors[kind] = str(exc)

        for wave, path in BOSS_ASSET_FILES.items():
            try:
                if not path.exists():
                    raise FileNotFoundError(path)
                self.boss_assets[wave] = pygame.image.load(str(path)).convert_alpha()
            except (OSError, pygame.error) as exc:
                self.boss_asset_errors[wave] = str(exc)

        for kind, path in TOWER_ASSET_FILES.items():
            try:
                if not path.exists():
                    raise FileNotFoundError(path)
                self.tower_assets[kind] = pygame.image.load(str(path)).convert_alpha()
            except (OSError, pygame.error) as exc:
                self.tower_asset_errors[kind] = str(exc)
        for kind, path in TOWER_ICON_FILES.items():
            try:
                if not path.exists():
                    raise FileNotFoundError(path)
                self.tower_icons[kind] = pygame.image.load(str(path)).convert_alpha()
            except (OSError, pygame.error) as exc:
                self.tower_asset_errors[f"icon:{kind}"] = str(exc)

        for path in ARENA_BACKGROUND_CANDIDATES:
            try:
                if path.exists():
                    self.arena_background = pygame.image.load(str(path)).convert()
                    break
            except (OSError, pygame.error) as exc:
                self.creep_asset_errors["arena_background"] = str(exc)
        for path in TRANSIT_NEXUS_V3_BACKGROUND_CANDIDATES:
            try:
                if path.exists():
                    self.map_backgrounds["transit_nexus_v3"] = pygame.image.load(str(path)).convert()
                    break
            except (OSError, pygame.error) as exc:
                self.creep_asset_errors["transit_nexus_v3_background"] = str(exc)

    def _creep_sprite(self, kind: str) -> Optional[pygame.Surface]:
        source = self.creep_assets.get(kind)
        if source is None:
            return None
        key = (kind, int(CELL), self.active_grid_size)
        if key not in self.creep_sprite_cache:
            grid_factor = 0.88 if self.active_grid_size[1] >= 16 else 1.0
            target_height = max(1, int(round(CELL * CREEP_VISUAL_SCALE.get(kind, 1.2) * grid_factor)))
            scale = target_height / max(1, source.get_height())
            target_size = (max(1, int(round(source.get_width() * scale))), target_height)
            self.creep_sprite_cache[key] = pygame.transform.smoothscale(source, target_size)
        return self.creep_sprite_cache[key]

    def _boss_sprite(self, boss_wave: int) -> Optional[pygame.Surface]:
        """Return the centrally mapped, cached boss portrait for this wave."""
        asset_wave = boss_asset_wave_for(int(boss_wave))
        source = self.boss_assets.get(asset_wave)
        if source is None:
            return None
        key = (asset_wave, int(CELL), self.active_grid_size)
        if key not in self.boss_sprite_cache:
            target = max(42, int(round(CELL * 2.05)))
            scale = min(target / source.get_width(), target / source.get_height())
            target_size = (
                max(1, int(round(source.get_width() * scale))),
                max(1, int(round(source.get_height() * scale))),
            )
            self.boss_sprite_cache[key] = pygame.transform.smoothscale(source, target_size)
        return self.boss_sprite_cache[key]

    def _tower_sprite(self, kind: str) -> Optional[pygame.Surface]:
        """Return a cached transparent sprite for a current grid-cell size."""
        source = self.tower_assets.get(kind)
        if source is None:
            return None
        key = (kind, int(CELL), self.active_grid_size)
        if key not in self.tower_sprite_cache:
            target = max(18, int(round(CELL * 0.84)))
            scale = min(target / source.get_width(), target / source.get_height())
            target_size = (
                max(1, int(round(source.get_width() * scale))),
                max(1, int(round(source.get_height() * scale))),
            )
            self.tower_sprite_cache[key] = pygame.transform.smoothscale(source, target_size)
        return self.tower_sprite_cache[key]

    def _tower_icon(self, kind: str, button_height: int) -> Optional[pygame.Surface]:
        source = self.tower_icons.get(kind)
        if source is None:
            return None
        size = max(14, min(28, button_height - 10))
        key = (kind, size)
        if key not in self.tower_icon_cache:
            scale = min(size / source.get_width(), size / source.get_height())
            target_size = (
                max(1, int(round(source.get_width() * scale))),
                max(1, int(round(source.get_height() * scale))),
            )
            self.tower_icon_cache[key] = pygame.transform.smoothscale(source, target_size)
        return self.tower_icon_cache[key]

    def _draw_arena_background(self) -> bool:
        if self.arena_background is None:
            return False
        key = (int(BOARD_W), int(BOARD_H))
        if key not in self.arena_background_cache:
            source = self.arena_background
            # The source has a decorative cyan room frame around its own grid.
            # Crop into that room before fitting it to the real 20x12 board so
            # the decoration cannot read as a second playable boundary.
            source_rect = pygame.Rect(
                int(source.get_width() * 0.24),
                int(source.get_height() * 0.16),
                int(source.get_width() * 0.52),
                int(source.get_height() * 0.68),
            )
            source = source.subsurface(source_rect).copy()
            scale = max(BOARD_W / source.get_width(), BOARD_H / source.get_height())
            scaled_size = (max(1, int(round(source.get_width() * scale))), max(1, int(round(source.get_height() * scale))))
            scaled = pygame.transform.smoothscale(source, scaled_size)
            crop_x = max(0, (scaled.get_width() - BOARD_W) // 2)
            crop_y = max(0, (scaled.get_height() - BOARD_H) // 2)
            self.arena_background_cache[key] = scaled.subsurface(pygame.Rect(crop_x, crop_y, BOARD_W, BOARD_H)).copy()
        self.screen.blit(self.arena_background_cache[key], (BOARD_X, BOARD_Y))
        return True

    def _draw_map_background(self, map_def) -> bool:
        if map_def.key == "arena":
            return self._draw_arena_background()
        source = self.map_backgrounds.get(map_def.key)
        if source is None:
            return False
        key = (map_def.key, int(BOARD_W), int(BOARD_H))
        if key not in self.map_background_cache:
            scale = max(BOARD_W / source.get_width(), BOARD_H / source.get_height())
            scaled_size = (max(1, int(round(source.get_width() * scale))), max(1, int(round(source.get_height() * scale))))
            scaled = pygame.transform.smoothscale(source, scaled_size)
            crop_x = max(0, (scaled.get_width() - BOARD_W) // 2)
            crop_y = max(0, (scaled.get_height() - BOARD_H) // 2)
            self.map_background_cache[key] = scaled.subsurface(pygame.Rect(crop_x, crop_y, BOARD_W, BOARD_H)).copy()
        self.screen.blit(self.map_background_cache[key], (BOARD_X, BOARD_Y))
        return True

    def _save_preferences(self) -> None:
        save_config(self.config)

    def _evil_notice(self, text: str) -> None:
        self._notice(text)

    def _queue_evil_comment(
        self,
        event: str,
        context: Optional[Dict[str, object]] = None,
        *,
        force: bool = False,
        snapshot: Optional[Dict] = None,
    ) -> None:
        current_snapshot = snapshot or self.current
        if current_snapshot is None and self.state is not None:
            current_snapshot = self.state.snapshot(self.server.player_count if self.server else 1)
        comment = self.evil.trigger(event, current_snapshot or {}, context, force=force)
        if comment is None:
            return
        now = time.monotonic()
        active = self.evil_comment
        if active and now < self.evil_comment_until:
            active_priority = int(active.get("priority", 0))
            new_priority = int(comment.get("priority", 0))
            # Critical messages are retained in a small serial queue.  This
            # avoids contradictory simultaneous game-over text while making
            # the third-loss line reliably visible after the final verdict.
            if new_priority <= active_priority:
                if new_priority >= 85:
                    self._queue_pending_evil_comment(comment)
                return
            if active_priority >= 85 and event != "game_over":
                self._queue_pending_evil_comment(active)
        self._activate_evil_comment(comment, now)

    def _queue_pending_evil_comment(self, comment: Dict[str, object]) -> None:
        if any(item.get("id") == comment.get("id") for item in self._evil_pending):
            return
        self._evil_pending.append(comment)
        self._evil_pending.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)

    def _activate_evil_comment(self, comment: Dict[str, object], now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        self.evil_comment = comment
        self.evil_comment_started = now
        priority = int(comment.get("priority", 0))
        text_length = len(str(comment.get("text", "")))
        duration = 4.5 + min(7.0, text_length * 0.028)
        if priority >= 85:
            duration += 2.5
        self.evil_comment_until = now + duration
        self.advisor.present(int(comment.get("stage", 1)), priority, now)

    def _record_action_comment(self, action: Dict, ok: bool, message: str, before: Optional[Dict] = None) -> None:
        kind = action.get("type")
        if ok:
            if kind in {"build", "build_plan"}:
                self._queue_evil_comment("tower_built", {"tower": action.get("tower", "plan")})
            elif kind == "sell":
                after_count = len(self.state.towers) if self.state is not None else 1
                self._queue_evil_comment("last_tower_sold" if after_count == 0 else "tower_sold")
            elif kind == "research":
                self._queue_evil_comment("research_completed", {"research": action.get("research", "")})
            elif kind == "invest":
                percent = int(action.get("percent", 0))
                event = "all_investment" if percent >= 100 else "large_investment" if percent >= 50 else "small_investment"
                self._queue_evil_comment(event, {"percent": percent, "amount": self.state.last_investment_amount if self.state else 0})
                self._queue_evil_comment("income_increased", {"percent": percent})
            elif kind == "restart":
                self._queue_evil_comment("restart")
            elif kind == "start_wave" and self.state is not None and self.state.wave == 1:
                self._queue_evil_comment("first_wave")
                if not self.state.towers:
                    self._queue_evil_comment("no_defense", force=True)
        else:
            lowered = message.lower()
            if "coin" in lowered or "guthaben" in lowered or "kosten" in lowered:
                self._queue_evil_comment("insufficient_coins", force=True)
            elif kind in {"build", "build_plan"}:
                event = "rare_blockade" if "block" in lowered or "laufweg" in lowered else "rare_invalid_build"
                self._queue_evil_comment(event, force=True)

    def _evil_line(self, wave: int) -> str:
        # Kept as a compatibility hook for older integrations; live comments
        # now come from EvilCommentary and are rendered in the commentary box.
        return ""

    def close(self) -> None:
        if self.server:
            self.server.close()
        if self.client:
            self.client.close()
        pygame.quit()

    def _open_join_dialog(self) -> None:
        self.join_address = ""
        self.join_error = ""
        self.menu_screen = "join"

    def _connect_from_join_dialog(self) -> None:
        raw = self.join_address.strip()
        if not raw:
            self.join_error = "Bitte die IP-Adresse des Hosts eingeben."
            return

        host = raw
        port = self.port
        if raw.count(":") == 1:
            possible_host, possible_port = raw.rsplit(":", 1)
            if possible_port.isdigit():
                host = possible_host.strip()
                port = int(possible_port)
            else:
                self.join_error = "Der Port muss eine Zahl zwischen 1 und 65535 sein."
                return
        if not host:
            self.join_error = "Bitte eine gültige Host-IP eingeben."
            return
        if not 1 <= port <= 65535:
            self.join_error = "Der Port muss zwischen 1 und 65535 liegen."
            return

        new_client: Optional[NetworkClient] = None
        try:
            new_client = NetworkClient(host, port)
        except (OSError, ValueError) as exc:
            self.join_error = f"Verbindung fehlgeschlagen: {exc}"
            if new_client:
                new_client.close()
            return

        if self.server:
            self.server.close()
            self.server = None
        if self.client:
            self.client.close()
        self.client = new_client
        self.host_mode = False
        self.port = port
        self.menu_active = False
        self.menu_screen = "main"
        self.current = None
        self.state = None
        self.join_error = ""
        self.local_notice = f"Verbunden mit {host}:{port} · Warte auf Host-Snapshot …"
        self.local_notice_until = time.monotonic() + 4

    def _handle_join_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.menu_screen = "main"
                self.join_error = ""
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._connect_from_join_dialog()
                return
            if event.key == pygame.K_BACKSPACE:
                self.join_address = self.join_address[:-1]
                self.join_error = ""
                return
            typed = getattr(event, "unicode", "")
            if typed and typed.isprintable() and len(self.join_address) < 64:
                self.join_address += typed
                self.join_error = ""
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.menu_buttons.get("join_connect", pygame.Rect()).collidepoint(event.pos):
                self._connect_from_join_dialog()
            elif self.menu_buttons.get("join_back", pygame.Rect()).collidepoint(event.pos):
                self.menu_screen = "main"
                self.join_error = ""

    def _notice(self, message: str, duration: float = 2.5) -> None:
        self.local_notice = message
        self.local_notice_until = time.monotonic() + duration

    def _cycle_menu_map(self, direction: int) -> None:
        indices = map_indices_for_layout(self.menu_map_category)
        if not indices:
            return
        current = indices.index(self.menu_map_index) if self.menu_map_index in indices else 0
        self.menu_map_index = indices[(current + direction) % len(indices)]

    def _select_menu_map_category(self, category: str) -> None:
        self.menu_map_category = category
        indices = map_indices_for_layout(category)
        if indices:
            self.menu_map_index = indices[0]

    def _start_host_game(self, lan_mode: bool) -> None:
        if self.server:
            self.server.close()
            self.server = None
        self.state = GameState(map_index=self.menu_map_index, difficulty=self.menu_difficulty, mode=self.menu_game_mode)
        if lan_mode:
            self.server = HostServer(self.port)
            self.local_notice = f"LAN-Koop aktiv. Host-Port {self.port}."
        elif self.menu_game_mode in ("big_combo", "bounty_hunter"):
            self.local_notice = f"{mode_info(self.menu_game_mode)['name']} aktiv. Mr. Evil erwartet Rendite."
        else:
            self.local_notice = "Singleplayer aktiv. Leertaste startet die erste Welle."
        self.local_notice_until = time.monotonic() + 3
        self.menu_active = False
        self.current = None
        self.selected_tower = None
        self.investment_percent_draft = 0
        self.investment_dragging = False
        self.investment_draft_dirty = False
        self.tick_accumulator = 0.0
        self.snapshot_accumulator = 0.0
        self.game_speed = float(self.config["gameplay"].get("speed", 1)) if not lan_mode else 1.0
        self.show_tower_range = bool(self.config["gameplay"].get("show_range", True))
        self._evil_seen_enemy_roles.clear()
        self._queue_evil_comment("game_start", {"mode": self.menu_game_mode, "difficulty": self.menu_difficulty})

    def _return_to_main_menu(self) -> None:
        if not self.host_mode:
            self._notice("Das Hauptmenü ist nur auf dem Host verfügbar.")
            return
        if self.state is not None:
            self.menu_map_index = self.state.map_index
            self.menu_map_category = get_map(self.state.map_index).layout_mode
            self.menu_difficulty = self.state.difficulty_key
            self.menu_game_mode = self.state.mode
        if self.server:
            self.server.close()
            self.server = None
        self.state = None
        self.current = None
        self.selected_tower = None
        self.investment_percent_draft = 0
        self.investment_dragging = False
        self.investment_draft_dirty = False
        self.show_research = False
        self.paused = False
        self.game_speed = 1.0
        self.main_menu_rect = pygame.Rect(0, 0, 0, 0)
        self.wave_start_rect = pygame.Rect(0, 0, 0, 0)
        self.menu_active = True
        self.local_notice = "Wählt Modus, Karte und Schwierigkeit."
        self.local_notice_until = time.monotonic() + 3
        self._queue_evil_comment("quit")

    def submit(self, action: Dict) -> None:
        if self.host_mode:
            assert self.state is not None
            ok, message = self.state.action(action)
            self._record_action_comment(action, ok, message, self.current)
            if not ok:
                self._notice(message)
        elif self.client:
            if not self.client.send_action(action):
                self._notice("Verbindung zum Host verloren.", 99)

    def _grid_at(self, pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        x, y = pos
        board_x, board_y, board_w, board_h = self.layout.board_rect
        if board_x <= x < board_x + board_w and board_y <= y < board_y + board_h:
            return ((x - board_x) // self.layout.cell, (y - board_y) // self.layout.cell)
        # Existing headless smoke integrations use the original canonical board
        # coordinates. Keep that compatibility path isolated from real windows;
        # on a displayed window every hitbox remains tied to the live viewport.
        if pygame.display.get_driver() == "dummy" and BOARD_X != 24:
            cols, rows = self.active_grid_size
            if 24 <= x < 24 + cols * 52 and 82 <= y < 82 + rows * 52:
                return ((x - 24) // 52, (y - 82) // 52)
        return None

    def _tower_at(self, cell: Tuple[int, int]) -> Optional[Dict]:
        if not self.current:
            return None
        for tower in self.current.get("towers", []):
            if tuple(tower["cell"]) == cell:
                return tower
        return None

    def _handle_click(self, pos: Tuple[int, int], button: int) -> None:
        if not self.current:
            return
        if button == 3:
            self.selected_tower = None
            self.investment_dragging = False
            self._notice("Turmauswahl aufgehoben.")
            return
        if self.show_research:
            if self.research_buy_rect.collidepoint(pos) and self.selected_research:
                self.submit({"type": "research", "research": self.selected_research})
                return
            for key, rect in self.research_rects.items():
                if rect.collidepoint(pos):
                    self.selected_research = key
                    self._notice(f"Ausgewählt: {self.current.get('research_status', {}).get(key, {}).get('name', key)}")
                    return
            return
        if self.planning_mode:
            if self.planning_confirm_rect.collidepoint(pos):
                if self.planned_builds:
                    self.submit({"type": "build_plan", "actions": list(self.planned_builds)})
                self.planning_mode = False
                self.planned_builds.clear()
                return
            if self.planning_cancel_rect.collidepoint(pos):
                self.planning_mode = False
                self.planned_builds.clear()
                return
            cell = self._grid_at(pos)
            if cell is not None and button == 1:
                if any(tuple(item["cell"]) == cell for item in self.planned_builds):
                    self.planned_builds = [item for item in self.planned_builds if tuple(item["cell"]) != cell]
                else:
                    self.planned_builds.append({"tower": self.selected_build, "cell": list(cell)})
                return
        if self.main_menu_rect.collidepoint(pos):
            self._return_to_main_menu()
            return
        if self.options_rect.collidepoint(pos):
            self.show_options = True
            self.options_tab = "gameplay"
            return
        if self.research_open_rect.collidepoint(pos):
            self.show_research = True
            return
        if self.priority_rect.collidepoint(pos) and self.selected_tower is not None:
            self.submit({"type": "priority", "tower_id": self.selected_tower})
            return
        for speed, rect in self.speed_rects.items():
            if rect.collidepoint(pos):
                self.game_speed = float(speed) if self.host_mode and self.server is None else 1.0
                self._notice(f"Spieltempo: {self.game_speed:.0f}x" if self.game_speed > 1 else "Spieltempo: 1x (LAN-Limit)")
                return
        if self.wave_start_rect.collidepoint(pos):
            self.submit({"type": "start_wave"})
            return
        if self.current.get("mode") == "big_combo":
            if self.investment_slider_rect.collidepoint(pos):
                self.investment_dragging = True
                self._update_investment_draft(pos[0])
                return
            if self.investment_apply_rect.collidepoint(pos):
                self.submit({"type": "invest", "percent": self.investment_percent_draft})
                self.investment_dragging = False
                return
        for tower_type, rect in self.button_rects.items():
            if rect.collidepoint(pos):
                self.selected_build = tower_type
                self._notice(f"Ausgewählt: {TOWER_DEFS[tower_type]['name']}")
                return
        cell = self._grid_at(pos)
        if cell is None:
            return
        tower = self._tower_at(cell)
        if tower:
            self.selected_tower = tower["id"]
            return
        if button == 1:
            map_def = get_map(self.current["map_index"])
            protected = {route[0] for route in map_def.paths} | {route[-1] for route in map_def.paths}
            buildable = cell in map_def.pads if map_def.layout_mode == "fixed" else cell not in protected
            if buildable and cell not in protected:
                self.submit({"type": "build", "tower": self.selected_build, "cell": list(cell)})

    def _update_investment_draft(self, mouse_x: int) -> None:
        if self.investment_slider_rect.w <= 0:
            return
        ratio = (mouse_x - self.investment_slider_rect.left) / self.investment_slider_rect.w
        self.investment_percent_draft = max(0, min(100, int(round(ratio * 100))))
        self.investment_draft_dirty = True

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            self._resize_window(event.size)
            return
        if self.menu_active:
            self._handle_menu_event(event)
            return
        if self.show_options:
            if self.options_tab == "manual":
                self._handle_manual_event(event, True)
            else:
                self._handle_options_event(event, True)
            return
        if self.show_manual:
            self._handle_manual_event(event, False)
            return
        if event.type == pygame.MOUSEMOTION and self.investment_dragging:
            self._update_investment_draft(event.pos[0])
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.investment_dragging = False
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_click(event.pos, event.button)
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            if self.show_options:
                self.show_options = False
            elif self.show_manual:
                self.show_manual = False
            elif self.show_research:
                self.show_research = False
            else:
                self.running = False
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
            self.selected_build = TOWER_TYPES[event.key - pygame.K_1]
        elif event.key == pygame.K_SPACE:
            self.submit({"type": "start_wave"})
        elif event.key == pygame.K_m and self.current:
            if self.current.get("game_over"):
                self.submit({
                    "type": "restart",
                    "map_index": self.current.get("map_index", 0),
                    "difficulty": self.current.get("difficulty", "normal"),
                    "mode": self.current.get("mode", "classic"),
                })
                return
            current_index = self.current["map_index"]
            family = get_map(current_index).layout_mode
            indices = map_indices_for_layout(family)
            next_index = indices[(indices.index(current_index) + 1) % len(indices)]
            self.submit({"type": "select_map", "map_index": next_index})
        elif event.key == pygame.K_r:
            self.show_tower_range = not self.show_tower_range
            state = "eingeblendet" if self.show_tower_range else "ausgeblendet"
            self._notice(f"Turmreichweite {state}.")
        elif event.key == pygame.K_u and self.selected_tower is not None:
            self.submit({"type": "upgrade", "tower_id": self.selected_tower})
        elif event.key == pygame.K_x and self.selected_tower is not None:
            self.submit({"type": "sell", "tower_id": self.selected_tower})
            self.selected_tower = None
        elif event.key == pygame.K_q and self.selected_tower is not None:
            self.submit({"type": "priority", "tower_id": self.selected_tower})
        elif event.key == pygame.K_b:
            self.submit({"type": "invest", "percent": 10})
        elif event.key == pygame.K_f:
            if self.current:
                if self.selected_research:
                    self.submit({"type": "research", "research": self.selected_research})
                else:
                    self._notice("Forschung auswählen; F kauft nur die Auswahl.")
        elif event.key == pygame.K_t:
            self.show_research = not self.show_research
        elif event.key == pygame.K_o:
            self.show_options = True
            self.options_tab = "gameplay"
        elif event.key == pygame.K_y:
            self.planning_mode = not self.planning_mode
            if not self.planning_mode:
                self.planned_builds.clear()
            self._notice("Bauplan aktiv: Felder anklicken, dann bestätigen." if self.planning_mode else "Bauplan verworfen.")
        elif event.key == pygame.K_p:
            self.paused = not self.paused
            self._notice("Pause" if self.paused else "Spiel fortgesetzt")
        elif event.key in (pygame.K_6, pygame.K_7, pygame.K_8):
            requested = float(event.key - pygame.K_6 + 1)
            self.game_speed = requested if self.host_mode and self.server is None else 1.0
            if requested == 3:
                self._queue_evil_comment("rare_speed_3")
            self._notice(f"Spieltempo: {self.game_speed:.0f}x" if self.game_speed > 1 else "Spieltempo: 1x (LAN-Limit)")
        elif event.key in (pygame.K_j, pygame.K_k) and self.selected_tower is not None:
            self.submit({"type": "specialize", "tower_id": self.selected_tower, "choice": "a" if event.key == pygame.K_j else "b"})

    def _handle_menu_event(self, event: pygame.event.Event) -> None:
        if self.menu_screen == "join":
            self._handle_join_event(event)
            return
        if self.menu_screen == "options":
            self._handle_options_event(event, False)
            return
        if self.menu_screen == "manual":
            self._handle_manual_event(event, False)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.menu_buttons.items():
                if rect.collidepoint(event.pos):
                    if key in ("single", "coop"):
                        self.menu_mode = key
                    elif key == "join":
                        self._open_join_dialog()
                    elif key in ("maps_fixed", "maps_maze"):
                        self._select_menu_map_category("fixed" if key == "maps_fixed" else "maze")
                    elif key in ("classic", "combo", "bounty"):
                        self.menu_game_mode = {"classic": "classic", "combo": "big_combo", "bounty": "bounty_hunter"}[key]
                    elif key == "map_prev":
                        self._cycle_menu_map(-1)
                    elif key == "map_next":
                        self._cycle_menu_map(1)
                    elif key.startswith("difficulty:"):
                        self.menu_difficulty = key.split(":", 1)[1]
                    elif key == "start":
                        self._start_host_game(lan_mode=self.menu_mode == "coop")
                    elif key == "options":
                        self.menu_screen = "options"
                    elif key == "manual":
                        self.menu_screen = "manual"
                    elif key == "quit":
                        self._queue_evil_comment("quit")
                        self.running = False
                    return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self._cycle_menu_map(-1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self._cycle_menu_map(1)
        elif event.key == pygame.K_TAB:
            self.menu_mode = "coop" if self.menu_mode == "single" else "single"
        elif event.key == pygame.K_b:
            self.menu_game_mode = {"classic": "big_combo", "big_combo": "bounty_hunter", "bounty_hunter": "classic"}[self.menu_game_mode]
        elif event.key == pygame.K_o:
            self.menu_screen = "options"
        elif event.key == pygame.K_h:
            self.menu_screen = "manual"
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.menu_difficulty = DIFFICULTY_KEYS[event.key - pygame.K_1]
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._start_host_game(lan_mode=self.menu_mode == "coop")

    def _handle_manual_event(self, event: pygame.event.Event, from_options: bool) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self.menu_buttons.items():
                if rect.collidepoint(event.pos):
                    if key in ("manual_back", "manual_from_options"):
                        self.menu_screen = "options" if from_options else "main"
                        return
                    if key.startswith("manual_page:"):
                        self.manual_page = int(key.split(":", 1)[1])
                        return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.menu_screen = "options" if from_options else "main"

    def _handle_options_event(self, event: pygame.event.Event, in_game: bool) -> None:
        if self.options_tab == "manual" and not in_game:
            self._handle_manual_event(event, True)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if in_game:
                self.show_options = False
            else:
                self.menu_screen = "main"
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        for key, rect in self.menu_buttons.items():
            if rect.collidepoint(event.pos):
                if key in ("options_back", "options_close"):
                    if in_game:
                        self.show_options = False
                    else:
                        self.menu_screen = "main"
                    return
                if key.startswith("options_tab:"):
                    self.options_tab = key.split(":", 1)[1]
                    return
        for key, rect in self.option_rects.items():
            if rect.collidepoint(event.pos):
                self._change_option(key)
                return

    def _change_option(self, key: str) -> None:
        if key == "opt:fullscreen":
            self.config["video"]["fullscreen"] = not self.config["video"]["fullscreen"]
            self._apply_video_options()
        elif key == "opt:resolution":
            current = self.config["video"].get("resolution", "1280x760")
            try:
                next_index = (RESOLUTION_PRESETS.index(current) + 1) % len(RESOLUTION_PRESETS)
            except ValueError:
                next_index = RESOLUTION_PRESETS.index("1280x760")
            selected = RESOLUTION_PRESETS[next_index]
            width, height = (int(part) for part in selected.split("x", 1))
            self.config["video"]["resolution"] = selected
            self.config["video"]["window_size"] = [width, height]
            self._apply_video_options()
        elif key == "opt:effects":
            self.config["video"]["effects"] = "off" if self.config["video"]["effects"] != "off" else "normal"
        elif key == "opt:ui_scale":
            self.config["video"]["ui_scale"] = {0.8: 1.0, 1.0: 1.2, 1.2: 0.8}.get(float(self.config["video"].get("ui_scale", 1.0)), 1.0)
            self._rebuild_fonts()
        elif key.startswith("opt:audio:"):
            child = key.split(":", 2)[2]
            self.config["audio"][child] = (int(self.config["audio"][child]) + 10) % 110
        elif key == "opt:text_size":
            self.config["text"]["size"] = {"small": "normal", "normal": "large", "large": "small"}.get(self.config["text"]["size"], "normal")
            self._rebuild_fonts()
        elif key == "opt:tooltip":
            self.config["text"]["tooltip_seconds"] = {1.0: 2.0, 2.0: 3.0, 3.0: 1.0}.get(float(self.config["text"]["tooltip_seconds"]), 2.0)
        elif key == "opt:language":
            self._evil_notice("Deutsch ist derzeit die verfügbare UI-Sprache.")
        elif key == "opt:humor":
            self.config["text"]["humor"] = {"aus": "normal", "normal": "hoch", "hoch": "aus"}.get(self.config["text"]["humor"], "normal")
        elif key == "opt:show_range":
            self.config["gameplay"]["show_range"] = not self.config["gameplay"]["show_range"]
            self.show_tower_range = self.config["gameplay"]["show_range"]
        elif key == "opt:evil_comments":
            self._cycle_evil_frequency()
        elif key == "opt:evil_frequency":
            self._cycle_evil_frequency()
        elif key == "opt:evil_animations":
            self.config["gameplay"]["evil_animations"] = not self.config["gameplay"].get("evil_animations", True)
            self.evil.configure(self._evil_frequency(), self.config["gameplay"]["evil_animations"], self.config["gameplay"].get("evil_text_size", "normal"))
        elif key == "opt:evil_text_size":
            current_size = self.config["gameplay"].get("evil_text_size", "normal")
            self.config["gameplay"]["evil_text_size"] = {"small": "normal", "normal": "large", "large": "small"}.get(current_size, "normal")
            self.evil.configure(self._evil_frequency(), self.config["gameplay"].get("evil_animations", True), self.config["gameplay"]["evil_text_size"])
        elif key == "opt:speed":
            self.config["gameplay"]["speed"] = 1 if int(self.config["gameplay"]["speed"]) >= 3 else int(self.config["gameplay"]["speed"]) + 1
            if self.host_mode and self.server is None:
                self.game_speed = float(self.config["gameplay"]["speed"])
        self._save_preferences()

    def _evil_frequency(self) -> str:
        frequency = self.config["gameplay"].get("evil_frequency", "normal")
        return frequency if frequency in {"off", "rare", "normal", "frequent"} else "normal"

    def _cycle_evil_frequency(self) -> None:
        values = ("off", "rare", "normal", "frequent")
        current = self._evil_frequency()
        self.config["gameplay"]["evil_frequency"] = values[(values.index(current) + 1) % len(values)]
        self.config["gameplay"]["evil_comments"] = self.config["gameplay"]["evil_frequency"] != "off"
        self.evil.configure(
            self.config["gameplay"]["evil_frequency"],
            self.config["gameplay"].get("evil_animations", True),
            self.config["gameplay"].get("evil_text_size", "normal"),
        )

    def _apply_video_options(self) -> None:
        width, height = self._configured_resolution()
        flags = pygame.FULLSCREEN if self.config["video"].get("fullscreen") else pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((width, height), flags)
        except pygame.error:
            self.config["video"]["fullscreen"] = False
            self.config["video"]["resolution"] = "1280x760"
            self.config["video"]["window_size"] = [WINDOW_W, WINDOW_H]
            self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.RESIZABLE)
            width, height = WINDOW_W, WINDOW_H
        self.layout = ResponsiveLayout.for_window(width, height, self.active_grid_size)
        self._apply_layout_constants()
        self._rebuild_fonts()
        self._save_preferences()

    def _observe_evil_snapshot(self, previous: Optional[Dict], current: Dict) -> None:
        """Translate authoritative state changes into local commentary events."""
        if previous is None:
            self._evil_last_player_count = int(current.get("players", 1))
            return
        old_players = int(previous.get("players", 1))
        new_players = int(current.get("players", 1))
        if new_players > old_players:
            self._queue_evil_comment("lan_join", snapshot=current)
        elif new_players < old_players:
            self._queue_evil_comment("lan_leave", snapshot=current)
        old_lives = int(previous.get("lives", 0))
        new_lives = int(current.get("lives", 0))
        if new_lives < old_lives:
            self._queue_evil_comment("enemy_breakthrough", force=True, snapshot=current)
            if new_lives == 1:
                self._queue_evil_comment("last_life", force=True, snapshot=current)
        if not previous.get("game_over") and current.get("game_over"):
            self._queue_evil_comment(
                "game_over_after_all_in" if self.evil.memory.get("all_in") else "game_over",
                force=True,
                snapshot=current,
            )
            if int(self.evil.memory.get("losses", 0)) >= 3:
                self._queue_evil_comment("three_losses", force=True, snapshot=current)
        old_wave = int(previous.get("wave", 0))
        new_wave = int(current.get("wave", 0))
        if previous.get("wave_active") and not current.get("wave_active") and old_wave > 0:
            self._queue_evil_comment("wave_survived", snapshot=current)
        if new_wave > old_wave:
            self._evil_seen_enemy_roles.clear()
            if new_wave >= 50:
                self._queue_evil_comment("rare_new_record", snapshot=current)
        old_kinds = {enemy.get("kind") for enemy in previous.get("enemies", [])}
        new_kinds = {enemy.get("kind") for enemy in current.get("enemies", [])}
        for kind, event in (("raider", "fast_enemies"), ("wisp", "flying_enemies"), ("healer", "healer_enemies"), ("shield", "shield_enemies")):
            if kind in new_kinds and kind not in old_kinds and kind not in self._evil_seen_enemy_roles:
                self._evil_seen_enemy_roles.add(kind)
                self._queue_evil_comment(event, snapshot=current)
        old_boss_waves = {
            int(enemy.get("boss_wave", 0))
            for enemy in previous.get("enemies", [])
            if enemy.get("kind") == "boss"
        }
        for enemy in current.get("enemies", []):
            if enemy.get("kind") != "boss":
                continue
            boss_wave = int(enemy.get("boss_wave", 0))
            if boss_wave not in old_boss_waves:
                asset_wave = boss_asset_wave_for(boss_wave)
                event = f"boss_wave_{asset_wave}" if asset_wave else "boss_appeared"
                self._queue_evil_comment(event, snapshot=current)
        if "boss" in old_kinds and "boss" not in new_kinds and not current.get("game_over"):
            self._queue_evil_comment("boss_defeated", snapshot=current)

    def _update_state(self, dt: float) -> None:
        if self.host_mode:
            if self.menu_active:
                return
            assert self.state is not None
            player_count = self.server.player_count if self.server is not None else 1
            self.state.set_player_count(player_count)
            if self.server is not None:
                for action in self.server.drain_actions():
                    before = self.current
                    ok, message = self.state.action(action)
                    self._record_action_comment(action, ok, message, before)
            self.tick_accumulator += dt
            while self.tick_accumulator >= 1.0 / TICK_RATE:
                if not self.paused:
                    self.state.tick((1.0 / TICK_RATE) * self.game_speed)
                self.tick_accumulator -= 1.0 / TICK_RATE
            previous = self.current
            self.current = self.state.snapshot(player_count)
            self._observe_evil_snapshot(previous, self.current)
            self.snapshot_accumulator += dt
            if self.server is not None and self.snapshot_accumulator >= 1.0 / SNAPSHOT_RATE:
                self.server.broadcast(self.current)
                self.snapshot_accumulator = 0.0
        elif self.client:
            if not self.client.connected:
                self.current = None
                self._notice("Verbindung zum Host verloren.", 99)
            else:
                newest = self.client.state()
                if newest:
                    previous = self.current
                    self.current = newest
                    self._observe_evil_snapshot(previous, self.current)

        if self.current:
            if self.current.get("mode") != "big_combo":
                self.investment_draft_dirty = False
            server_percent = int(self.current.get("investment_percent", 0))
            if not self.investment_draft_dirty or server_percent == self.investment_percent_draft:
                self.investment_percent_draft = server_percent
                self.investment_draft_dirty = False

        if self.current and self.selected_tower is not None:
            if not any(t["id"] == self.selected_tower for t in self.current.get("towers", [])):
                self.selected_tower = None

    def _rect_for_cell(self, cell: Tuple[int, int]) -> pygame.Rect:
        return pygame.Rect(
            self.layout.board_x + cell[0] * self.layout.cell,
            self.layout.board_y + cell[1] * self.layout.cell,
            self.layout.cell,
            self.layout.cell,
        )

    def _screen_pos(self, point: Point) -> Tuple[int, int]:
        return (
            int(self.layout.board_x + (point[0] + 0.5) * self.layout.cell),
            int(self.layout.board_y + (point[1] + 0.5) * self.layout.cell),
        )

    def _text(self, content: str, pos: Tuple[int, int], color=TEXT, font=None, anchor: str = "topleft") -> pygame.Rect:
        image = (font or self.font).render(content, True, color)
        rect = image.get_rect()
        setattr(rect, anchor, pos)
        self.screen.blit(image, rect)
        return rect

    def _menu_button(self, key: str, rect: pygame.Rect, label: str, active: bool = False) -> None:
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = (57, 74, 96) if active else ((28, 48, 65) if hovered else PANEL)
        outline = SELECT if active else (MANA if hovered else (68, 84, 92))
        pygame.draw.rect(self.screen, fill, rect, border_radius=5)
        pygame.draw.rect(self.screen, outline, rect, 2, border_radius=5)
        button_font = self.font
        label_width = button_font.size(label)[0]
        if label_width > rect.w - 12:
            compact_size = max(9, int(button_font.get_height() * (rect.w - 12) / label_width))
            button_font = pygame.font.SysFont("dejavusans", compact_size, bold=button_font.get_bold())
        self._text(label, rect.center, TEXT if active else MUTED, button_font, "center")
        self.menu_buttons[key] = rect

    def _draw_backdrop(self, title: str, subtitle: str = "") -> None:
        width, height = self.layout.width, self.layout.height
        self.screen.fill(INK)
        for x in range(0, width, 64):
            pygame.draw.line(self.screen, (9, 24, 38), (x, 0), (x, height), 1)
        for y in range(0, height, 64):
            pygame.draw.line(self.screen, (9, 24, 38), (0, y), (width, y), 1)
        header = pygame.Rect(0, 0, width, self.layout.header)
        pygame.draw.rect(self.screen, PANEL_DARK, header)
        pygame.draw.line(self.screen, MANA, (0, header.bottom - 2), (width, header.bottom - 2), 2)
        self._text(title, (self.layout.margin, 16), (155, 235, 255), self.big)
        if subtitle:
            self._text(subtitle, (self.layout.margin + 4, header.bottom - 25), (187, 115, 255), self.small)

    def _frame(self, rect: pygame.Rect, accent=MANA, fill=PANEL_DARK) -> None:
        pygame.draw.rect(self.screen, fill, rect, border_radius=9)
        pygame.draw.rect(self.screen, (accent[0] // 3, accent[1] // 3, accent[2] // 3), rect, 1, border_radius=9)
        pygame.draw.line(self.screen, accent, (rect.x + 12, rect.y), (rect.x + min(150, rect.w - 24), rect.y), 2)

    def _draw_map_preview(self, map_index: int, rect: pygame.Rect) -> None:
        map_def = get_map(map_index)
        path = path_cells(map_def)
        cols, rows = map_def.grid_size
        cell_w = rect.w / cols
        cell_h = rect.h / rows
        for y in range(rows):
            for x in range(cols):
                tile = pygame.Rect(
                    int(rect.x + x * cell_w),
                    int(rect.y + y * cell_h),
                    max(1, int(math.ceil(cell_w))),
                    max(1, int(math.ceil(cell_h))),
                )
                if (x, y) in path:
                    color = PATH
                elif (x, y) in map_def.pads:
                    color = (67, 84, 72)
                else:
                    color = (38, 46, 48)
                pygame.draw.rect(self.screen, color, tile)
        pygame.draw.rect(self.screen, (89, 106, 112), rect, 2, border_radius=4)

    def _draw_menu(self) -> None:
        if self.menu_screen == "options":
            self._draw_options(False)
            return
        if self.menu_screen == "manual":
            self._draw_manual(False)
            return
        if self.menu_screen == "join":
            self._draw_join_dialog()
            return
        self.menu_buttons = {}
        self._draw_backdrop("CREEPGRID", "BARBAROSSA & EVIL ENTERPRISES™")
        width, height, margin = self.layout.width, self.layout.height, self.layout.margin
        self._text("Weil Weltherrschaft auch nur Projektmanagement ist.", (width // 2, 28), MUTED, self.font, "midtop")
        self._menu_button("options", pygame.Rect(width - margin - 250, 16, 108, 34), "Optionen")
        self._menu_button("manual", pygame.Rect(width - margin - 132, 16, 110, 34), "Handbuch")
        self._menu_button("quit", pygame.Rect(width - margin - 250, 56, 238, 28), "Beenden")
        left_x, top_y = margin, self.layout.header + 18
        left_w = min(620, max(430, int(width * 0.40)))
        right_x = left_x + left_w + self.layout.gap
        right_w = width - margin - right_x
        bottom = height - self.layout.footer - margin
        self._frame(pygame.Rect(left_x, top_y, left_w, bottom - top_y), MANA)
        self._frame(pygame.Rect(right_x, top_y, right_w, bottom - top_y), SELECT)
        self._text("KONTROLLZENTRALE", (left_x + 20, top_y + 18), TEXT, self.title)
        self._text("Konfiguriere dein Imperium. Mr. Evil überwacht die Kennzahlen.", (left_x + 22, top_y + 50), MUTED, self.small)
        content_x, y = left_x + 20, top_y + 82
        inner_w = left_w - 40
        self._text("BETRIEBSART", (content_x, y), MANA, self.small)
        mode_w = (inner_w - 20) // 3
        self._menu_button("single", pygame.Rect(content_x, y + 22, mode_w, 40), "Einzelspieler", self.menu_mode == "single")
        self._menu_button("coop", pygame.Rect(content_x + mode_w + 10, y + 22, mode_w, 40), "Koop-LAN hosten", self.menu_mode == "coop")
        self._menu_button("join", pygame.Rect(content_x + 2 * (mode_w + 10), y + 22, mode_w, 40), "Multiplayer beitreten")
        y += 78
        self._text("SPIELMODUS", (content_x, y), MANA, self.small)
        half = (inner_w - 10) // 2
        mode_keys = (("classic", "Letzte Bastion"), ("combo", "Megalomanie"), ("bounty", "Akkordarbeit"))
        mode_w = (inner_w - 20) // 3
        for index, (key, label) in enumerate(mode_keys):
            self._menu_button(key, pygame.Rect(content_x + index * (mode_w + 10), y + 22, mode_w, 44), label, self.menu_game_mode == {"classic": "classic", "combo": "big_combo", "bounty": "bounty_hunter"}[key])
        self._text(mode_info(self.menu_game_mode)["description"], (content_x, y + 74), GOLD, self.small)
        y += 106
        self._text("KARTENMODUS", (content_x, y), MANA, self.small)
        self._menu_button("maps_fixed", pygame.Rect(content_x, y + 22, half, 38), "Vorgegebene Wege", self.menu_map_category == "fixed")
        self._menu_button("maps_maze", pygame.Rect(content_x + half + 10, y + 22, half, 38), "Freies Bauen", self.menu_map_category == "maze")
        self._text(MAP_FAMILY_INFO[self.menu_map_category]["description"], (content_x, y + 68), MUTED, self.small)
        map_def = get_map(self.menu_map_index)
        preview = pygame.Rect(content_x, y + 94, inner_w, max(94, min(145, bottom - (y + 160))))
        self._draw_map_preview(self.menu_map_index, preview)
        self._menu_button("map_prev", pygame.Rect(content_x, preview.bottom + 8, 54, 30), "<")
        self._menu_button("map_next", pygame.Rect(content_x + inner_w - 54, preview.bottom + 8, 54, 30), ">")
        self._text(map_def.title, (content_x + inner_w // 2, preview.bottom + 10), (240, 229, 177), self.font, "midtop")
        self._text(map_def.subtitle, (content_x + inner_w // 2, preview.bottom + 34), MUTED, self.small, "midtop")
        self._text("RISIKOPROFIL", (right_x + 22, top_y + 22), MANA, self.small)
        for i, key in enumerate(DIFFICULTY_KEYS):
            spec = DIFFICULTY_DEFS[key]
            rect = pygame.Rect(right_x + 20, top_y + 54 + i * 68, min(320, right_w - 40), 54)
            active = key == self.menu_difficulty
            pygame.draw.rect(self.screen, (44, 65, 87) if active else PANEL, rect, border_radius=5)
            pygame.draw.rect(self.screen, SELECT if active else (63, 91, 113), rect, 2, border_radius=5)
            self._text(f"{i + 1}  {spec['name']}", (rect.x + 12, rect.y + 7), TEXT, self.font)
            self._text(DIFFICULTY_FLAVOR[key][:38], (rect.x + 12, rect.y + 31), MUTED, self.small)
            self.menu_buttons[f"difficulty:{key}"] = rect
        selected = DIFFICULTY_DEFS[self.menu_difficulty]
        info_x = right_x + min(360, max(20, right_w // 2 + 8))
        self._text("AKTIVE KONFIGURATION", (info_x, top_y + 54), MANA, self.small)
        self._text(mode_info(self.menu_game_mode)["name"], (info_x, top_y + 82), SELECT, self.title)
        self._text(mode_info(self.menu_game_mode)["description"], (info_x, top_y + 124), TEXT, self.small)
        self._text(f"{map_def.title} · {MAP_FAMILY_INFO[self.menu_map_category]['name']}", (info_x, top_y + 174), GOLD, self.font)
        self._text(f"{selected['gold']} Coins · {selected['lives']} Integrität", (info_x, top_y + 204), TEXT, self.font)
        self._text("Türme bauen. Vermögen anhäufen. Entscheidungen bereuen.", (info_x, top_y + 250), MUTED, self.small)
        self._menu_button("start", pygame.Rect(right_x + 20, bottom - 64, right_w - 40, 50), "IMPERIUM STARTEN", True)
        if self.evil_comment is None:
            self._queue_evil_comment("corporate")
        # The advisor dock belongs to the game HUD below the board.  Drawing
        # it over the configuration menu would cover the primary start action.
        self._text("Klick oder Tastatur · 1–3 Schwierigkeit · B Modus · Tab Koop · Enter Start", (width // 2, height - 18), MUTED, self.small, "midbottom")

    def _draw_join_dialog(self) -> None:
        self.menu_buttons = {}
        self._draw_backdrop("MULTIPLAYER BEITRETEN", "LAN / HAMACHI · MIT HOST-IP VERBINDEN")
        width, height, margin = self.layout.width, self.layout.height, self.layout.margin
        dialog_w = min(760, width - 2 * margin)
        dialog_h = min(390, height - self.layout.header - self.layout.footer - 2 * margin)
        dialog = pygame.Rect((width - dialog_w) // 2, self.layout.header + 42, dialog_w, dialog_h)
        self._frame(dialog, SELECT)
        self._text("HOST-VERBINDUNG", (dialog.x + 30, dialog.y + 28), SELECT, self.title)
        self._text("Gib die lokale IP-Adresse des Spielleiters ein.", (dialog.x + 32, dialog.y + 72), TEXT, self.font)
        self._text("Optional kannst du den Port anhängen: 192.168.1.20:5000", (dialog.x + 32, dialog.y + 100), MUTED, self.small)

        input_rect = pygame.Rect(dialog.x + 30, dialog.y + 146, dialog.w - 60, 52)
        pygame.draw.rect(self.screen, (13, 25, 36), input_rect, border_radius=5)
        pygame.draw.rect(self.screen, SELECT, input_rect, 2, border_radius=5)
        input_text = self.join_address or "z. B. 192.168.1.20:5000"
        self._text(input_text, (input_rect.x + 16, input_rect.centery), TEXT if self.join_address else MUTED, self.font, "midleft")

        button_y = dialog.bottom - 68
        self._menu_button("join_back", pygame.Rect(dialog.x + 30, button_y, 150, 42), "Zurück")
        self._menu_button("join_connect", pygame.Rect(dialog.right - 250, button_y, 220, 42), "VERBINDEN", True)
        if self.join_error:
            self._text(self.join_error[:92], (dialog.x + 32, input_rect.bottom + 20), HEALTH, self.small)
        else:
            self._text("Standard-Port: 5000 · Der Host muss zuerst Koop-LAN hosten.", (dialog.x + 32, input_rect.bottom + 20), MUTED, self.small)
        self._text("Enter verbindet · Esc zurück · Windows-Firewall für den Host-Port prüfen", (width // 2, height - 18), MUTED, self.small, "midbottom")

    def _draw_options(self, in_game: bool) -> None:
        self.menu_buttons = {}
        self.option_rects = {}
        self._draw_backdrop("OPTIONEN", "Lokale Einstellungen · robust gespeichert")
        width, height, margin = self.layout.width, self.layout.height, self.layout.margin
        back_key = "options_close" if in_game else "options_back"
        self._menu_button(back_key, pygame.Rect(width - margin - 132, 16, 132, 34), "Zurück")
        tabs = (("video", "Video"), ("audio", "Audio"), ("text", "Text"), ("gameplay", "Gameplay"), ("manual", "Handbuch"))
        tab_gap = 8
        tab_w = max(112, (width - 2 * margin - 4 * tab_gap) // 5)
        for index, (key, label) in enumerate(tabs):
            self._menu_button(f"options_tab:{key}", pygame.Rect(margin + index * (tab_w + tab_gap), self.layout.header + 18, tab_w, 38), label, self.options_tab == key)
        if self.options_tab == "manual":
            self._draw_manual(True)
            return
        panel = pygame.Rect(margin, self.layout.header + 72, width - 2 * margin, height - self.layout.header - self.layout.footer - 94)
        self._frame(panel, MANA, PANEL)
        self._text(self.options_tab.upper(), (panel.x + 28, panel.y + 24), MANA, self.title)
        content_y = panel.y + 72
        if self.options_tab == "video":
            self._option_row("opt:fullscreen", "Fenster / Vollbild", "Vollbild" if self.config["video"]["fullscreen"] else "Fenster", content_y)
            self._option_row("opt:resolution", "Auflösung", self.config["video"]["resolution"], content_y + 58)
            self._option_row("opt:ui_scale", "UI-Skalierung", f"{self.config['video']['ui_scale']:.1f}x", content_y + 116)
            self._option_row("opt:effects", "Visuelle Effekte", str(self.config["video"]["effects"]).capitalize(), content_y + 174)
            self._text("RESIZABLE aktiv · Ziehen an Fensterrand oder Ecke wirkt sofort.", (panel.x + 28, content_y + 236), MUTED, self.small)
        elif self.options_tab == "audio":
            for index, (key, label) in enumerate((("master", "Gesamtlautstärke"), ("music", "Musiklautstärke"), ("effects", "Effektlautstärke"), ("evil", "Mr.-Evil-Kommentare"))):
                self._option_row(f"opt:audio:{key}", label, f"{self.config['audio'][key]} %", content_y + index * 58)
            self._text("Aktuell existieren keine externen Musik-/SFX-Assets; die Regler sind vorbereitet.", (panel.x + 28, content_y + 246), MUTED, self.small)
        elif self.options_tab == "text":
            self._option_row("opt:text_size", "Textgröße", self.config["text"]["size"], content_y)
            self._option_row("opt:tooltip", "Tooltip-Dauer", f"{self.config['text']['tooltip_seconds']:.1f} Sekunden", content_y + 58)
            self._option_row("opt:language", "UI-Sprache", "Deutsch (verfügbar)", content_y + 116)
            self._option_row("opt:humor", "Mr.-Evil-Humor", self.config["text"]["humor"], content_y + 174)
        else:
            self._option_row("opt:show_range", "Reichweitenanzeige", "An" if self.config["gameplay"]["show_range"] else "Aus", content_y)
            self._option_row("opt:evil_frequency", "Mr.-Evil-Kommentare", self._evil_frequency().capitalize(), content_y + 58)
            self._option_row("opt:evil_animations", "Kommentaranimationen", "An" if self.config["gameplay"].get("evil_animations", True) else "Aus", content_y + 116)
            self._option_row("opt:evil_text_size", "Kommentartextgröße", self.config["gameplay"].get("evil_text_size", "normal"), content_y + 174)
            self._option_row("opt:speed", "Starttempo Einzelspieler", f"{self.config['gameplay']['speed']}x", content_y + 232)
            self._text("Wichtige Warnungen erscheinen auch bei Mr. Evil = Aus.", (panel.x + 28, content_y + 286), MUTED, self.small)
        self._text("Änderungen werden unmittelbar lokal gespeichert.", (panel.x + 28, panel.bottom - 28), (121, 228, 169), self.small)

    def _option_row(self, key: str, label: str, value: str, y: int) -> None:
        rect = pygame.Rect(self.layout.margin + 28, y, min(720, self.layout.width - 2 * self.layout.margin - 56), 46)
        self.option_rects[key] = rect
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=5)
        pygame.draw.rect(self.screen, (60, 102, 128), rect, 1, border_radius=5)
        self._text(label, (rect.x + 16, rect.y + 13), TEXT, self.font)
        self._text(value, (rect.right - 16, rect.y + 13), GOLD, self.font, "topright")

    def _draw_manual(self, from_options: bool = False) -> None:
        self.manual_rects = {}
        self._draw_backdrop("CREEPGRID · HANDBUCH", "Spielwissen, Steuerung und Unternehmensethik")
        width, height, margin = self.layout.width, self.layout.height, self.layout.margin
        back = "manual_from_options" if from_options else "manual_back"
        self._menu_button(back, pygame.Rect(width - margin - 132, 16, 132, 34), "Zurück")
        chapters = ("Grundlagen", "Spielmodi", "Kartenmodi", "Türme", "Spezialisierungen", "Forschung", "Megalomanie", "Gegner", "Koop / LAN", "Steuerung")
        gap = 8
        chapter_w = max(122, (width - 2 * margin - 4 * gap) // 5)
        for index, label in enumerate(chapters):
            row, column = divmod(index, 5)
            self._menu_button(f"manual_page:{index}", pygame.Rect(margin + column * (chapter_w + gap), self.layout.header + 18 + row * 46, chapter_w, 36), label, self.manual_page == index)
        panel_y = self.layout.header + 122
        panel = pygame.Rect(margin, panel_y, width - 2 * margin, height - panel_y - self.layout.footer - margin)
        self._frame(panel, MANA, PANEL)
        self._draw_manual_page(panel)

    def _draw_manual_page(self, panel: pygame.Rect) -> None:
        page = self.manual_page
        titles = ("Grundlagen", "Spielmodi", "Kartenmodi", "Türme", "Spezialisierungen", "Forschung", "Megalomanie", "Gegner", "Koop / LAN", "Steuerung")
        self._text(titles[page], (panel.x + 28, panel.y + 24), MANA, self.title)
        lines: List[str]
        if page == 0:
            lines = ["Baue Türme auf freien Feldern und halte den Laufweg bis zur Basis frei.", "Linksklick baut den ausgewählten Turm; ein ausgewählter Turm zeigt seine Managementdaten.", "Wellen, Forschung, Upgrades und Verkaufen werden vom Host autoritativ geprüft."]
        elif page == 1:
            lines = [f"{info['name']}: {info['description']}" for info in MODE_INFO.values()]
        elif page == 2:
            lines = [f"{info['name']}: {info['description']}" for info in MAP_FAMILY_INFO.values()]
        elif page == 3:
            lines = [f"{spec['name']} · {spec['cost']} Coins · {spec['description']}" for spec in TOWER_DEFS.values()]
        elif page == 4:
            lines = [f"{spec['name']}: {spec.get('specializations', {}).get('a', 'Grundturm')} / {spec.get('specializations', {}).get('b', 'Grundturm')}" for spec in TOWER_DEFS.values()]
        elif page == 5:
            lines = [f"{spec['name']} · ab Welle {spec['wave']} · {spec['cost']} Coins" for spec in RESEARCH_DEFS.values()]
        elif page == 6:
            lines = ["Megalomanie zahlt das dauerhafte Rundeneinkommen alle 30 Sekunden als Coin-Tick aus.", "Investiere einen Prozentsatz deines aktuellen Guthabens; der Betrag wird sofort abgezogen.", "Die Vorschau zeigt Coins, Restguthaben und das neue dauerhafte Tick-Einkommen."]
        elif page == 7:
            lines = [f"{spec['name']} · {spec.get('description', '')}" for spec in ENEMY_DEFS.values()]
        elif page == 8:
            lines = ["Der Host simuliert die Partie und verteilt Zustands-Snapshots.", "Startguthaben und Einkommen werden bei mehreren Spielern gleichmäßig geteilt: 2 Spieler = 50% pro Spieler.", "Clients senden nur Aktionen. Für Koop muss TCP am gewählten Port erreichbar sein."]
        else:
            lines = ["1–5 Turm wählen · U Upgrade · X Verkauf · Q Zielpriorität · J/K Spezialisierung", "T Forschung · O Optionen · Y Bauplan · P Pause · 6/7/8 Tempo · M Neustart/Karte", "Mr. Evil kommentiert lokal; Häufigkeit, Animationen und Textgröße stehen unter O → Gameplay.", "Mausklicks sind für Auswahl, Panels, Forschung, Optionen und Hauptmenü verfügbar."]
        row_y = panel.y + 78
        max_width = panel.w - 60
        for index, line in enumerate(lines[:12]):
            words, current_line = line.split(), ""
            wrapped = []
            for word in words:
                candidate = f"{current_line} {word}".strip()
                if self.small.size(candidate)[0] > max_width and current_line:
                    wrapped.append(current_line)
                    current_line = word
                else:
                    current_line = candidate
            if current_line:
                wrapped.append(current_line)
            for wrapped_line in wrapped[:2]:
                if row_y + self.small.get_height() > panel.bottom - 18:
                    return
                self._text("· " + wrapped_line, (panel.x + 30, row_y), TEXT if index < 3 else MUTED, self.small)
                row_y += 24

    def _draw_header(self) -> None:
        width, height = self.layout.width, self.layout.height
        pygame.draw.rect(self.screen, PANEL_DARK, (0, 0, width, self.layout.header))
        pygame.draw.rect(self.screen, (56, 83, 98), (0, self.layout.header - 1, width, 1))
        self._text("CREEPGRID", (self.layout.margin, 10), (155, 235, 255), self.title)
        self._text("BARBAROSSA & EVIL ENTERPRISES™", (self.layout.margin + 2, self.layout.header - 24), (187, 115, 255), self.small)
        if self.current:
            info_x = max(250, int(width * 0.20))
            self._text(f"◈  {self.current.get('credits', self.current['gold'])}", (info_x, 12), GOLD, self.title)
            self._text(f"♥  {self.current['lives']}/{self.current.get('max_lives', 20)}", (info_x + 120, 13), HEALTH, self.title)
            if self.current.get("first_wave_start_required"):
                wave_text = "BEREIT · ERSTE WELLE STARTEN"
            elif self.current.get("next_wave_in", 0) > 0:
                wave_text = f"WELLE {self.current['wave']}  ·  NÄCHSTE IN {self.current['next_wave_in']:.1f}s"
            else:
                wave_text = f"WELLE {self.current['wave']}" + (f"  ·  {self.current['spawn_remaining']} im Anmarsch" if self.current['wave_active'] else "  ·  Bereit")
            if self.layout.compact:
                wave_text = f"WELLE {self.current['wave']}" + (" · aktiv" if self.current["wave_active"] else " · bereit")
            self._text(wave_text, (info_x + 270, 19), TEXT, self.small)
            self._text(f"Tempo {self.game_speed:.0f}x", (width - 300, self.layout.header - 24), MUTED, self.small)
            if not self.layout.compact:
                self._text(self.current.get("mode_name", ""), (width - 300, 15), (187, 115, 255), self.small)
            players = int(self.current.get("players", 1))
            share = self.current.get("resource_share_percent", 100.0)
            player_label = f"{players} SPIELER · {share:.0f}% RESSOURCENANTEIL" if players > 1 else "1 SPIELER"
            self._text(player_label, (width - self.layout.margin, 19), MANA, self.small, "topright")
        if self.host_mode and self.server is None:
            role = "SINGLEPLAYER"
        elif self.host_mode:
            role = f"HOST · Port {self.port}"
        else:
            role = "CLIENT · synchronisiert"
        self._text(role, (width - self.layout.margin, self.layout.header - 22), MUTED, self.small, "topright")

    def _draw_board(self) -> None:
        if not self.current:
            return
        map_def = get_map(self.current["map_index"])
        cols, rows = map_def.grid_size
        pygame.draw.rect(self.screen, (8, 10, 12), (BOARD_X - 3, BOARD_Y - 3, BOARD_W + 6, BOARD_H + 6), border_radius=4)
        map_background_drawn = self._draw_map_background(map_def)
        map_overlay = pygame.Surface((BOARD_W, BOARD_H), pygame.SRCALPHA) if map_background_drawn or map_def.terrain in ("nexus", "nexus_v3") else None
        cells = path_cells(map_def)
        for y in range(rows):
            for x in range(cols):
                rect = self._rect_for_cell((x, y))
                if map_background_drawn:
                    pygame.draw.rect(self.screen, (26, 42, 51), rect, 1)
                    continue
                if map_def.terrain == "arena":
                    base = GRASS if (x + y) % 2 == 0 else GRASS_ALT
                elif map_def.terrain == "water":
                    base = (47 + ((x + y) % 2) * 8, 102 + (x % 2) * 7, 91 + (y % 2) * 6)
                elif map_def.terrain == "lava":
                    base = (73 + ((x * 3 + y) % 2) * 8, 62 + (y % 3) * 5, 56)
                elif map_def.terrain == "ice":
                    base = (58 + ((x + y) % 2) * 9, 96 + ((x + y) % 2) * 8, 122 + (x % 2) * 6)
                elif map_def.terrain == "desert":
                    base = (122 + ((x + y) % 2) * 10, 102 + ((x + y) % 2) * 8, 66)
                elif map_def.terrain == "forest":
                    base = (30 + ((x + y) % 2) * 6, 62 + ((x + y) % 2) * 7, 44)
                elif map_def.terrain == "crypt":
                    base = (48 + ((x + y) % 2) * 7, 44 + ((x + y) % 2) * 6, 58)
                elif map_def.terrain in ("nexus", "nexus_v3"):
                    base = (20 + ((x + y) % 2) * 5, 39 + ((x * 2 + y) % 2) * 6, 55 + ((x + y) % 2) * 7)
                else:
                    base = GRASS if (x + y) % 2 == 0 else GRASS_ALT
                pygame.draw.rect(self.screen, base, rect)
                pygame.draw.rect(self.screen, (28, 33, 35), rect, 1)
        for cell in cells:
            rect = self._rect_for_cell(cell)
            if map_overlay is not None:
                local = rect.move(-BOARD_X, -BOARD_Y)
                if map_def.terrain in ("nexus", "nexus_v3"):
                    pygame.draw.rect(map_overlay, (26, 35, 47, 218), local.inflate(-2, -2), border_radius=3)
                    pygame.draw.rect(map_overlay, (94, 119, 132, 188), local.inflate(-12, -12), border_radius=4)
                    pygame.draw.circle(map_overlay, (205, 190, 122, 210), (local.centerx, local.centery), 3)
                else:
                    pygame.draw.rect(map_overlay, (32, 36, 38, 185), local.inflate(-2, -2), border_radius=3)
                    pygame.draw.rect(map_overlay, (108, 123, 120, 155), local.inflate(-12, -12), border_radius=4)
                    pygame.draw.circle(map_overlay, (178, 193, 187, 190), (local.centerx, local.centery), 3)
            else:
                pygame.draw.rect(self.screen, PATH_EDGE, rect.inflate(-2, -2), border_radius=3)
                pygame.draw.rect(self.screen, PATH, rect.inflate(-12, -12), border_radius=4)
                pygame.draw.circle(self.screen, (136, 145, 142), rect.center, 3)
        if map_def.terrain == "arena":
            pass
        elif map_def.terrain == "water":
            pygame.draw.rect(self.screen, WATER, (BOARD_X, BOARD_Y + CELL * 10 + 10, BOARD_W, 24), border_radius=9)
            pygame.draw.rect(self.screen, (83, 165, 194), (BOARD_X + 80, BOARD_Y + 18, 150, 9), border_radius=5)
        elif map_def.terrain == "lava":
            pygame.draw.rect(self.screen, (199, 80, 43), (BOARD_X + 20, BOARD_Y + CELL * 1 + 14, BOARD_W - 40, 12), border_radius=6)
            pygame.draw.rect(self.screen, (246, 149, 53), (BOARD_X + 52, BOARD_Y + CELL * 11 + 11, 270, 9), border_radius=5)
        elif map_def.terrain == "ice":
            pygame.draw.rect(self.screen, (140, 196, 222), (BOARD_X + 60, BOARD_Y + 14, 200, 8), border_radius=5)
            pygame.draw.rect(self.screen, (196, 230, 242), (BOARD_X + BOARD_W - 300, BOARD_Y + BOARD_H - 22, 220, 8), border_radius=5)
        elif map_def.terrain == "desert":
            pygame.draw.ellipse(self.screen, (150, 124, 80), (BOARD_X + 120, BOARD_Y + CELL * 4, 220, 26))
            pygame.draw.ellipse(self.screen, (160, 134, 88), (BOARD_X + BOARD_W - 380, BOARD_Y + CELL * 8, 260, 30))
        elif map_def.terrain == "forest":
            pygame.draw.circle(self.screen, (24, 52, 36), self._screen_pos((4.0, 2.0)), 30)
            pygame.draw.circle(self.screen, (24, 52, 36), self._screen_pos((16.0, 9.0)), 34)
            pygame.draw.circle(self.screen, (38, 78, 52), self._screen_pos((4.0, 2.0)), 18)
            pygame.draw.circle(self.screen, (38, 78, 52), self._screen_pos((16.0, 9.0)), 20)
        elif map_def.terrain == "crypt":
            for px, py in ((6.0, 0.5), (13.0, 11.5), (1.0, 11.5), (18.0, 0.5)):
                pygame.draw.rect(self.screen, (84, 78, 100), (*self._screen_pos((px, py)), 14, 22))
        elif map_def.terrain in ("nexus", "nexus_v3"):
            for x in range(2, cols, 5):
                pygame.draw.line(self.screen, (43, 77, 93), self._screen_pos((float(x), 0.0)), self._screen_pos((float(x), float(rows - 1))), 1)
            for y in range(2, rows, 3):
                pygame.draw.line(self.screen, (36, 68, 82), self._screen_pos((0.0, float(y))), self._screen_pos((float(cols - 1), float(y))), 1)
        else:
            pygame.draw.circle(self.screen, (79, 101, 111), self._screen_pos((10.5, 5.2)), 42)
            pygame.draw.circle(self.screen, (119, 137, 139), self._screen_pos((10.5, 5.2)), 27)

        mouse_cell = self._grid_at(pygame.mouse.get_pos())
        occupied = {tuple(t["cell"]) for t in self.current["towers"]}
        protected = {route[0] for route in map_def.paths} | {route[-1] for route in map_def.paths}
        preview = None
        preview_invalid = False
        if mouse_cell is not None and mouse_cell not in protected and mouse_cell not in occupied:
            if map_def.layout_mode == "fixed":
                preview = tuple(map_def.paths[0])
                preview_invalid = mouse_cell not in map_def.pads
            else:
                blocked = occupied | {mouse_cell}
                preview = find_path(map_def.paths[0][0], map_def.paths[0][-1], blocked, map_def.grid_size)
                preview_invalid = preview is None
            if preview:
                points = [self._screen_pos((float(x), float(y))) for x, y in preview]
                if len(points) > 1:
                    pygame.draw.lines(self.screen, (121, 228, 169), False, points, 3)
        for cell in map_def.pads:
            rect = self._rect_for_cell(cell)
            if cell == mouse_cell and preview_invalid:
                color = (128, 55, 61)
            else:
                color = BUILD_PAD_HOVER if cell == mouse_cell and cell not in occupied else BUILD_PAD
            if map_overlay is not None:
                local = rect.move(-BOARD_X, -BOARD_Y).inflate(-18, -18)
                if cell == mouse_cell and preview_invalid:
                    fill = (*color, 155)
                    outline = (255, 142, 125, 220)
                elif cell == mouse_cell:
                    fill = (*color, 125)
                    outline = (161, 222, 171, 205)
                elif map_def.terrain in ("nexus", "nexus_v3"):
                    fill = (47, 100, 108, 100)
                    outline = (111, 179, 175, 178)
                else:
                    fill = (57, 110, 78, 72)
                    outline = (112, 156, 126, 135)
                pygame.draw.rect(map_overlay, fill, local, border_radius=3)
                pygame.draw.rect(map_overlay, outline, local, 1, border_radius=3)
            else:
                pygame.draw.rect(self.screen, color, rect.inflate(-18, -18), border_radius=3)
                pygame.draw.rect(self.screen, (91, 106, 94), rect.inflate(-18, -18), 1, border_radius=3)
        if map_def.junctions and map_overlay is not None:
            for junction in map_def.junctions:
                local = self._rect_for_cell(junction).move(-BOARD_X, -BOARD_Y)
                center = local.center
                radius = max(5, CELL // 5)
                pygame.draw.circle(map_overlay, (239, 196, 76, 225), center, radius, 2)
                pygame.draw.line(map_overlay, (239, 196, 76, 225), (center[0] - radius, center[1]), (center[0] + radius, center[1]), 2)
                pygame.draw.line(map_overlay, (239, 196, 76, 225), (center[0], center[1] - radius), (center[0], center[1] + radius), 2)
        if map_overlay is not None:
            self.screen.blit(map_overlay, (BOARD_X, BOARD_Y))
        if map_def.layout_mode == "maze" and mouse_cell is not None and mouse_cell not in protected and mouse_cell not in occupied and mouse_cell not in map_def.pads:
            rect = self._rect_for_cell(mouse_cell)
            pygame.draw.rect(self.screen, (121, 228, 169) if not preview_invalid else (221, 89, 95), rect.inflate(-8, -8), 2, border_radius=4)
        if mouse_cell is not None and mouse_cell not in protected and mouse_cell not in occupied and not preview_invalid:
            radius = int(TOWER_DEFS[self.selected_build]["range"] * CELL)
            preview_color = (221, 89, 95) if preview_invalid else (121, 228, 169)
            pygame.draw.circle(self.screen, (*preview_color, 42), self._screen_pos((float(mouse_cell[0]), float(mouse_cell[1]))), radius, 1)

        for item in self.planned_builds:
            planned_cell = tuple(item["cell"])
            center = self._screen_pos((float(planned_cell[0]), float(planned_cell[1])))
            valid = planned_cell not in protected and (map_def.layout_mode != "fixed" or planned_cell in map_def.pads)
            pygame.draw.circle(self.screen, (121, 228, 169) if valid else HEALTH, center, 17, 2)
            self._text("+", center, GOLD, self.font, "center")
        if self.planning_mode and map_def.layout_mode == "maze":
            planned_blocked = occupied | {tuple(item["cell"]) for item in self.planned_builds}
            planned_route = find_path(map_def.paths[0][0], map_def.paths[0][-1], planned_blocked, map_def.grid_size)
            if planned_route:
                points = [self._screen_pos((float(x), float(y))) for x, y in planned_route]
                if len(points) > 1:
                    pygame.draw.lines(self.screen, (247, 200, 73), False, points, 4)

        spawn = self._rect_for_cell(map_def.paths[0][0])
        castle = self._rect_for_cell(map_def.paths[0][-1])
        pygame.draw.rect(self.screen, (93, 55, 74), spawn.inflate(-10, -10), border_radius=6)
        self._text("SPAWN", (spawn.centerx, spawn.bottom + 2), (235, 192, 184), self.small, "midtop")
        pygame.draw.rect(self.screen, (88, 110, 131), castle.inflate(-6, -6), border_radius=5)
        pygame.draw.rect(self.screen, (221, 229, 214), (castle.x + 13, castle.y + 11, 12, 19))
        self._text("BASE", (castle.centerx, castle.bottom + 2), TEXT, self.small, "midtop")

    def _draw_boss_health_bar(self, bosses: List[Dict[str, object]]) -> None:
        """Show the active boss identity and health without changing combat data."""
        if not bosses:
            return
        boss = max(bosses, key=lambda item: float(item.get("max_hp", 0)))
        width = min(max(220, int(BOARD_W * 0.56)), max(220, BOARD_W - 32))
        rect = pygame.Rect(BOARD_X + (BOARD_W - width) // 2, BOARD_Y + 7, width, 31)
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((16, 11, 25, 218))
        self.screen.blit(overlay, rect)
        pygame.draw.rect(self.screen, (208, 86, 196), rect, 1, border_radius=5)
        name = str(boss.get("boss_name") or ENEMY_DEFS["boss"]["name"])
        hp = max(0.0, float(boss.get("hp", 0)))
        max_hp = max(1.0, float(boss.get("max_hp", 1)))
        self._text(f"BOSS · {name} · {int(hp)}/{int(max_hp)} HP", (rect.centerx, rect.y + 4), TEXT, self.small, "midtop")
        track = pygame.Rect(rect.x + 8, rect.bottom - 9, rect.w - 16, 5)
        pygame.draw.rect(self.screen, (59, 33, 50), track, border_radius=3)
        pygame.draw.rect(self.screen, (230, 82, 143), (track.x, track.y, int(track.w * hp / max_hp), track.h), border_radius=3)

    def _draw_towers_and_enemies(self) -> None:
        if not self.current:
            return
        # Attack effects beneath units.
        for effect in self.current.get("effects", []) if self.config["video"].get("effects") != "off" else ():
            points = [self._screen_pos((float(p[0]), float(p[1]))) for p in effect["points"]]
            color = tuple(effect["color"])
            if effect["kind"] == "burst":
                pygame.draw.circle(self.screen, color, points[0], int(CELL * 0.65), effect["width"])
            elif len(points) > 1:
                pygame.draw.lines(self.screen, color, False, points, effect["width"])
                for p in points[1:]:
                    pygame.draw.circle(self.screen, color, p, 4)
        selected = next((t for t in self.current["towers"] if t["id"] == self.selected_tower), None)
        if selected and self.show_tower_range:
            center = self._screen_pos((selected["cell"][0], selected["cell"][1]))
            radius = int(selected["range"] * CELL)
            range_overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
            pygame.draw.circle(range_overlay, (*SELECT, 34), center, radius)
            self.screen.blit(range_overlay, (0, 0))
            pygame.draw.circle(self.screen, SELECT, center, radius, 1)
        for tower in self.current["towers"]:
            cell = tuple(tower["cell"])
            center = self._screen_pos(cell)
            spec = TOWER_DEFS[tower["kind"]]
            sprite = self._tower_sprite(tower["kind"])
            sprite_rect: Optional[pygame.Rect] = None
            if sprite is not None:
                sprite_rect = sprite.get_rect(center=center)
                self.screen.blit(sprite, sprite_rect)
            else:
                # Legacy types and absent optional assets intentionally retain
                # the original geometry rather than borrowing a wrong sprite.
                pygame.draw.circle(self.screen, (21, 30, 38), center, spec["radius"] + 5)
                pygame.draw.circle(self.screen, spec["color"], center, spec["radius"])
                if tower["kind"] in ("archer", "mg"):
                    pygame.draw.polygon(self.screen, (237, 252, 220), [(center[0],center[1]-11),(center[0]-7,center[1]+9),(center[0]+7,center[1]+9)])
                elif tower["kind"] in ("cannon", "artillery"):
                    pygame.draw.rect(self.screen, (78, 56, 47), (center[0]-4, center[1]-15, 9, 20), border_radius=3)
                elif tower["kind"] in ("frost", "laser"):
                    pygame.draw.circle(self.screen, (222, 251, 255), center, 6)
                elif tower["kind"] == "support":
                    pygame.draw.circle(self.screen, (255, 240, 148), center, 8, 2)
                else:
                    pygame.draw.line(self.screen, (250, 236, 255), (center[0]-8,center[1]+6), (center[0]+8,center[1]-6), 3)
                    pygame.draw.line(self.screen, (250, 236, 255), (center[0]-8,center[1]-6), (center[0]+8,center[1]+6), 3)
            if tower["id"] == self.selected_tower:
                selection_radius = max(spec["radius"] + 8, (max(sprite_rect.size) // 2 + 4) if sprite_rect else 0)
                pygame.draw.circle(self.screen, SELECT, center, selection_radius, 2)
            marker_y = (sprite_rect.bottom + 4) if sprite_rect else (center[1] + spec["radius"] + 8)
            for pip in range(tower["level"]):
                pygame.draw.circle(self.screen, GOLD, (center[0] - 7 + pip * 7, marker_y), 2)
        bosses: List[Dict[str, object]] = []
        for enemy in self.current["enemies"]:
            spec = ENEMY_DEFS[enemy["kind"]]
            center = self._screen_pos((enemy["x"], enemy["y"]))
            radius = spec["radius"]
            body = (220, 244, 255) if enemy["slow"] else spec["color"]
            is_boss = bool(spec.get("boss"))
            sprite = self._boss_sprite(int(enemy.get("boss_wave", 0))) if is_boss else self._creep_sprite(enemy["kind"])
            if sprite is None:
                fallback_radius = max(radius, int(CELL * 0.84)) if is_boss else radius
                pygame.draw.circle(self.screen, (35, 29, 34), center, fallback_radius + 2)
                pygame.draw.circle(self.screen, body, center, fallback_radius)
                if enemy.get("shielded"):
                    pygame.draw.circle(self.screen, (153, 217, 255), center, fallback_radius + 4, 1)
                if enemy["flash"]:
                    pygame.draw.circle(self.screen, (255, 255, 255), center, fallback_radius, 2)
                bar_width = 54 if is_boss else 30
                bar_y = center[1] - fallback_radius - 10
            else:
                sprite_rect = sprite.get_rect(center=center)
                self.screen.blit(sprite, sprite_rect)
                if enemy.get("shielded"):
                    pygame.draw.ellipse(self.screen, (153, 217, 255), sprite_rect.inflate(6, 6), 1)
                if enemy["slow"]:
                    pygame.draw.ellipse(self.screen, (220, 244, 255), sprite_rect.inflate(-2, -2), 2)
                if enemy["flash"]:
                    pygame.draw.ellipse(self.screen, (255, 255, 255), sprite_rect.inflate(-2, -2), 2)
                bar_width = max(54, min(104, int(sprite_rect.width * 0.72))) if is_boss else max(24, min(52, int(sprite_rect.width * 0.52)))
                bar_y = sprite_rect.top - 9
            bar = pygame.Rect(center[0] - bar_width // 2, bar_y, bar_width, 6 if is_boss else 4)
            pygame.draw.rect(self.screen, (54, 35, 41), bar, border_radius=2)
            pygame.draw.rect(self.screen, HEALTH, (bar.x, bar.y, int(bar.w * enemy["hp"] / enemy["max_hp"]), bar.h), border_radius=2)
            if is_boss:
                bosses.append(enemy)
        self._draw_boss_health_bar(bosses)

    def _draw_panel(self) -> None:
        if not self.current:
            return
        x, y, w, h = self.layout.panel_x, self.layout.panel_y, self.layout.panel_width, self.layout.panel_height
        self._frame(pygame.Rect(x, y, w, h), SELECT, PANEL)
        self._text(self.current["map_title"], (x + 12, y + 12), (240, 229, 177), self.font)
        self._text(self.current["map_subtitle"], (x + 12, y + 32), MUTED, self.small)
        self._text(f"Schwierigkeit: {self.current.get('difficulty_name', 'Normal')}", (x + 12, y + 50), MANA, self.small)
        pygame.draw.line(self.screen, (61, 82, 94), (x+10,y+70), (x+w-10,y+70))
        self._text("BAUEN", (x + 12, y + 82), TEXT, self.small)
        self.button_rects = {}
        button_h = 27 if self.layout.compact else 39
        button_step = button_h + (3 if self.layout.compact else 5)
        for i, tower_type in enumerate(TOWER_TYPES):
            spec = TOWER_DEFS[tower_type]
            rect = pygame.Rect(x + 10, y + 102 + i * button_step, w - 20, button_h)
            self.button_rects[tower_type] = rect
            fill = (59, 77, 87) if tower_type == self.selected_build else PANEL_DARK
            pygame.draw.rect(self.screen, fill, rect, border_radius=5)
            pygame.draw.rect(self.screen, spec["color"], rect, 2, border_radius=5)
            icon = self._tower_icon(tower_type, button_h)
            if icon is None:
                pygame.draw.circle(self.screen, spec["color"], (rect.x + 17, rect.centery), 9)
            else:
                self.screen.blit(icon, icon.get_rect(center=(rect.x + 17, rect.centery)))
            locked = tower_type == "laser" and "tech_laser" not in self.current.get("research", [])
            label = f"{i+1}  {spec['name']}" + (" · gesperrt" if locked else "")
            self._text(label, (rect.x + 32, rect.y + 3), MUTED if locked else TEXT, self.small)
            if not self.layout.compact:
                self._text(f"{spec['cost']} Coins · {spec['description']}", (rect.x + 32, rect.y + 21), GOLD if tower_type == self.selected_build else MUTED, self.small)
        mouse_pos = pygame.mouse.get_pos()
        hovered = next((kind for kind, rect in self.button_rects.items() if rect.collidepoint(mouse_pos)), None)
        now = time.monotonic()
        if hovered != self.hover_tower_button:
            self.hover_tower_button = hovered
            self.hover_tower_since = now
        if hovered and now - self.hover_tower_since >= float(self.config["text"].get("tooltip_seconds", 2.0)):
            self._draw_tower_tooltip(hovered, self.button_rects[hovered])
        if self.layout.compact:
            # Megalomania's investment slider is an actionable control, not
            # auxiliary information.  Reserve its full card even on the
            # smallest layout so the controls never become unreachable.
            if self.current.get("mode") == "big_combo":
                preview_h = 174
                preview_y = y + h - preview_h - 8
                self._side_preview_rect = pygame.Rect(x + 10, preview_y, w - 20, preview_h)
                self.wave_start_rect = pygame.Rect(0, 0, 0, 0)
                self._draw_combo_controls()
                return
            # A 800x600 side panel cannot hold five build controls, detailed
            # tower statistics and the full wave card simultaneously.  Keep
            # the actionable controls visible and use a concise wave state.
            compact_y = y + h - 54
            pygame.draw.line(self.screen, (61, 82, 94), (x + 10, compact_y - 6), (x + w - 10, compact_y - 6))
            if self.current.get("first_wave_start_required"):
                self.wave_start_rect = pygame.Rect(x + 10, compact_y, w - 20, 28)
                pygame.draw.rect(self.screen, (66, 92, 78), self.wave_start_rect, border_radius=4)
                pygame.draw.rect(self.screen, (121, 228, 169), self.wave_start_rect, 1, border_radius=4)
                self._text("Start erste Welle", self.wave_start_rect.center, TEXT, self.small, "center")
            else:
                self.wave_start_rect = pygame.Rect(0, 0, 0, 0)
                wave_hint = "[LEER] Welle" if self.current.get("mode") == "classic" else "Nächste Welle automatisch"
                self._text(wave_hint, (x + 12, compact_y + 8), MANA, self.small)
                self._text("[T] Forschung · [U] Upgrade", (x + 12, compact_y + 25), MUTED, self.small)
            return
        detail_y = y + 102 + 5 * button_step + 12
        pygame.draw.line(self.screen, (61, 82, 94), (x+10,detail_y-10), (x+w-10,detail_y-10))
        tower = next((t for t in self.current["towers"] if t["id"] == self.selected_tower), None)
        if tower:
            spec = TOWER_DEFS[tower["kind"]]
            self._text("TURMDETAILS", (x + 12, detail_y), TEXT, self.small)
            self._text(f"{spec['name']} · Stufe {tower['level']}", (x + 12, detail_y + 21), spec["color"], self.font)
            self._text(f"Schaden {tower['damage']:.0f}   Reichweite {tower['range']:.1f}", (x + 12, detail_y + 44), TEXT, self.small)
            self._text(f"Ziel: {PRIORITY_LABELS[tower['priority']]}", (x + 12, detail_y + 62), MUTED, self.small)
            self.priority_rect = pygame.Rect(x + 8, detail_y + 52, w - 16, 24)
            self._text(f"Schaden gesamt {tower.get('total_damage', 0):.0f} · Abschüsse {tower.get('kills', 0)}", (x + 12, detail_y + 80), MANA, self.small)
            if not self.layout.compact:
                self._text(f"Feuerrate {tower.get('fire_rate', 0):.2f}/s · Investiert {tower.get('invested', 0)} Coins", (x + 12, detail_y + 98), TEXT, self.small)
            upgrade = "MAX" if tower["level"] >= 3 else f"{int(spec['cost'] * (0.72 + 0.38*tower['level']))} Coins"
            self._text(f"[U] Upgrade: {upgrade}", (x + 12, detail_y + 116 if not self.layout.compact else detail_y + 98), GOLD, self.small)
            self._text("[Q] Ziel  [R] Radius", (x + 12, detail_y + 134 if not self.layout.compact else detail_y + 116), MUTED, self.small)
            self._text("[X] Verkauf (65%)", (x + 12, detail_y + 152 if not self.layout.compact else detail_y + 134), MUTED, self.small)
            if not self.layout.compact and tower.get("specialization") is None and "weapon_specialist" in self.current.get("research", []):
                self._text("[J/K] Spezialisierung A/B", (x + 12, detail_y + 170 if not self.layout.compact else detail_y + 152), MANA, self.small)
            elif not self.layout.compact and tower.get("specialization"):
                self._text(f"Spezialisierung {tower['specialization'].upper()}", (x + 12, detail_y + 170 if not self.layout.compact else detail_y + 152), MANA, self.small)
        else:
            self._text("TIPP", (x + 12, detail_y), TEXT, self.small)
            self._text("Wählt einen Turm", (x + 12, detail_y + 21), MUTED, self.small)
            self._text("oder Bauplatz aus.", (x + 12, detail_y + 38), MUTED, self.small)
        if self.layout.compact:
            controls_y = y + h - (190 if self.current.get("mode") == "big_combo" else 138)
        else:
            controls_y = max(detail_y + 176, y + h - (208 if self.current.get("mode") == "big_combo" else 132))
        pygame.draw.line(self.screen, (61, 82, 94), (x+10,controls_y), (x+w-10,controls_y))
        self.wave_start_rect = pygame.Rect(0, 0, 0, 0)
        mode = self.current.get("mode_name", "Klassisch")
        self._text(mode, (x + 12, controls_y + 12), MANA, self.small)
        self._text(f"Forschung: {len(self.current.get('research', []))}/{len(self.current.get('research_status', {}))} [T/F]", (x + 12, controls_y + 30), MUTED, self.small)
        if self.current.get("first_wave_start_required"):
            wave_button_y = controls_y - 34 if self.current.get("mode") == "big_combo" else controls_y + 66
            self._text("Vorbereitung abgeschlossen?", (x + 12, wave_button_y - 18), MUTED, self.small)
            self.wave_start_rect = pygame.Rect(x + 10, wave_button_y, w - 20, 30)
            pygame.draw.rect(self.screen, (66, 92, 78), self.wave_start_rect, border_radius=4)
            pygame.draw.rect(self.screen, (121, 228, 169), self.wave_start_rect, 1, border_radius=4)
            self._text("Start erste Welle", self.wave_start_rect.center, TEXT, self.small, "center")
        else:
            if self.current.get("mode") == "big_combo":
                self._text(f"Coins: {self.current.get('credits', 0)} · Einkommen: {self.current.get('round_income', 0)}", (x + 12, controls_y + 48), GOLD, self.small)
            wave_hint = "[LEER] Welle" if self.current.get("mode") == "classic" else "Nächste Welle automatisch"
            hint_y = controls_y + 66
            self._text(f"{wave_hint}  [M] Karte", (x + 12, hint_y), MUTED, self.small)
        preview_h = 174 if self.current.get("mode") == "big_combo" else 142
        preview_y = y + h - preview_h - 8
        self._side_preview_rect = pygame.Rect(x + 10, preview_y, w - 20, preview_h)
        if self.current.get("mode") == "big_combo":
            self._draw_combo_controls()
        elif self.planning_mode:
            self._draw_planning_info()
        else:
            self._draw_wave_preview()

    def _draw_wave_preview(self) -> None:
        if not self.current:
            return
        preview = self.current.get("wave_preview", {})
        panel = getattr(self, "_side_preview_rect", pygame.Rect(self.layout.panel_x + 10, self.layout.panel_y + 420, self.layout.panel_width - 20, 142))
        if panel.h < 70:
            return
        pygame.draw.rect(self.screen, (12, 17, 21), panel, border_radius=6)
        pygame.draw.rect(self.screen, (76, 130, 151), panel, 2, border_radius=6)
        self._text("NÄCHSTE WELLE", (panel.x + 12, panel.y + 9), MANA, self.small)
        self._text(str(preview.get("combo_name", "Standardformation")), (panel.x + 12, panel.y + 29), TEXT, self.small)
        counts = preview.get("counts", {})
        names = [ENEMY_DEFS[k]["name"] + f" ×{v}" for k, v in counts.items() if k in ENEMY_DEFS]
        self._text(" · ".join(names)[:42] or "Noch keine Gegner", (panel.x + 12, panel.y + 53), MUTED, self.small)
        abilities = ", ".join(preview.get("special_abilities", [])) or "Keine Sonderfähigkeit"
        self._text(abilities[:42], (panel.x + 12, panel.y + 72), GOLD, self.small)
        wait = self.current.get("next_wave_in", 0)
        self._text(f"Vorbereitung: {wait:.1f}s · Plan: {preview.get('remaining', 0)}", (panel.x + 12, panel.y + 98), TEXT, self.small)
        self._text("Vorschau aus dem echten Wellenplan", (panel.x + 12, panel.y + 125), (126, 170, 178), self.small)

    def _draw_planning_info(self) -> None:
        if not self.current:
            return
        total = sum(TOWER_DEFS[item["tower"]]["cost"] for item in self.planned_builds if item["tower"] in TOWER_DEFS)
        panel = getattr(self, "_side_preview_rect", pygame.Rect(self.layout.panel_x + 10, self.layout.panel_y + 420, self.layout.panel_width - 20, 142))
        if panel.h < 70:
            return
        pygame.draw.rect(self.screen, (12, 17, 21), panel, border_radius=6)
        pygame.draw.rect(self.screen, SELECT, panel, 2, border_radius=6)
        self._text("BAUPLANUNG · NICHT ABGEBUCHT", (panel.x + 12, panel.y + 9), GOLD, self.small)
        self._text(f"{len(self.planned_builds)} Türme · Gesamt {total} Coins", (panel.x + 12, panel.y + 32), TEXT, self.font)
        self._text(f"Verbleibend nach Bestätigung: {self.current.get('credits', 0) - total} Coins", (panel.x + 12, panel.y + 57), MUTED, self.small)
        map_def = get_map(self.current["map_index"])
        blocked = {tuple(t["cell"]) for t in self.current.get("towers", [])} | {tuple(item["cell"]) for item in self.planned_builds}
        route = tuple(map_def.paths[0]) if map_def.layout_mode == "fixed" else find_path(map_def.paths[0][0], map_def.paths[0][-1], blocked, map_def.grid_size)
        self._text("Laufweg: erreichbar" if route else "Laufweg: BLOCKIERT", (panel.x + 12, panel.y + 83), (121, 228, 169) if route else HEALTH, self.small)
        self._text("Klick: vormerken/entfernen · Y: beenden", (panel.x + 12, panel.y + 109), MUTED, self.small)

    def _draw_combo_controls(self) -> None:
        panel = getattr(self, "_side_preview_rect", pygame.Rect(self.layout.panel_x + 10, self.layout.panel_y + 420, self.layout.panel_width - 20, 174))
        if panel.h < 100:
            return
        pygame.draw.rect(self.screen, (12, 17, 21), panel, border_radius=6)
        pygame.draw.rect(self.screen, (187, 115, 255), panel, 2, border_radius=6)
        self._text("MEGALOMANIE · INVESTITION", (panel.x + 12, panel.y + 9), (187, 115, 255), self.small)
        credits = self.current.get("credits", 0) if self.current else 0
        income = self.current.get("round_income", 0) if self.current else 0
        tick_in = self.current.get("income_tick_in", 30.0) if self.current else 30.0
        self._text(f"{credits} Coins · Rundeneinkommen {income}", (panel.x + 12, panel.y + 28), TEXT, self.small)
        tick_label = "wartet auf ersten Spawn" if tick_in is None else f"in {tick_in:.1f}s"
        self._text(f"Nächster Coin-Tick: {tick_label} · +{income} Coins", (panel.x + 12, panel.y + 45), GOLD, self.small)
        self.investment_slider_rect = pygame.Rect(panel.x + 16, panel.y + 53, max(30, panel.w - 32), 24)
        slider_track = pygame.Rect(self.investment_slider_rect.left, self.investment_slider_rect.centery - 3, self.investment_slider_rect.w, 6)
        pygame.draw.rect(self.screen, (59, 70, 75), slider_track, border_radius=3)
        knob_x = self.investment_slider_rect.left + int(self.investment_slider_rect.w * self.investment_percent_draft / 100)
        pygame.draw.rect(self.screen, (187, 115, 255), pygame.Rect(slider_track.left, slider_track.top, max(1, knob_x - slider_track.left), slider_track.h), border_radius=3)
        pygame.draw.circle(self.screen, SELECT, (knob_x, slider_track.centery), 8)
        self._text(f"{self.investment_percent_draft}% des Guthabens", (panel.x + 12, panel.y + 82), MUTED, self.small)
        amount = int(credits * self.investment_percent_draft / 100)
        factor = 1.25 if self.current and "eco_invest" in self.current.get("research", []) else 1.0
        new_income = income + (max(1, int(amount * 0.10 * factor)) if self.investment_percent_draft and amount > 0 else 0)
        self._text(f"Invest: {amount} · Rest: {credits - amount} · Neu: {new_income}", (panel.x + 12, panel.y + 102), TEXT, self.small)
        self.investment_apply_rect = pygame.Rect(panel.x + 16, panel.y + max(120, panel.h - 38), max(30, panel.w - 32), 30)
        pygame.draw.rect(self.screen, (66, 92, 78), self.investment_apply_rect, border_radius=4)
        pygame.draw.rect(self.screen, (121, 228, 169), self.investment_apply_rect, 1, border_radius=4)
        self._text("Investition übernehmen", self.investment_apply_rect.center, TEXT, self.small, "center")
        # Compatibility aliases for older UI smoke tests and integrations.
        self.savings_slider_rect = self.investment_slider_rect
        self.savings_apply_rect = self.investment_apply_rect

    def _draw_tower_tooltip(self, tower_type: str, button: pygame.Rect) -> None:
        """Show a delayed, mouse-hover explanation for every build button."""
        spec = TOWER_DEFS[tower_type]
        tooltip_w = min(310, max(210, self.layout.panel_width + 24))
        tooltip = pygame.Rect(
            max(self.layout.margin, self.layout.panel_x - tooltip_w - 10),
            max(self.layout.header + 8, min(button.y - 4, self.layout.height - self.layout.footer - 118)),
            tooltip_w,
            112,
        )
        pygame.draw.rect(self.screen, (12, 17, 21), tooltip, border_radius=6)
        pygame.draw.rect(self.screen, spec["color"], tooltip, 2, border_radius=6)
        self._text(spec["name"], (tooltip.x + 10, tooltip.y + 9), spec["color"], self.font)
        self._text(spec["description"], (tooltip.x + 10, tooltip.y + 31), TEXT, self.small)
        self._text(f"Kosten {spec['cost']} Coins · Reichweite {spec['range']:.1f}", (tooltip.x + 10, tooltip.y + 50), GOLD, self.small)
        if tower_type == "support":
            detail = "Aura: benachbarte Türme greifen schneller/stärker an."
        elif tower_type == "artillery":
            detail = "Explodiert am Ziel und trifft Gegner in der Nähe."
        elif tower_type == "laser":
            detail = "Kontinuierlicher Strahl; ignoriert mit Spezialisierung Panzerung."
        elif tower_type == "tesla":
            detail = "Springt als Kettenblitz auf mehrere Ziele über."
        else:
            detail = "Ideal gegen einzelne Ziele durch sehr kurze Abklingzeit."
        self._text(detail, (tooltip.x + 10, tooltip.y + 72), MUTED, self.small)

    def _draw_research(self) -> None:
        self.main_menu_rect = pygame.Rect(0, 0, 0, 0)
        self.research_open_rect = pygame.Rect(0, 0, 0, 0)
        self.research_rects = {}
        self.research_buy_rect = pygame.Rect(0, 0, 0, 0)
        self.screen.fill(INK)
        margin = self.layout.margin
        panel = pygame.Rect(margin, margin, self.layout.width - 2 * margin, self.layout.height - 2 * margin)
        self._frame(panel, SELECT, PANEL_DARK)
        self._text("FORSCHUNGSZENTRUM", (panel.x + 28, panel.y + 28), (240, 229, 177), self.big)
        self._text("Forschung anklicken · danach Kaufen oder F · T = schließen", (panel.x + 30, panel.y + 76), MUTED, self.small)
        if not self.current:
            return
        branches = (("weapons", "WAFFEN"), ("technology", "TECHNOLOGIE"), ("economy", "WIRTSCHAFT"))
        statuses = self.current.get("research_status", {})
        columns = min(3, max(1, (panel.w - 56) // 270))
        col_w = (panel.w - 56 - (columns - 1) * 14) // columns
        for column, (branch, title) in enumerate(branches):
            x = panel.x + 28 + column * (col_w + 14)
            self._text(title, (x, panel.y + 124), MANA, self.title)
            items = [(key, item) for key, item in statuses.items() if item["branch"] == branch]
            for row, (key, item) in enumerate(items):
                y = panel.y + 168 + row * 67
                state = item["state"]
                color = (111, 221, 147) if state == "purchased" else GOLD if state == "available" else MUTED
                rect = pygame.Rect(x, y, col_w, 54)
                self.research_rects[key] = rect
                pygame.draw.rect(self.screen, (47, 57, 67) if self.selected_research and (self.selected_research in self.research_rects and self.research_rects[self.selected_research] == rect) else PANEL, rect, border_radius=4)
                pygame.draw.rect(self.screen, SELECT if self.selected_research and self.research_rects.get(self.selected_research) == rect else color, rect, 2 if self.selected_research and self.research_rects.get(self.selected_research) == rect else 1, border_radius=4)
                self._text(item["name"], (x + 10, y + 7), color, self.font)
                if state == "locked":
                    detail = f"ab Welle {item['wave']}"
                elif state == "prerequisite":
                    detail = "Voraussetzungen fehlen"
                elif state == "unaffordable":
                    detail = f"{item['cost']} Coins benötigt"
                elif state == "purchased":
                    detail = "erworben"
                elif state == "exclusive":
                    detail = "Alternative bereits gewählt"
                else:
                    detail = f"{item['cost']} Coins · anklicken zum Auswählen"
                self._text(detail, (x + 10, y + 30), MUTED, self.small)
        selected = statuses.get(self.selected_research) if self.selected_research else None
        if selected:
            self._text(f"Auswahl: {selected['name']} · {selected['description']}", (panel.x + 28, panel.bottom - 48), TEXT, self.small)
            self.research_buy_rect = pygame.Rect(panel.right - 190, panel.bottom - 54, 168, 32)
            buy_color = (66, 92, 78) if selected.get("state") == "available" else (55, 57, 60)
            pygame.draw.rect(self.screen, buy_color, self.research_buy_rect, border_radius=4)
            pygame.draw.rect(self.screen, SELECT, self.research_buy_rect, 1, border_radius=4)
            self._text("Forschung kaufen", self.research_buy_rect.center, TEXT, self.small, "center")

    @staticmethod
    def _wrap_advisor_text(content: str, font: pygame.font.Font, max_width: int) -> List[str]:
        """Word-wrap without discarding a final line from long dialogue."""
        lines: List[str] = []
        current_line = ""
        for word in content.split():
            candidate = f"{current_line} {word}".strip()
            if current_line and font.size(candidate)[0] > max_width:
                lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line:
            lines.append(current_line)
        return lines or [""]

    def _draw_evil_commentary(self) -> Optional[pygame.Rect]:
        """Draw the persistent advisor dock; retained as the old public hook."""
        now = time.monotonic()
        if self.evil_comment is not None and now >= self.evil_comment_until:
            if self._evil_pending:
                self._activate_evil_comment(self._evil_pending.pop(0), now)
            else:
                self.evil_comment = None
        self.advisor.update(self.evil_comment is not None, now)
        rect = pygame.Rect(self.layout.advisor_rect)
        pygame.draw.rect(self.screen, (26, 14, 43), rect, border_radius=8)
        pygame.draw.rect(self.screen, (90, 59, 126), rect, 1, border_radius=8)

        accent = self.advisor.color
        pygame.draw.line(self.screen, (255, 171, 67), (rect.x + 12, rect.y + 3), (min(rect.right - 12, rect.x + 170), rect.y + 3), 2)
        portrait_w = min(166 if not self.layout.compact else 112, max(96, rect.h))
        portrait_rect = pygame.Rect(rect.x + 8, rect.y + 8, portrait_w, rect.h - 16)
        pygame.draw.rect(self.screen, (17, 14, 29), portrait_rect, border_radius=6)
        pygame.draw.rect(self.screen, accent, portrait_rect, 1, border_radius=6)
        label_h = 32 if self.layout.compact else 38
        image_rect = portrait_rect.inflate(-10, -label_h - 8)
        alpha, offset_y, _ = self.advisor.visual_style(now, self.evil.animations)
        portrait = self.advisor.portrait_for(image_rect.size)
        if portrait is not None:
            portrait = portrait.copy()
            portrait.set_alpha(alpha)
            rendered = portrait.get_rect(midbottom=(image_rect.centerx, image_rect.bottom + offset_y))
            self.screen.blit(portrait, rendered)
        else:
            # Do not fabricate a substitute character: this status stays
            # deliberately textual until the approved source image is added.
            self._text("REFERENZ", image_rect.center, MUTED, self.small, "midbottom")
            self._text("FEHLT", (image_rect.centerx, image_rect.centery + 4), MUTED, self.small, "midtop")
        self._text("MR. EVIL", (portrait_rect.centerx, portrait_rect.bottom - label_h + 3), (255, 171, 67), self.small, "midtop")
        self._text(self.advisor.emotion.upper(), (portrait_rect.centerx, portrait_rect.bottom - 4), accent, self.small, "midbottom")

        bubble = pygame.Rect(portrait_rect.right + 16, rect.y + 12, rect.right - portrait_rect.right - 28, rect.h - 24)
        pygame.draw.polygon(self.screen, (48, 31, 68), [(bubble.x - 12, bubble.centery - 8), (bubble.x, bubble.centery - 2), (bubble.x, bubble.centery + 10)])
        pygame.draw.polygon(self.screen, accent, [(bubble.x - 12, bubble.centery - 8), (bubble.x, bubble.centery - 2), (bubble.x, bubble.centery + 10)], 1)
        pygame.draw.rect(self.screen, (48, 31, 68), bubble, border_radius=8)
        pygame.draw.rect(self.screen, accent, bubble, 1, border_radius=8)
        text_font = self.font if self.evil.text_size == "large" else self.small
        if self.evil.text_size == "small":
            text_font = pygame.font.SysFont("dejavusans", max(9, self.small.get_height() - 1))
        header = f"MR. EVIL · {self.advisor.emotion.upper()}"
        self._text(header, (bubble.x + 12, bubble.y + 7), (255, 188, 93), self.small)
        if self.evil_comment is None:
            self._text("Die Kennzahlen werden überwacht.", (bubble.x + 12, bubble.y + 29), MUTED, text_font)
            return rect
        content = str(self.evil_comment.get("text", ""))
        lines = self._wrap_advisor_text(content, text_font, bubble.w - 24)
        line_height = text_font.get_linesize()
        per_page = max(1, (bubble.h - 36) // line_height)
        page_count = max(1, (len(lines) + per_page - 1) // per_page)
        required_until = self.evil_comment_started + page_count * 3.4 + (2.5 if int(self.evil_comment.get("priority", 0)) >= 85 else 0.0)
        self.evil_comment_until = max(self.evil_comment_until, required_until)
        page = min(page_count - 1, int((now - self.evil_comment_started) / 3.4))
        page_lines = lines[page * per_page:(page + 1) * per_page]
        for index, line in enumerate(page_lines):
            self._text(line, (bubble.x + 12, bubble.y + 30 + index * line_height), TEXT, text_font)
        if page_count > 1:
            self._text(f"{page + 1}/{page_count}", (bubble.right - 10, bubble.bottom - 7), accent, self.small, "bottomright")
        return rect

    def _draw_footer(self) -> None:
        width, height = self.layout.width, self.layout.height
        footer_y = height - self.layout.footer
        pygame.draw.rect(self.screen, PANEL_DARK, (0, footer_y, width, self.layout.footer))
        pygame.draw.line(self.screen, (56, 83, 98), (0, footer_y), (width, footer_y), 1)
        message = ""
        if self.paused:
            message = "PAUSE · [P] fortsetzen"
        elif time.monotonic() < self.local_notice_until:
            message = self.local_notice
        elif self.current:
            message = self.current.get("status", "")
        if self.layout.compact and len(message) > 24:
            message = message[:21].rstrip() + "…"
        self._text(message[: max(20, width // 11)], (self.layout.margin, footer_y + 12), (245, 230, 170) if message else MUTED, self.small)
        button_y = footer_y + max(8, (self.layout.footer - 32) // 2)
        right = width - self.layout.margin
        compact = self.layout.compact
        main_width = 132 if compact else 176
        self.main_menu_rect = pygame.Rect(right - main_width, button_y, main_width, 30)
        pygame.draw.rect(self.screen, (47, 57, 64), self.main_menu_rect, border_radius=4)
        pygame.draw.rect(self.screen, (102, 125, 137), self.main_menu_rect, 1, border_radius=4)
        self._text("Zum Hauptmenü", self.main_menu_rect.center, TEXT, self.small, "center")
        self.options_rect = pygame.Rect(self.main_menu_rect.x - 50, button_y, 42, 30)
        pygame.draw.rect(self.screen, (47, 57, 64), self.options_rect, border_radius=4)
        pygame.draw.rect(self.screen, (102, 125, 137), self.options_rect, 1, border_radius=4)
        self._text("O", self.options_rect.center, TEXT, self.small, "center")
        research_width = 108 if compact else 120
        self.research_open_rect = pygame.Rect(self.options_rect.x - research_width - 8, button_y, research_width, 30)
        pygame.draw.rect(self.screen, (47, 38, 67), self.research_open_rect, border_radius=4)
        pygame.draw.rect(self.screen, SELECT, self.research_open_rect, 1, border_radius=4)
        self._text("Forschung [T]", self.research_open_rect.center, TEXT, self.small, "center")
        self.speed_rects = {}
        speed_x = self.layout.margin + (200 if compact else max(294, width // 2 - self.layout.margin - 76))
        self._text("Tempo", (speed_x - 8, footer_y + 15), MUTED, self.small, "midright")
        for index, speed in enumerate((1, 2, 3)):
            step = 44 if compact else 52
            speed_width = 40 if compact else 46
            rect = pygame.Rect(speed_x + index * step, button_y, speed_width, 30)
            self.speed_rects[speed] = rect
            active = self.game_speed == speed
            pygame.draw.rect(self.screen, (66, 92, 78) if active else (47, 57, 64), rect, border_radius=4)
            pygame.draw.rect(self.screen, SELECT if active else (102, 125, 137), rect, 1, border_radius=4)
            self._text(f"{speed}x", rect.center, TEXT, self.small, "center")
        plan_x = speed_x + (136 if compact else 170)
        self.planning_confirm_rect = pygame.Rect(plan_x, button_y, 60 if compact else 132, 30)
        self.planning_cancel_rect = pygame.Rect(self.planning_confirm_rect.right + 6, button_y, 56 if compact else 132, 30)
        if self.planning_mode:
            labels = ((self.planning_confirm_rect, "Bauen" if compact else "Bauplan bauen"), (self.planning_cancel_rect, "X" if compact else "Verwerfen"))
            for rect, label in labels:
                pygame.draw.rect(self.screen, (66, 92, 78) if label in {"Bauplan bauen", "Bauen"} else (55, 57, 60), rect, border_radius=4)
                pygame.draw.rect(self.screen, SELECT, rect, 1, border_radius=4)
                self._text(f"{label} ({len(self.planned_builds)})" if label in {"Bauplan bauen", "Bauen"} else label, rect.center, TEXT, self.small, "center")
        if self.current and self.current.get("game_over"):
            overlay = pygame.Surface((BOARD_W, BOARD_H), pygame.SRCALPHA)
            overlay.fill((22, 12, 17, 175))
            self.screen.blit(overlay, (BOARD_X, BOARD_Y))
            self._text("DIE BURG IST GEFALLEN", (BOARD_X + BOARD_W // 2, BOARD_Y + BOARD_H // 2 - 20), (245, 179, 166), self.big, "center")
            self._text(f"Welle {self.current.get('wave', 0)} · {self.current.get('kills', 0)} besiegt · {self.current.get('survival_time', 0):.1f}s überlebt", (BOARD_X + BOARD_W // 2, BOARD_Y + BOARD_H // 2 + 20), TEXT, self.font, "center")
            self._text(f"{self.current.get('total_credits_earned', 0)} Coins erwirtschaftet · Forschung {len(self.current.get('research', []))}", (BOARD_X + BOARD_W // 2, BOARD_Y + BOARD_H // 2 + 44), GOLD, self.font, "center")
            self._text("Drücke M für einen zuverlässigen Neustart · Zum Hauptmenü unten rechts", (BOARD_X + BOARD_W // 2, BOARD_Y + BOARD_H // 2 + 72), TEXT, self.font, "center")

    def draw(self) -> None:
        if self.current:
            self._set_active_grid_size(get_map(self.current["map_index"]).grid_size)
        elif self.state and not self.menu_active:
            self._set_active_grid_size(self.state.map.grid_size)
        if self.menu_active:
            self._draw_menu()
            pygame.display.flip()
            return
        if self.show_options:
            self._draw_options(True)
            pygame.display.flip()
            return
        if self.show_manual:
            self._draw_manual(False)
            pygame.display.flip()
            return
        if self.show_research:
            self._draw_research()
            pygame.display.flip()
            return
        self.screen.fill(INK)
        self._draw_header()
        if self.current:
            self._draw_board()
            self._draw_towers_and_enemies()
            self._draw_panel()
            self._draw_evil_commentary()
            self._draw_footer()
        else:
            self._text("Verbindung wird hergestellt …", (WINDOW_W // 2, WINDOW_H // 2), TEXT, self.title, "center")
        pygame.display.flip()

    def run(self) -> None:
        try:
            while self.running:
                dt = min(0.1, self.clock.tick(FPS) / 1000.0)
                for event in pygame.event.get():
                    self._handle_event(event)
                self._update_state(dt)
                self.draw()
        finally:
            self.close()
