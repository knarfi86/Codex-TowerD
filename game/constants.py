from __future__ import annotations

WINDOW_W, WINDOW_H = 1280, 760
GRID_COLS, GRID_ROWS = 20, 12
CELL = 52
BOARD_X, BOARD_Y = 24, 82
BOARD_W, BOARD_H = GRID_COLS * CELL, GRID_ROWS * CELL
FPS = 60
TICK_RATE = 30.0
SNAPSHOT_RATE = 20.0

# Palette
INK = (6, 10, 20)
PANEL = (14, 25, 40)
PANEL_DARK = (7, 12, 22)
TEXT = (232, 235, 232)
MUTED = (139, 150, 151)
GOLD = (255, 171, 67)
HEALTH = (226, 89, 87)
MANA = (94, 224, 255)
GRASS = (42, 49, 45)
GRASS_ALT = (46, 54, 50)
PATH = (92, 98, 98)
PATH_EDGE = (32, 36, 38)
WATER = (50, 125, 163)
BUILD_PAD = (57, 68, 61)
BUILD_PAD_HOVER = (89, 112, 82)
SELECT = (187, 115, 255)

TOWER_DEFS = {
    "archer": {
        "name": "Bogenschütze", "cost": 75, "damage": 14, "range": 3.1,
        "cooldown": 0.48, "color": (82, 188, 111), "radius": 16,
        "projectile": (218, 239, 189), "description": "Schnell · Einzelziel",
    },
    "cannon": {
        "name": "Kanone", "cost": 115, "damage": 32, "range": 2.75,
        "cooldown": 1.20, "color": (216, 117, 74), "radius": 18,
        "projectile": (255, 186, 100), "splash": 1.38, "description": "Fläche · solider Schaden",
    },
    "frost": {
        "name": "Frostmagier", "cost": 105, "damage": 10, "range": 3.35,
        "cooldown": 0.62, "color": (80, 184, 226), "radius": 16,
        "projectile": (174, 237, 255), "slow": 0.46, "description": "Verlangsamt Gegner",
    },
    "tesla": {
        "name": "Tesla-Spule", "cost": 145, "damage": 24, "range": 2.9,
        "cooldown": 0.78, "color": (170, 112, 233), "radius": 17,
        "projectile": (237, 213, 255), "chain": 3, "description": "Kettenblitz · 3 Ziele",
    },
    "mg": {
        "name": "MG-Turm", "cost": 70, "damage": 8, "range": 3.4,
        "cooldown": 0.18, "color": (105, 202, 121), "radius": 15,
        "projectile": (218, 239, 189), "description": "Hohe Feuerrate · Einzelziel",
        "specializations": {"a": "Sturmfeuer: höhere Feuerrate", "b": "Präzisionslauf: mehr Schaden"},
    },
    "artillery": {
        "name": "Artillerie", "cost": 125, "damage": 38, "range": 3.1,
        "cooldown": 1.35, "color": (222, 126, 70), "radius": 18,
        "projectile": (255, 186, 100), "splash": 3.45, "description": "Explosion · sehr großer Flächenschaden",
        "specializations": {"a": "Sprengkopf: größere Explosion", "b": "Panzerbrecher: Direktschaden"},
    },
    "laser": {
        "name": "Laser", "cost": 155, "damage": 18, "range": 3.8,
        "cooldown": 0.12, "color": (234, 92, 130), "radius": 16,
        "projectile": (255, 146, 184), "description": "Kontinuierlich · hoher Einzelschaden",
        "specializations": {"a": "Fokussierter Strahl: mehr Schaden", "b": "Prismalinse: mehr Reichweite"},
    },
    "support": {
        "name": "Support", "cost": 110, "damage": 0, "range": 2.2,
        "cooldown": 1.0, "color": (236, 191, 79), "radius": 16,
        "projectile": (255, 232, 150), "support": 0.16, "description": "Aura · benachbarte Türme",
        "specializations": {"a": "Taktiknetz: mehr Feuerrate", "b": "Kampfaura: mehr Schaden für verbundene Türme"},
    },
}

ENEMY_DEFS = {
    "scout": {"name": "Standardgegner", "hp": 48, "speed": 1.20, "reward": 6, "color": (212, 194, 121), "radius": 12, "armor": 0.0},
    "raider": {"name": "Schneller Gegner", "hp": 72, "speed": 1.62, "reward": 8, "color": (190, 88, 81), "radius": 11, "armor": 0.0},
    "brute": {"name": "Gepanzerter Gegner", "hp": 310, "speed": 0.46, "reward": 18, "color": (107, 83, 104), "radius": 18, "armor": 0.32},
    "wisp": {"name": "Fliegender Gegner", "hp": 72, "speed": 1.52, "reward": 11, "color": (115, 218, 230), "radius": 10, "flying": True, "armor": 0.0},
    "healer": {"name": "Heiler", "hp": 120, "speed": 0.72, "reward": 16, "color": (104, 211, 148), "radius": 13, "heal": 7, "armor": 0.05},
    "shield": {"name": "Schildgenerator", "hp": 155, "speed": 0.58, "reward": 20, "color": (89, 166, 231), "radius": 15, "shield": 0.20, "armor": 0.12},
    "siege": {"name": "Belagerungseinheit", "hp": 230, "speed": 0.42, "reward": 22, "color": (220, 137, 74), "radius": 16, "base_damage": 2, "armor": 0.18},
    "boss": {"name": "Boss", "hp": 900, "speed": 0.30, "reward": 100, "color": (202, 74, 177), "radius": 24, "armor": 0.42, "boss": True, "abilities": ("rage", "shield_burst")},
}

ENEMY_ALIASES = {"standard": "scout", "fast": "raider", "armored": "brute", "flying": "wisp"}
TOWER_TYPES = ("mg", "artillery", "laser", "tesla", "support")

PRIORITIES = ("first", "strong", "near", "last")
PRIORITY_LABELS = {"first": "Erste", "strong": "Stärkste", "near": "Nächste", "last": "Letzte"}

DIFFICULTY_DEFS = {
    "easy": {
        "name": "Leicht", "description": "Mehr Credits, robuste Basis",
        "gold": 340, "lives": 25, "health_scale": 0.86, "count_scale": 0.86,
        "spawn_scale": 1.12,
    },
    "normal": {
        "name": "Normal", "description": "Ausgewogenes Standardspiel",
        "gold": 280, "lives": 20, "health_scale": 1.0, "count_scale": 1.0,
        "spawn_scale": 1.0,
    },
    "hard": {
        "name": "Schwer", "description": "Weniger Reserve, dichtere Wellen",
        "gold": 235, "lives": 16, "health_scale": 1.18, "count_scale": 1.18,
        "spawn_scale": 0.88,
    },
}

DIFFICULTY_KEYS = tuple(DIFFICULTY_DEFS)
