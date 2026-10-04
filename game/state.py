from __future__ import annotations
import math
import random
from collections import Counter
from typing import Dict, List, Optional, Tuple

from .constants import DIFFICULTY_DEFS, ENEMY_ALIASES, ENEMY_DEFS, PRIORITY_LABELS, TOWER_DEFS, TOWER_TYPES
from .entities import Effect, Enemy, Tower, WavePlan
from .maps import MAPS, MapDefinition, get_map
from .pathfinding import clear_path_cache, find_path, route_for_position
from .research import RESEARCH_DEFS, research_status
from .ui_data import mode_name

Grid = Tuple[int, int]

class GameState:
    """Single source of truth. Only the host mutates an instance of this class."""

    def __init__(self, seed: int = 1337, map_index: int = 0, difficulty: str = "normal", mode: str = "classic") -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self.difficulty_key = self._difficulty_key(difficulty)
        self.max_lives = int(self.difficulty["lives"])
        self.map_index = map_index % len(MAPS)
        self.map: MapDefinition = get_map(self.map_index)
        self.mode = mode if mode in ("classic", "big_combo", "bounty_hunter") else "classic"
        self.player_count = 1
        self.gold = int(self.difficulty["gold"])
        self.lives = self.max_lives
        self.wave = 0
        self.towers: Dict[int, Tower] = {}
        self.enemies: Dict[int, Enemy] = {}
        self.effects: List[Effect] = []
        self.plan: Optional[WavePlan] = None
        self.next_enemy_id = 1
        self.next_tower_id = 1
        self.status = "Bereit: Baut eure Verteidigung und startet die erste Welle."
        self.status_timer = 7.0
        self.game_over = False
        self.total_kills = 0
        self.research: set[str] = set()
        self.investments = 0
        self.round_income = max(1, int(100 / self.player_count))
        self.income_rate = float(self.round_income)
        self.investment_percent = 0
        self.last_investment_amount = 0
        self.last_wave_income = 0
        self.income_clock = 0.0
        self.income_timer_active = False
        self.survival_time = 0.0
        self.total_credits_earned = self.gold
        self.combo_summary: List[str] = []
        self.next_wave_timer = 0.0
        self.auto_wave_delay = 8.0
        self.path_cache: Dict[Tuple[Grid, ...], Tuple[Grid, ...]] = {}

    @staticmethod
    def _difficulty_key(key: str) -> str:
        return key if key in DIFFICULTY_DEFS else "normal"

    @property
    def difficulty(self) -> Dict:
        return DIFFICULTY_DEFS[self.difficulty_key]

    def set_player_count(self, players: int) -> None:
        """Scale the shared economy to the currently connected player count."""
        players = max(1, int(players))
        if players == self.player_count:
            return
        previous = self.player_count
        self.gold = max(0, int(self.gold * previous / players))
        self.round_income = max(1, int(self.round_income * previous / players))
        self.income_rate = float(self.round_income)
        if self.last_wave_income:
            self.last_wave_income = max(0, int(self.last_wave_income * previous / players))
        self.player_count = players
        share = 100.0 / players
        self.set_status(f"Koop-Ressourcen: {share:.0f}% Startguthaben und Einkommen pro Spieler.", 3.0)

    def reset_map(self, index: int, difficulty: Optional[str] = None) -> None:
        if difficulty is not None:
            self.difficulty_key = self._difficulty_key(difficulty)
        self.max_lives = int(self.difficulty["lives"])
        self.map_index = index % len(MAPS)
        self.map = get_map(self.map_index)
        self.gold, self.lives, self.wave = max(1, int(self.difficulty["gold"] / self.player_count)), self.max_lives, 0
        self.mode = self.mode if self.mode in ("classic", "big_combo", "bounty_hunter") else "classic"
        self.towers.clear()
        self.enemies.clear()
        self.effects.clear()
        self.plan = None
        self.next_enemy_id = self.next_tower_id = 1
        self.game_over = False
        self.total_kills = 0
        self.research.clear()
        self.investments = 0
        self.round_income = max(1, int(100 / self.player_count))
        self.income_rate = float(self.round_income)
        self.investment_percent = 0
        self.last_investment_amount = 0
        self.last_wave_income = 0
        self.income_clock = 0.0
        self.income_timer_active = False
        self.survival_time = 0.0
        self.total_credits_earned = self.gold
        self.combo_summary.clear()
        self.next_wave_timer = 0.0
        self.path_cache.clear()
        clear_path_cache()
        self.set_status(f"{self.map.title} · {self.difficulty['name']} gestartet.", 4.0)

    def set_status(self, text: str, timer: float = 2.5) -> None:
        self.status = text
        self.status_timer = timer

    def action(self, data: Dict) -> Tuple[bool, str]:
        """Validate every client request. Returns result for logging / acknowledgement."""
        kind = data.get("type")
        if self.game_over and kind not in ("restart", "select_map", "select_mode", "select_difficulty"):
            return False, "Die Burg ist gefallen. Wähle eine Karte zum Neustart."
        if kind == "build":
            return self._build(data)
        if kind == "build_plan":
            return self._build_plan(data)
        if kind == "upgrade":
            return self._upgrade(data)
        if kind == "sell":
            return self._sell(data)
        if kind == "priority":
            return self._priority(data)
        if kind == "start_wave":
            return self._start_wave()
        if kind == "select_map":
            return self._select_map(data)
        if kind == "restart":
            return self._restart(data)
        if kind == "select_difficulty":
            return self._select_difficulty(data)
        if kind == "select_mode":
            return self._select_mode(data)
        if kind == "research":
            return self._research(data)
        if kind == "invest":
            return self._invest(data)
        if kind in ("withdraw_reserve", "set_savings_percent"):
            return False, "Megalomanie verwendet keine Reserve oder Sparquote mehr."
        if kind == "specialize":
            return self._specialize(data)
        return False, "Unbekannte Aktion."

    def _cell(self, raw: object) -> Optional[Grid]:
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        if any(isinstance(value, bool) or not isinstance(value, int) for value in raw):
            return None
        cell = (raw[0], raw[1])
        cols, rows = self.map.grid_size
        if not (0 <= cell[0] < cols and 0 <= cell[1] < rows):
            return None
        return cell

    def _build(self, data: Dict) -> Tuple[bool, str]:
        tower_kind = data.get("tower")
        cell = self._cell(data.get("cell"))
        if tower_kind not in TOWER_DEFS or cell is None:
            return False, "Ungültiger Bauauftrag."
        if tower_kind == "laser" and "tech_laser" not in self.research:
            return False, "Laser-Technologie muss zuerst erforscht werden."
        protected = {route[0] for route in self.map.paths} | {route[-1] for route in self.map.paths}
        if cell in protected:
            return False, "Spawn und Basis dürfen nicht blockiert werden."
        if self.map.layout_mode == "fixed" and cell not in self.map.pads:
            return False, "Auf dieser festen Karte ist dort kein Bauplatz."
        if any(t.cell == cell for t in self.towers.values()):
            return False, "Dieser Bauplatz ist bereits belegt."
        cost = self._build_cost(tower_kind)
        if self.gold < cost:
            return False, "Zu wenig Coins."
        candidate_blocked = set(t.cell for t in self.towers.values())
        candidate_blocked.add(cell)
        if self.map.layout_mode == "maze" and not self._all_ground_routes_open(candidate_blocked):
            return False, "Ungültig: Dieser Turm würde den letzten Laufweg blockieren."
        self.gold -= cost
        tower = Tower.create(self.next_tower_id, tower_kind, cell)
        self.towers[tower.tid] = tower
        self.next_tower_id += 1
        self.path_cache.clear()
        clear_path_cache()
        self._refresh_enemy_routes()
        self.set_status(f"{tower.spec['name']} errichtet.")
        return True, "gebaut"

    def _build_plan(self, data: Dict) -> Tuple[bool, str]:
        """Validate and commit several placements as one transaction."""
        actions = data.get("actions")
        if not isinstance(actions, list) or not actions:
            return False, "Der Bauplan ist leer."
        if len(actions) > 20:
            return False, "Der Bauplan enthält zu viele Türme."
        protected = {route[0] for route in self.map.paths} | {route[-1] for route in self.map.paths}
        occupied = {tower.cell for tower in self.towers.values()}
        validated: List[Tuple[str, Grid, int]] = []
        total_cost = 0
        for action in actions:
            if not isinstance(action, dict):
                return False, "Ungültiger Eintrag im Bauplan."
            tower_kind = action.get("tower")
            cell = self._cell(action.get("cell"))
            if tower_kind not in TOWER_DEFS or cell is None:
                return False, "Ungültiger Eintrag im Bauplan."
            if tower_kind == "laser" and "tech_laser" not in self.research:
                return False, "Laser-Technologie muss zuerst erforscht werden."
            if cell in protected:
                return False, "Spawn und Basis dürfen nicht blockiert werden."
            if self.map.layout_mode == "fixed" and cell not in self.map.pads:
                return False, "Auf dieser festen Karte ist dort kein Bauplatz."
            if cell in occupied:
                return False, "Der Bauplan enthält einen belegten Bauplatz."
            occupied.add(cell)
            cost = self._build_cost(tower_kind)
            total_cost += cost
            validated.append((tower_kind, cell, cost))
            if self.map.layout_mode == "maze" and not self._all_ground_routes_open(occupied):
                return False, "Ungültig: Der Bauplan blockiert den letzten Laufweg."
        if self.gold < total_cost:
            return False, "Zu wenig Coins für den vollständigen Bauplan."
        self.gold -= total_cost
        for tower_kind, cell, _ in validated:
            tower = Tower.create(self.next_tower_id, tower_kind, cell)
            self.towers[tower.tid] = tower
            self.next_tower_id += 1
        self.path_cache.clear()
        clear_path_cache()
        self._refresh_enemy_routes()
        self.set_status(f"Bauplan bestätigt: {len(validated)} Türme für {total_cost} Coins.")
        return True, "bauplan bestätigt"

    def _build_cost(self, tower_kind: str) -> int:
        discount = 0.90 if "eco_build" in self.research else 1.0
        return max(1, int(TOWER_DEFS[tower_kind]["cost"] * discount))

    def _all_ground_routes_open(self, blocked: set[Grid]) -> bool:
        return all(find_path(route[0], route[-1], blocked, self.map.grid_size) for route in self.map.paths)

    def path_preview(self, cell: Optional[Grid] = None) -> Optional[Tuple[Grid, ...]]:
        if self.map.layout_mode == "fixed":
            return tuple(self.map.paths[0])
        blocked = {t.cell for t in self.towers.values()}
        if cell is not None:
            blocked.add(cell)
        start, goal = self.map.paths[0][0], self.map.paths[0][-1]
        return find_path(start, goal, blocked, self.map.grid_size)

    def _tower(self, data: Dict) -> Optional[Tower]:
        try:
            return self.towers.get(int(data.get("tower_id")))
        except (TypeError, ValueError):
            return None

    def _upgrade(self, data: Dict) -> Tuple[bool, str]:
        tower = self._tower(data)
        if tower is None:
            return False, "Turm nicht gefunden."
        if not tower.can_upgrade():
            return False, "Dieser Turm hat bereits Stufe 3."
        cost = tower.upgrade_cost()
        if self.gold < cost:
            return False, "Zu wenig Coins für das Upgrade."
        self.gold -= tower.upgrade()
        self.set_status(f"{tower.spec['name']} auf Stufe {tower.level} aufgewertet.")
        return True, "aufgewertet"

    def _sell(self, data: Dict) -> Tuple[bool, str]:
        tower = self._tower(data)
        if tower is None:
            return False, "Turm nicht gefunden."
        refund_factor = 0.65 + (0.15 if "eco_salvage" in self.research else 0.0)
        refund = int(tower.invested * refund_factor)
        self.gold += refund
        del self.towers[tower.tid]
        self.path_cache.clear()
        clear_path_cache()
        self._refresh_enemy_routes()
        self.set_status(f"Turm verkauft: +{refund} Coins.")
        return True, "verkauft"

    def _priority(self, data: Dict) -> Tuple[bool, str]:
        tower = self._tower(data)
        if tower is None:
            return False, "Turm nicht gefunden."
        tower.next_priority()
        self.set_status(f"Zielpriorität: {PRIORITY_LABELS[tower.priority]}")
        return True, "priorität geändert"

    def _start_wave(self) -> Tuple[bool, str]:
        if self.plan is not None or self.enemies:
            return False, "Die aktuelle Welle läuft noch."
        if self.mode in ("big_combo", "bounty_hunter") and self.next_wave_timer > 0:
            return False, f"Die nächste Welle startet automatisch in {self.next_wave_timer:.1f} Sekunden."
        self.wave += 1
        self.next_wave_timer = 0.0
        self.plan = WavePlan.build(
            self.wave,
            float(self.difficulty["count_scale"]),
            float(self.difficulty["spawn_scale"]),
            self.mode,
            self.seed,
        )
        if self.mode == "big_combo":
            self.combo_summary = self._combo_summary(self.wave)
            if self.wave % 5 == 0:
                self.set_status(f"{mode_name(self.mode)} · Spezialwelle {self.wave}: {' · '.join(self.combo_summary)}", 4.0)
            else:
                self.set_status(f"{mode_name(self.mode)} · Welle {self.wave}: {' · '.join(self.combo_summary)}", 3.0)
        else:
            self.set_status(f"Welle {self.wave} beginnt!", 3.0)
        return True, "welle gestartet"

    @staticmethod
    def _combo_summary(number: int) -> List[str]:
        roles = ["Schnelle Einheiten", "Gepanzerte Front", "Unterstützung durch Heiler"]
        if number % 5 == 0:
            roles.extend(("Schildgenerator", "Belagerungsdruck", "Bossfähigkeit"))
        elif number % 3 == 0:
            roles.append("Fliegende Flankierer")
        return roles

    def _select_map(self, data: Dict) -> Tuple[bool, str]:
        if not self.game_over and (self.wave > 0 or self.plan is not None or self.enemies):
            return False, "Kartenwechsel nur vor der ersten Welle möglich."
        try:
            index = int(data.get("map_index"))
        except (TypeError, ValueError):
            return False, "Ungültige Karte."
        self.reset_map(index)
        return True, "karte gewählt"

    def _restart(self, data: Dict) -> Tuple[bool, str]:
        """Reset the complete run, including a still-populated loss state."""
        try:
            index = int(data.get("map_index", self.map_index))
        except (TypeError, ValueError):
            return False, "Ungültige Karte."
        difficulty = data.get("difficulty", self.difficulty_key)
        if not isinstance(difficulty, str) or difficulty not in DIFFICULTY_DEFS:
            return False, "Ungültige Schwierigkeit."
        mode = data.get("mode", self.mode)
        if mode not in ("classic", "big_combo", "bounty_hunter"):
            return False, "Ungültiger Spielmodus."
        self.mode = mode
        self.reset_map(index, difficulty)
        self.set_status("Neuer Lauf gestartet. Baut eure Verteidigung.", 4.0)
        return True, "neustart"

    def _select_difficulty(self, data: Dict) -> Tuple[bool, str]:
        if self.wave > 0 or self.plan is not None or self.enemies:
            return False, "Schwierigkeit nur vor der ersten Welle änderbar."
        key = data.get("difficulty")
        if not isinstance(key, str) or key not in DIFFICULTY_DEFS:
            return False, "Ungültige Schwierigkeit."
        self.reset_map(self.map_index, key)
        return True, "schwierigkeit gewählt"

    def _select_mode(self, data: Dict) -> Tuple[bool, str]:
        if self.wave > 0 or self.plan is not None or self.enemies:
            return False, "Der Spielmodus kann nur vor der ersten Welle gewählt werden."
        mode = data.get("mode")
        if mode not in ("classic", "big_combo", "bounty_hunter"):
            return False, "Ungültiger Spielmodus."
        self.mode = mode
        self.set_status(mode_name(mode))
        return True, "modus gewählt"

    def _research(self, data: Dict) -> Tuple[bool, str]:
        key = data.get("research")
        spec = RESEARCH_DEFS.get(key)
        if spec is None:
            return False, "Unbekannte Forschung."
        if key in self.research:
            return False, "Diese Forschung wurde bereits erworben."
        if self.wave < spec["wave"]:
            return False, f"Freigeschaltet ab Welle {spec['wave']}."
        if any(req not in self.research for req in spec["requires"]):
            return False, "Voraussetzungen fehlen."
        if any(conflict in self.research for conflict in spec.get("conflicts", ())):
            return False, "Dieser Forschungszweig schließt die gewählte Alternative aus."
        if self.gold < spec["cost"]:
            return False, "Zu wenig Coins für die Forschung."
        self.gold -= spec["cost"]
        self.research.add(key)
        if spec["effect"] == "income":
            self.round_income += 2
            self.income_rate = float(self.round_income)
        self.set_status(f"Forschung erworben: {spec['name']}")
        return True, "forschung erworben"

    def _invest(self, data: Dict) -> Tuple[bool, str]:
        if self.mode != "big_combo":
            return False, "Investitionen gibt es nur in Megalomanie."
        try:
            percent = int(data.get("percent"))
        except (TypeError, ValueError):
            return False, "Investitionsanteil muss zwischen 1 und 100 Prozent liegen."
        if not 1 <= percent <= 100:
            return False, "Investitionsanteil muss zwischen 1 und 100 Prozent liegen."
        amount = int(self.gold * percent / 100)
        if amount <= 0:
            return False, "Das aktuelle Guthaben ist für diese Investition zu klein."
        self.gold -= amount
        self.investments += amount
        self.investment_percent = percent
        self.last_investment_amount = amount
        self.round_income += max(1, int(amount * 0.10 * (1.25 if "eco_invest" in self.research else 1.0)))
        self.income_rate = float(self.round_income)
        self.set_status(f"Megalomanie: {amount} Coins investiert · Rundeneinkommen jetzt {self.round_income} Coins.")
        return True, "investiert"

    def _specialize(self, data: Dict) -> Tuple[bool, str]:
        tower = self._tower(data)
        choice = data.get("choice")
        if tower is None:
            return False, "Turm nicht gefunden."
        if "weapon_specialist" not in self.research:
            return False, "Erwirb zuerst den Spezialistenkern."
        if not tower.specialize(choice):
            return False, "Spezialisierung bereits gewählt oder ungültig."
        self.set_status(f"{tower.spec['name']} spezialisiert: {choice.upper()}")
        return True, "spezialisiert"

    def _choose_route(self) -> List[Grid]:
        # Load-sensitive random choice makes branches feel alive while remaining deterministic on host.
        occupancy = Counter()
        for enemy in self.enemies.values():
            route_key = tuple(enemy.route)
            occupancy[route_key] += 1
        weights = []
        for route in self.map.paths:
            load = occupancy[tuple(route)]
            weights.append(1.0 / (1 + load * 0.55))
        return list(self.random.choices(self.map.paths, weights=weights, k=1)[0])

    def _spawn(self, enemy_kind: str) -> None:
        enemy_kind = ENEMY_ALIASES.get(enemy_kind, enemy_kind)
        if self.mode == "big_combo" and not self.income_timer_active:
            self.income_timer_active = True
            self.income_clock = 0.0
        health_scale = (1.0 + (self.wave - 1) * 0.105) * float(self.difficulty["health_scale"])
        route = self._choose_route()
        if ENEMY_DEFS[enemy_kind].get("flying"):
            route = list(find_path(route[0], route[-1], (), self.map.grid_size)) or route
        elif self.map.layout_mode == "fixed":
            route = list(route)
        else:
            dynamic_route = find_path(route[0], route[-1], {t.cell for t in self.towers.values()}, self.map.grid_size)
            route = list(dynamic_route) if dynamic_route else route
        enemy = Enemy.create(self.next_enemy_id, enemy_kind, route, health_scale)
        self.enemies[enemy.eid] = enemy
        self.next_enemy_id += 1

    def _refresh_enemy_routes(self) -> None:
        if self.map.layout_mode == "fixed":
            return
        blocked = {t.cell for t in self.towers.values()}
        for enemy in self.enemies.values():
            if enemy.spec.get("flying"):
                continue
            position = enemy.grid_position()
            goal = enemy.route[-1]
            route = route_for_position(enemy.grid_position(), goal, blocked, self.map.grid_size)
            if route:
                enemy.route = route
                nearest = min(range(len(route)), key=lambda index: self._distance(position, route[index]))
                enemy.progress = float(nearest)

    @staticmethod
    def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _targets_in_range(self, tower: Tower) -> List[Enemy]:
        center = (tower.cell[0] + 0.5, tower.cell[1] + 0.5)
        radius = self._tower_stat(tower, "range")
        return [enemy for enemy in self.enemies.values() if enemy.alive and self._distance(center, enemy.grid_position()) <= radius]

    def _tower_stat(self, tower: Tower, name: str) -> float:
        value = tower.stat(name)
        if name == "damage" and "weapon_damage" in self.research:
            value *= 1.12
        if name == "damage" and tower.kind == "laser" and "tech_laser_damage" in self.research:
            value *= 1.25
        if name == "range" and "weapon_targeting" in self.research:
            value *= 1.12
        if name == "range" and tower.kind == "laser" and "tech_laser_range" in self.research:
            value *= 1.22
        if name == "cooldown":
            if "weapon_projectiles" in self.research:
                value *= 0.833333
            if "weapon_velocity" in self.research:
                value *= 0.90
        return value

    def _support_bonus(self, tower: Tower, name: str) -> float:
        bonus = 0.0
        for support in self.towers.values():
            if support.kind != "support" or support.tid == tower.tid:
                continue
            if self._distance((support.cell[0] + 0.5, support.cell[1] + 0.5), (tower.cell[0] + 0.5, tower.cell[1] + 0.5)) <= self._tower_stat(support, "range"):
                amount = self._tower_stat(support, "support")
                if "tech_support" in self.research:
                    amount *= 1.35
                if support.specialization == "a" and name == "cooldown":
                    amount *= 1.35
                bonus += amount
        return bonus

    def _choose_target(self, tower: Tower, candidates: List[Enemy]) -> Optional[Enemy]:
        if not candidates:
            return None
        center = (tower.cell[0] + 0.5, tower.cell[1] + 0.5)
        if tower.priority == "strong":
            return max(candidates, key=lambda e: (e.hp, e.progress))
        if tower.priority == "near":
            return min(candidates, key=lambda e: self._distance(center, e.grid_position()))
        if tower.priority == "last":
            return min(candidates, key=lambda e: (e.progress, e.eid))
        return max(candidates, key=lambda e: e.progress)

    def _damage_enemy(self, enemy: Enemy, damage: float, slow: Optional[float] = None, ignore_armor: bool = False, tower: Optional[Tower] = None) -> None:
        if any(
            other.eid != enemy.eid and other.kind == "shield"
            and self._distance(other.grid_position(), enemy.grid_position()) <= 2.4
            for other in self.enemies.values()
        ):
            damage *= 0.80
        before_hp = enemy.hp
        defeated = enemy.damage(damage, slow, ignore_armor=ignore_armor)
        if tower is not None:
            tower.total_damage += max(0.0, before_hp - max(0.0, enemy.hp))
        if defeated:
            if tower is not None:
                tower.kills += 1
            self._kill(enemy)
        elif slow is not None and "tech_effects" in self.research:
            enemy.slow_timer = max(enemy.slow_timer, 1.8)

    def _kill(self, enemy: Enemy) -> None:
        if enemy.eid not in self.enemies:
            return
        self.gold += ENEMY_DEFS[enemy.kind]["reward"] + max(0, self.wave // 3)
        self.total_kills += 1
        del self.enemies[enemy.eid]

    def _fire(self, tower: Tower) -> None:
        if tower.kind == "support":
            tower.cooldown = self._tower_stat(tower, "cooldown")
            return
        targets = self._targets_in_range(tower)
        primary = self._choose_target(tower, targets)
        if primary is None:
            return
        origin = (tower.cell[0] + 0.5, tower.cell[1] + 0.5)
        target_position = primary.grid_position()
        spec = tower.spec
        damage = self._tower_stat(tower, "damage") * (1.0 + self._support_bonus(tower, "damage"))
        points = [origin, target_position]
        if tower.kind in ("cannon", "artillery"):
            self._damage_enemy(primary, damage, ignore_armor=(tower.kind == "artillery" and tower.specialization == "b"), tower=tower)
            splash = self._tower_stat(tower, "splash") * (1.25 if "tech_splash" in self.research else 1.0)
            for other in list(self.enemies.values()):
                if other.eid != primary.eid and self._distance(other.grid_position(), target_position) <= splash:
                    self._damage_enemy(other, damage * 0.42, tower=tower)
            self.effects.append(Effect("burst", [target_position], spec["projectile"], 0.22, 3))
        elif tower.kind == "frost":
            self._damage_enemy(primary, damage, spec["slow"], tower=tower)
        elif tower.kind == "tesla":
            hit = {primary.eid}
            current = primary
            chain = int(self._tower_stat(tower, "chain")) + (1 if "tech_tesla" in self.research and tower.specialization != "b" else 0)
            for _ in range(chain - 1):
                available = [e for e in self.enemies.values() if e.eid not in hit and self._distance(current.grid_position(), e.grid_position()) <= 2.15]
                if not available:
                    break
                next_enemy = min(available, key=lambda e: self._distance(current.grid_position(), e.grid_position()))
                points.append(next_enemy.grid_position())
                self._damage_enemy(next_enemy, damage * 0.73, tower=tower)
                hit.add(next_enemy.eid)
                current = next_enemy
            self._damage_enemy(primary, damage, tower=tower)
        elif tower.kind == "laser":
            self._damage_enemy(primary, damage, ignore_armor=(tower.specialization == "a"), tower=tower)
        else:
            self._damage_enemy(primary, damage, tower=tower)
        self.effects.append(Effect("beam", points, spec["projectile"], 0.12, 3 if tower.kind == "tesla" else 2))
        tower.cooldown = self._tower_stat(tower, "cooldown") * max(0.35, 1.0 - self._support_bonus(tower, "cooldown"))

    def tick(self, dt: float) -> None:
        if self.game_over:
            return
        self.status_timer = max(0.0, self.status_timer - dt)
        if self.next_wave_timer > 0:
            self.next_wave_timer = max(0.0, self.next_wave_timer - dt)
        self.survival_time += dt
        if self.mode == "big_combo" and self.income_timer_active:
            self.income_clock += dt
            while self.income_clock >= 30.0:
                self.income_clock -= 30.0
                payout = self.round_income
                self.gold += payout
                self.total_credits_earned += payout
                self.last_wave_income = payout
                self.set_status(f"Megalomanie-Tick: +{payout} Coins. Nächster Tick in 30 Sekunden.", 3.0)
        for effect in self.effects:
            effect.tick(dt)
        self.effects = [effect for effect in self.effects if effect.ttl > 0]
        if self.mode in ("big_combo", "bounty_hunter") and self.wave > 0 and self.next_wave_timer <= 0 and self.plan is None and not self.enemies:
            self._start_wave()
        if self.plan is not None:
            spawned = self.plan.tick(dt)
            if spawned:
                self._spawn(spawned)
        for enemy in list(self.enemies.values()):
            if enemy.spec.get("boss"):
                enemy.ability_timer -= dt
                if enemy.ability_timer <= 0:
                    enemy.ability_timer = 8.0
                    enemy.hp = min(enemy.max_hp, enemy.hp + enemy.max_hp * 0.08)
                    enemy.slow_factor = 1.0
                    self.effects.append(Effect("burst", [enemy.grid_position()], (244, 107, 202), 0.35, 3))
                    self.set_status("Bossfähigkeit: Regeneration und Wut aktiviert!", 1.8)
            if enemy.kind == "healer":
                for other in self.enemies.values():
                    if other.eid != enemy.eid and self._distance(enemy.grid_position(), other.grid_position()) <= 2.0:
                        other.hp = min(other.max_hp, other.hp + float(enemy.spec["heal"]) * dt)
            enemy.tick(dt)
            if enemy.reached_castle:
                self.enemies.pop(enemy.eid, None)
                self.lives -= int(enemy.spec.get("base_damage", 1))
                self.set_status("Ein Gegner hat die Burg erreicht!", 1.6)
                if self.lives <= 0:
                    self.lives = 0
                    self.game_over = True
                    self.set_status("Die Burg ist gefallen. Drückt M für eine neue Karte.", 99.0)
        for tower in list(self.towers.values()):
            tower.tick(dt)
            if tower.cooldown <= 0:
                self._fire(tower)
        if self.plan is not None and not self.plan.queue and not self.enemies:
            self.plan = None
            bonus = 8 + self.wave * 2
            if self.mode != "big_combo" and "eco_repairs" in self.research:
                bonus += 2
            repair_lives = 2 if "eco_repairs" in self.research else 1
            self.lives = min(self.max_lives, self.lives + repair_lives)
            if self.mode == "big_combo":
                next_tick = max(0.0, 30.0 - self.income_clock)
                self.set_status(f"Welle {self.wave} abgewehrt! Nächster Coin-Tick in {next_tick:.1f} Sekunden · +{repair_lives} Burgleben.", 5.0)
            else:
                self.last_wave_income = bonus
                self.gold += bonus
                self.total_credits_earned += bonus
                self.set_status(f"Welle {self.wave} abgewehrt! +{bonus} Coins Rundeneinkommen und +{repair_lives} Burgleben.", 5.0)
            if self.mode in ("big_combo", "bounty_hunter"):
                self.next_wave_timer = self.auto_wave_delay

    def _tower_snapshot(self, tower: Tower) -> Dict:
        payload = tower.serialize()
        payload["damage"] = round(self._tower_stat(tower, "damage"), 1)
        payload["range"] = round(self._tower_stat(tower, "range"), 2)
        cooldown = self._tower_stat(tower, "cooldown")
        payload["cooldown"] = round(cooldown, 3)
        payload["fire_rate"] = round(1.0 / cooldown, 2) if cooldown > 0 else 0.0
        payload["support_power"] = round(self._tower_stat(tower, "support"), 3) if tower.kind == "support" else 0.0
        payload["research_bonuses"] = [key for key in sorted(self.research) if key.startswith(("weapon_", "tech_"))]
        return payload

    def snapshot(self, players: Optional[int] = None) -> Dict:
        players = self.player_count if players is None else max(1, int(players))
        return {
            "type": "state", "version": 2,
            "map_index": self.map_index, "map_title": self.map.title, "map_subtitle": self.map.subtitle,
            "layout_mode": self.map.layout_mode,
            "mode": self.mode, "mode_name": mode_name(self.mode),
            "difficulty": self.difficulty_key, "difficulty_name": self.difficulty["name"],
            "max_lives": self.max_lives, "credits": self.gold,
            "gold": self.gold, "lives": self.lives, "wave": self.wave,
            "spawn_remaining": self.plan.remaining if self.plan else 0,
            "wave_active": self.plan is not None or bool(self.enemies),
            "next_wave_in": round(self.next_wave_timer, 1),
            "income_tick_in": round(max(0.0, 30.0 - self.income_clock), 1) if self.mode == "big_combo" and self.income_timer_active else None,
            "income_timer_active": self.income_timer_active,
            "first_wave_start_required": self.mode in ("big_combo", "bounty_hunter") and self.wave == 0,
            "status": self.status if self.status_timer > 0 else "",
            "game_over": self.game_over, "players": players, "resource_share_percent": round(100.0 / players, 1), "kills": self.total_kills,
            "research": sorted(self.research), "research_status": research_status(self.research, self.wave, self.gold),
            "investments": self.investments, "income_rate": round(self.round_income, 2),
            "round_income": self.round_income, "investment_percent": self.investment_percent,
            "last_investment_amount": self.last_investment_amount, "last_wave_income": self.last_wave_income,
            "investment_preview": {
                "percent": self.investment_percent,
                "amount": int(self.gold * self.investment_percent / 100),
                "remaining": self.gold - int(self.gold * self.investment_percent / 100),
                "new_round_income": self.round_income + max(1, int(self.gold * self.investment_percent / 100 * 0.10 * (1.25 if "eco_invest" in self.research else 1.0))) if self.investment_percent and int(self.gold * self.investment_percent / 100) > 0 else self.round_income,
            },
            "survival_time": round(self.survival_time, 1), "total_credits_earned": self.total_credits_earned,
            "combo_summary": list(self.combo_summary),
            "wave_preview": (self.plan.preview() if self.plan is not None else WavePlan.build(
                self.wave + 1,
                float(self.difficulty["count_scale"]),
                float(self.difficulty["spawn_scale"]),
                self.mode,
                self.seed,
            ).preview()),
            "preview_route": [list(cell) for cell in (self.path_preview() or ())],
            "towers": [self._tower_snapshot(tower) for tower in self.towers.values()],
            "enemies": [enemy.serialize() for enemy in self.enemies.values()],
            "effects": [effect.serialize() for effect in self.effects],
        }
