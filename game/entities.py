from __future__ import annotations
from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Sequence, Tuple

from .constants import ENEMY_DEFS, PRIORITIES, TOWER_DEFS

Grid = Tuple[int, int]

@dataclass
class Enemy:
    eid: int
    kind: str
    route: Sequence[Grid]
    progress: float = 0.0
    hp: float = 1.0
    max_hp: float = 1.0
    slow_factor: float = 1.0
    slow_timer: float = 0.0
    hit_flash: float = 0.0
    shield_timer: float = 0.0
    ability_timer: float = 6.0

    @classmethod
    def create(cls, eid: int, kind: str, route: Sequence[Grid], health_scale: float) -> "Enemy":
        spec = ENEMY_DEFS[kind]
        hp = spec["hp"] * health_scale
        return cls(eid=eid, kind=kind, route=route, hp=hp, max_hp=hp)

    @property
    def spec(self) -> Dict:
        return ENEMY_DEFS[self.kind]

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def reached_castle(self) -> bool:
        return self.progress >= len(self.route) - 1

    def grid_position(self) -> Tuple[float, float]:
        if len(self.route) < 2:
            return (float(self.route[0][0]), float(self.route[0][1]))
        index = min(int(self.progress), len(self.route) - 2)
        fraction = self.progress - int(self.progress)
        a = self.route[index]
        b = self.route[index + 1]
        return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)

    def tick(self, dt: float) -> None:
        if self.slow_timer > 0:
            self.slow_timer = max(0.0, self.slow_timer - dt)
        else:
            self.slow_factor = 1.0
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.progress += self.spec["speed"] * self.slow_factor * dt

    def damage(self, amount: float, slow: Optional[float] = None, ignore_armor: bool = False) -> bool:
        armor = 0.0 if ignore_armor else float(self.spec.get("armor", 0.0))
        shield = float(self.spec.get("shield", 0.0)) if self.spec.get("shield") else 0.0
        self.hp -= amount * (1.0 - armor) * (1.0 - shield)
        self.hit_flash = 0.10
        if slow is not None:
            self.slow_factor = min(self.slow_factor, slow)
            self.slow_timer = max(self.slow_timer, 1.15)
        return self.hp <= 0

    def serialize(self) -> Dict:
        x, y = self.grid_position()
        return {
            "id": self.eid, "kind": self.kind, "x": x, "y": y,
            "hp": round(max(0, self.hp), 1), "max_hp": round(self.max_hp, 1),
            "slow": self.slow_timer > 0, "flash": self.hit_flash > 0,
            "flying": bool(self.spec.get("flying", False)),
            "shielded": bool(self.spec.get("shield", False)),
            "abilities": list(self.spec.get("abilities", ())),
        }


@dataclass
class Tower:
    tid: int
    kind: str
    cell: Grid
    level: int = 1
    cooldown: float = 0.0
    priority: str = "first"
    invested: int = 0
    specialization: Optional[str] = None
    total_damage: float = 0.0
    kills: int = 0

    @classmethod
    def create(cls, tid: int, kind: str, cell: Grid) -> "Tower":
        return cls(tid=tid, kind=kind, cell=cell, invested=TOWER_DEFS[kind]["cost"])

    @property
    def spec(self) -> Dict:
        return TOWER_DEFS[self.kind]

    def stat(self, name: str) -> float:
        if name == "damage":
            value = self.spec[name] * (1 + 0.43 * (self.level - 1))
            if self.specialization == "a" and self.kind in ("laser", "artillery"):
                value *= 1.28
            if self.specialization == "b" and self.kind in ("mg", "support"):
                value *= 1.22
            if self.specialization == "b" and self.kind == "artillery":
                value *= 1.30
            if self.specialization == "b" and self.kind == "tesla":
                value *= 1.35
            return value
        if name == "range":
            value = self.spec[name] + 0.22 * (self.level - 1)
            if self.specialization == "b" and self.kind == "laser":
                value += 0.65
            return value
        if name == "cooldown":
            value = self.spec[name] * (0.92 ** (self.level - 1))
            if self.specialization == "a" and self.kind in ("mg", "support"):
                value *= 0.72
            return value
        if name == "splash":
            value = float(self.spec.get(name, 0.0))
            if self.specialization == "a" and self.kind == "artillery":
                value *= 1.35
            return value
        if name == "chain":
            value = float(self.spec.get(name, 0.0))
            if self.specialization == "a" and self.kind == "tesla":
                value += 1
            if self.specialization == "b" and self.kind == "tesla":
                value = 1
            return value
        if name == "support":
            value = float(self.spec.get(name, 0.0))
            if self.specialization == "b" and self.kind == "support":
                value *= 1.25
            return value
        return float(self.spec.get(name, 0))

    def upgrade_cost(self) -> int:
        return int(self.spec["cost"] * (0.72 + 0.38 * self.level))

    def can_upgrade(self) -> bool:
        return self.level < 3

    def specialize(self, choice: str) -> bool:
        if choice not in ("a", "b") or self.specialization is not None:
            return False
        self.specialization = choice
        return True

    def upgrade(self) -> int:
        cost = self.upgrade_cost()
        self.level += 1
        self.invested += cost
        return cost

    def next_priority(self) -> None:
        index = (PRIORITIES.index(self.priority) + 1) % len(PRIORITIES)
        self.priority = PRIORITIES[index]

    def tick(self, dt: float) -> None:
        self.cooldown = max(0.0, self.cooldown - dt)

    def serialize(self) -> Dict:
        return {
            "id": self.tid, "kind": self.kind, "cell": list(self.cell), "level": self.level,
            "priority": self.priority, "cooldown": self.cooldown,
            "range": round(self.stat("range"), 2), "damage": round(self.stat("damage"), 1),
            "invested": self.invested, "specialization": self.specialization,
            "total_damage": round(self.total_damage, 1), "kills": self.kills,
        }


