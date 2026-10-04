from __future__ import annotations

from typing import Dict


MODE_INFO: Dict[str, Dict[str, str]] = {
    "classic": {
        "name": "Letzte Bastion",
        "legacy": "Klassische Verteidigung",
        "description": "Halte die Stellung. Die Geschichtsbücher brauchen schließlich auch Verlierer.",
    },
    "big_combo": {
        "name": "Megalomanie",
        "legacy": "The Big Combo",
        "description": "Kapitalismus trifft Creep-Apokalypse.",
    },
    "bounty_hunter": {
        "name": "Akkordarbeit",
        "legacy": "Bounty Hunter",
        "description": "Die Creeps haben keinen Feierabend. Du jetzt auch nicht.",
    },
}

MAP_FAMILY_INFO: Dict[str, Dict[str, str]] = {
    "maze": {"name": "Freies Bauen", "description": "Türme geben den Weg vor."},
    "fixed": {"name": "Vorgegebene Wege", "description": "Die Karte gibt den Weg vor."},
}

DIFFICULTY_FLAVOR = {
    "easy": "Mehr Startkapital und eine robustere Basis.",
    "normal": "Ausgewogene Unternehmensbedingungen.",
    "hard": "Weniger Reserve, dichtere Wellen. Mr. Evil empfiehlt Optimismus.",
}

def mode_info(mode: str) -> Dict[str, str]:
    return MODE_INFO.get(mode, MODE_INFO["classic"])


def mode_name(mode: str) -> str:
    return mode_info(mode)["name"]
