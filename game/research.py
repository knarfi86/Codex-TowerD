from __future__ import annotations

from typing import Dict, Tuple


RESEARCH_DEFS: Dict[str, Dict] = {
    "weapon_projectiles": {"branch": "weapons", "name": "Beschleunigte Geschosse", "description": "+20% Feuerrate", "cost": 90, "wave": 2, "requires": (), "effect": "fire_rate"},
    "weapon_damage": {"branch": "weapons", "name": "Verstärkte Sprengköpfe", "description": "+12% Grundschaden", "cost": 130, "wave": 4, "requires": ("weapon_projectiles",), "effect": "damage"},
    "weapon_targeting": {"branch": "weapons", "name": "Präzise Zielerfassung", "description": "+12% Reichweite", "cost": 150, "wave": 6, "requires": ("weapon_damage",), "effect": "range"},
    "weapon_specialist": {"branch": "weapons", "name": "Spezialistenkern", "description": "Alternative Turmspezialisierungen freigeschaltet", "cost": 220, "wave": 8, "requires": ("weapon_targeting",), "effect": "specializations"},
    "weapon_velocity": {"branch": "weapons", "name": "Überschallkern", "description": "Weitere 10% Feuerrate", "cost": 280, "wave": 12, "requires": ("weapon_specialist",), "effect": "fire_rate"},
    "tech_laser": {"branch": "technology", "name": "Laser-Technologie", "description": "Laser-Türme können gebaut werden", "cost": 110, "wave": 3, "requires": (), "effect": "laser"},
    "tech_laser_range": {"branch": "technology", "name": "Prismalinse", "description": "+22% Laser-Reichweite", "cost": 175, "wave": 6, "requires": ("tech_laser",), "conflicts": ("tech_laser_damage",), "effect": "laser_range"},
    "tech_laser_damage": {"branch": "technology", "name": "Fokussierkern", "description": "+25% Laser-Schaden", "cost": 175, "wave": 6, "requires": ("tech_laser",), "conflicts": ("tech_laser_range",), "effect": "laser_damage"},
    "tech_tesla": {"branch": "technology", "name": "Tesla-Technologie", "description": "Tesla-Ketten springen auf ein weiteres Ziel", "cost": 140, "wave": 5, "requires": (), "effect": "tesla"},
    "tech_splash": {"branch": "technology", "name": "Flächenfokus", "description": "+25% Flächenschaden", "cost": 180, "wave": 7, "requires": ("tech_laser",), "effect": "splash"},
    "tech_support": {"branch": "technology", "name": "Verbundnetz", "description": "Support-Auren werden um 35% stärker", "cost": 200, "wave": 9, "requires": ("tech_tesla",), "effect": "support"},
    "tech_effects": {"branch": "technology", "name": "Resonanzfelder", "description": "Spezialeffekte halten länger an", "cost": 260, "wave": 12, "requires": ("tech_splash", "tech_support"), "effect": "effects"},
    "eco_build": {"branch": "economy", "name": "Materialrecycling", "description": "Baukosten um 10% reduziert", "cost": 100, "wave": 2, "requires": (), "effect": "build_cost"},
    "eco_salvage": {"branch": "economy", "name": "Bergungstechnik", "description": "+15% Verkaufserlös", "cost": 120, "wave": 4, "requires": ("eco_build",), "effect": "sell_value"},
    "eco_repairs": {"branch": "economy", "name": "Günstige Reparaturen", "description": "Wellenabschluss heilt ein zusätzliches Leben", "cost": 160, "wave": 6, "requires": ("eco_salvage",), "effect": "repairs"},
    "eco_income": {"branch": "economy", "name": "Handelsrouten", "description": "+2 Credits zum Rundeneinkommen", "cost": 190, "wave": 8, "requires": ("eco_repairs",), "effect": "income"},
    "eco_invest": {"branch": "economy", "name": "Zinsoptimierung", "description": "Big-Combo-Investitionen liefern 25% mehr", "cost": 260, "wave": 11, "requires": ("eco_income",), "effect": "investments"},
}

RESEARCH_BRANCHES: Tuple[Tuple[str, str], ...] = (("weapons", "Waffenforschung"), ("technology", "Technologieforschung"), ("economy", "Wirtschaftsforschung"))


def research_status(purchased: set[str], wave: int, credits: int) -> Dict[str, Dict]:
    result = {}
    for key, spec in RESEARCH_DEFS.items():
        if key in purchased:
            state = "purchased"
        elif wave < spec["wave"]:
            state = "locked"
        elif any(req not in purchased for req in spec["requires"]):
            state = "prerequisite"
        elif any(conflict in purchased for conflict in spec.get("conflicts", ())):
            state = "exclusive"
        elif credits < spec["cost"]:
            state = "unaffordable"
        else:
            state = "available"
        result[key] = {**spec, "state": state}
    return result