@dataclass
class Effect:
    kind: str
    points: List[Tuple[float, float]]
    color: Tuple[int, int, int]
    ttl: float
    width: int = 2

    def tick(self, dt: float) -> None:
        self.ttl -= dt

    def serialize(self) -> Dict:
        return {"kind": self.kind, "points": self.points, "color": self.color, "ttl": self.ttl, "width": self.width}


@dataclass
class WavePlan:
    number: int
    queue: List[str] = field(default_factory=list)
    spawn_clock: float = 0.0
    spawn_scale: float = 1.0
    active: bool = False
    combo_name: str = "Standardformation"
    special_abilities: Tuple[str, ...] = ()

    @classmethod
    def build(cls, number: int, count_scale: float = 1.0, spawn_scale: float = 1.0, mode: str = "classic", seed: int = 1337) -> "WavePlan":
        queue: List[str] = []
        scout_count = max(1, round((6 + number * 2) * count_scale))
        queue.extend(["scout"] * scout_count)
        if number >= 2:
            queue.extend(["raider"] * max(1, round((1 + number * 2) * count_scale)))
        if number >= 3:
            queue.extend(["wisp"] * max(1, round((number // 2 + 1) * count_scale)))
        if number >= 3:
            queue.extend(["shield"] * max(1, round(number / 5 * count_scale)))
        if number >= 4:
            queue.extend(["healer"] * max(1, round(number / 6 * count_scale)))
        if number % 4 == 0:
            queue.extend(["brute"] * max(1, round((1 + number // 7) * count_scale)))
        if number >= 5:
            queue.extend(["siege"] * max(1, round(number / 8 * count_scale)))
        if number % 5 == 0:
            queue.extend(["boss"] * (1 if mode == "big_combo" else 0))
            # Special waves are compositions, not only an HP multiplier.
            queue.extend(["shield", "healer", "raider", "siege"])
        combo_name = "Standardformation"
        abilities: Tuple[str, ...] = ()
        if mode == "big_combo":
            if number % 5 == 0:
                combo_name = "Boss-Belagerung"
                abilities = ("Boss-Regeneration", "Schildschirm", "Belagerungsdruck")
            else:
                director = random.Random(seed + number * 7919)
                combo = director.choice(("tank", "swarm", "air", "siege"))
                if combo == "tank":
                    combo_name = "Panzerfront"
                    abilities = ("Rüstung", "Heilerunterstützung", "Schildschutz")
                    queue.extend(["brute", "shield", "healer"])
                elif combo == "swarm":
                    combo_name = "Schwarmangriff"
                    abilities = ("Hohe Anzahl", "Durchbruchdruck")
                    queue.extend(["raider"] * max(3, round((4 + number) * count_scale)))
                elif combo == "air":
                    combo_name = "Luftangriff"
                    abilities = ("Fliegende Flankierer", "Bodenlabyrinthe umgehen")
                    queue.extend(["wisp"] * max(3, round((3 + number // 2) * count_scale)))
                else:
                    combo_name = "Belagerung"
                    abilities = ("Erhöhter Basisschaden", "Widerstandsfähige Einheiten")
                    queue.extend(["siege"] * max(2, round((2 + number // 2) * count_scale)))
        # Interleave enemy archetypes predictably instead of sending clusters.
        order = {"boss": 0, "shield": 1, "healer": 2, "brute": 3, "siege": 4, "raider": 5, "wisp": 6, "scout": 7}
        queue.sort(key=lambda k: order.get(k, 99))
        return cls(number=number, queue=queue, spawn_clock=0.30 * spawn_scale, spawn_scale=spawn_scale, active=True, combo_name=combo_name, special_abilities=abilities)

    def tick(self, dt: float) -> Optional[str]:
        if not self.active or not self.queue:
            return None
        self.spawn_clock -= dt
        if self.spawn_clock <= 0:
            self.spawn_clock += max(0.24, 0.62 - self.number * 0.012) * self.spawn_scale
            return self.queue.pop(0)
        return None

    @property
    def remaining(self) -> int:
        return len(self.queue)

    def preview(self) -> Dict[str, object]:
        counts = {kind: self.queue.count(kind) for kind in sorted(set(self.queue))}
        return {
            "number": self.number,
            "combo_name": self.combo_name,
            "special_abilities": list(self.special_abilities),
            "counts": counts,
            "remaining": self.remaining,
        }
