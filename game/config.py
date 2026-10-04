from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "video": {
        "fullscreen": False,
        "resolution": "1280x760",
        "window_size": [1280, 760],
        "ui_scale": 1.0,
        "effects": "normal",
    },
    "audio": {"master": 100, "music": 70, "effects": 80, "evil": 80},
    "text": {"size": "normal", "tooltip_seconds": 2.0, "language": "de", "humor": "normal"},
    "gameplay": {
        "show_range": True,
        "evil_comments": True,
        "evil_frequency": "normal",
        "evil_animations": True,
        "evil_text_size": "normal",
        "speed": 1,
    },
}

RESOLUTION_PRESETS = ("1920x1080", "1600x900", "1366x768", "1280x720", "1280x760", "1024x768")


def config_path() -> Path:
    override = os.environ.get("CREEPGRID_CONFIG")
    return Path(override) if override else Path.home() / ".creepgrid_config.json"


def _merge(default: Dict[str, Any], loaded: Any) -> Dict[str, Any]:
    result = {key: (value.copy() if isinstance(value, dict) else value) for key, value in default.items()}
    if not isinstance(loaded, dict):
        return result
    for key, value in loaded.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key].update({child: value[child] for child in value if child in result[key]})
        elif key in result and not isinstance(result[key], dict) and isinstance(value, type(result[key])):
            result[key] = value
    return result


def _sanitize(config: Dict[str, Any]) -> Dict[str, Any]:
    """Reject malformed persisted UI values before the renderer consumes them."""
    video = config["video"]
    resolution = str(video.get("resolution", DEFAULT_CONFIG["video"]["resolution"]))
    if not re.fullmatch(r"\d{3,5}x\d{3,5}", resolution):
        resolution = DEFAULT_CONFIG["video"]["resolution"]
    video["resolution"] = resolution
    window_size = video.get("window_size")
    if not isinstance(window_size, (list, tuple)) or len(window_size) != 2:
        width, height = (int(part) for part in resolution.split("x", 1))
        video["window_size"] = [width, height]
    else:
        try:
            width, height = int(window_size[0]), int(window_size[1])
            if not (800 <= width <= 7680 and 600 <= height <= 4320):
                raise ValueError
            video["window_size"] = [width, height]
        except (TypeError, ValueError):
            width, height = (int(part) for part in DEFAULT_CONFIG["video"]["resolution"].split("x", 1))
            video["window_size"] = [width, height]
    try:
        video["ui_scale"] = max(0.75, min(1.5, float(video.get("ui_scale", 1.0))))
    except (TypeError, ValueError):
        video["ui_scale"] = 1.0
    if config["text"].get("size") not in {"small", "normal", "large"}:
        config["text"]["size"] = "normal"
    if config["video"].get("effects") not in {"off", "normal", "high"}:
        config["video"]["effects"] = "normal"
    if config["gameplay"].get("evil_frequency") not in {"off", "rare", "normal", "frequent"}:
        config["gameplay"]["evil_frequency"] = "normal"
    if config["gameplay"].get("evil_text_size") not in {"small", "normal", "large"}:
        config["gameplay"]["evil_text_size"] = "normal"
    config["gameplay"]["evil_animations"] = bool(config["gameplay"].get("evil_animations", True))
    # Keep the pre-existing Boolean option compatible with the new frequency control.
    if not config["gameplay"].get("evil_comments", True):
        config["gameplay"]["evil_frequency"] = "off"
    return config


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    target = path or config_path()
    try:
        with target.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError, TypeError):
        return _sanitize(_merge(DEFAULT_CONFIG, {}))
    return _sanitize(_merge(DEFAULT_CONFIG, loaded))


def save_config(config: Dict[str, Any], path: Optional[Path] = None) -> bool:
    target = path or config_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_sanitize(_merge(DEFAULT_CONFIG, config)), ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False
