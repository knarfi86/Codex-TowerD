from __future__ import annotations

from game.constants import ENEMY_DEFS, TOWER_TYPES
from game.entities import Tower, WavePlan
from game.maps import MAPS
from game.pathfinding import find_path
from game.state import GameState


def test_bfs_keeps_a_route_or_reports_a_full_block() -> None:
    assert find_path((0, 0), (4, 0), ())
    # The target is enclosed on all four sides.
    blocked = ((3, 0), (4, 1), (5, 0), (4, -1))
    assert find_path((0, 0), (4, 0), blocked) is None

    fixed = GameState()
    ok, message = fixed.action({"type": "build", "tower": "mg", "cell": [1, 5]})
    assert not ok and "festen Karte" in message

    maze_index = next(index for index, map_def in enumerate(MAPS) if map_def.key == "tower_maze")
    state = GameState(map_index=maze_index)
    state.gold = 1000
    for cell in ((0, 4), (0, 6)):
        ok, message = state.action({"type": "build", "tower": "mg", "cell": list(cell)})
        assert ok, message
    ok, message = state.action({"type": "build", "tower": "mg", "cell": [1, 5]})
    assert not ok and "blockieren" in message


def test_predefined_maps_keep_their_original_routes() -> None:
    for index, map_def in enumerate(MAPS):
        if map_def.layout_mode != "fixed":
            continue
        state = GameState(map_index=index)
        state.wave = 1
        state._spawn("scout")
        enemy = next(iter(state.enemies.values()))
        assert tuple(enemy.route) in map_def.paths


def test_five_towers_and_specialization_data_are_real() -> None:
    state = GameState()
    state.gold = 5000
    state.research.add("tech_laser")
    cells = list(state.map.pads)
    for kind, cell in zip(TOWER_TYPES, cells):
        ok, message = state.action({"type": "build", "tower": kind, "cell": list(cell)})
        assert ok, message
    assert {tower.kind for tower in state.towers.values()} == set(TOWER_TYPES)
    support = next(t for t in state.towers.values() if t.kind == "support")
    state.research.add("weapon_specialist")
    ok, _ = state.action({"type": "specialize", "tower_id": support.tid, "choice": "a"})
    assert ok and support.specialization == "a"


def test_each_tower_specialization_changes_its_promised_stat() -> None:
    variants = {}
    for kind in TOWER_TYPES:
        first = Tower.create(1, kind, (1, 1))
        second = Tower.create(2, kind, (2, 1))
        assert first.specialize("a") and second.specialize("b")
        variants[kind] = (first, second)
    mg_a, mg_b = variants["mg"]
    assert mg_a.stat("cooldown") < mg_b.stat("cooldown") and mg_b.stat("damage") > mg_a.stat("damage")
    artillery_a, artillery_b = variants["artillery"]
    assert artillery_a.stat("splash") > artillery_b.stat("splash") and artillery_b.stat("damage") > artillery_a.stat("damage")
    laser_a, laser_b = variants["laser"]
    assert laser_a.stat("damage") > laser_b.stat("damage") and laser_b.stat("range") > laser_a.stat("range")
    tesla_a, tesla_b = variants["tesla"]
    assert tesla_a.stat("chain") > tesla_b.stat("chain") and tesla_b.stat("damage") > tesla_a.stat("damage")
    support_a, support_b = variants["support"]
    assert support_a.stat("cooldown") < support_b.stat("cooldown") and support_b.stat("support") > support_a.stat("support")


def test_research_is_credit_paid_and_wave_locked() -> None:
    state = GameState()
    state.gold = 1000
    ok, message = state.action({"type": "research", "research": "tech_laser"})
    assert not ok and "Welle 3" in message
    state.wave = 3
    before = state.gold
    ok, _ = state.action({"type": "research", "research": "tech_laser"})
    assert ok and state.gold < before and "tech_laser" in state.research
    assert state.snapshot()["research_status"]["tech_laser"]["state"] == "purchased"


def test_big_combo_builds_role_based_special_wave_and_investment_income() -> None:
    state = GameState(mode="big_combo")
    state.gold = 1000
    ok, _ = state.action({"type": "invest", "percent": 10})
    assert ok and state.investments == 100 and state.round_income > 100 and state.gold == 900
    state.wave = 4
    ok, _ = state.action({"type": "start_wave"})
    assert ok and state.wave == 5
    assert {"boss", "shield", "healer", "siege"}.issubset(set(state.plan.queue))
    assert "Bossfähigkeit" in state.combo_summary


def test_multiplayer_scales_shared_starting_resources_and_income_by_player_count() -> None:
    state = GameState(mode="big_combo")
    assert state.gold == 280 and state.round_income == 100

    state.set_player_count(2)
    assert state.gold == 140 and state.round_income == 50
    assert state.snapshot(players=2)["resource_share_percent"] == 50.0

    state.set_player_count(4)
    assert state.gold == 70 and state.round_income == 25
    state.set_player_count(1)
    assert state.gold == 280 and state.round_income == 100


def test_megalomania_pays_income_every_thirty_seconds() -> None:
    state = GameState(mode="big_combo")
    before = state.gold
    state.tick(60.0)
    assert state.gold == before
    assert state.snapshot()["income_tick_in"] is None
    assert state.action({"type": "start_wave"})[0]
    state.tick(0.31)
    assert state.snapshot()["income_timer_active"] is True
    state.tick(29.9)
    assert state.gold == before
    income = state.round_income
    state.tick(0.1)
    assert state.gold == before + income
    assert state.snapshot()["income_tick_in"] == 30.0

    state.action({"type": "invest", "percent": 25})
    assert state.gold == int((before + income) * 0.75)


def test_enemy_roles_have_mechanical_capabilities() -> None:
    assert ENEMY_DEFS["wisp"]["flying"] is True
    assert ENEMY_DEFS["healer"]["heal"] > 0
    assert ENEMY_DEFS["shield"]["shield"] > 0
    assert ENEMY_DEFS["siege"]["base_damage"] > 1
    assert ENEMY_DEFS["boss"]["boss"] is True

    state = GameState(mode="big_combo")
    state.wave = 4
    assert state.action({"type": "start_wave"})[0]
    state._spawn("boss")
    boss = next(iter(state.enemies.values()))
    boss.hp = 400
    for _ in range(181):
        state.tick(1 / 30)
    assert boss.hp > 400


def test_loss_freezes_survival_time_and_income() -> None:
    state = GameState(mode="big_combo")
    state.income_rate = 10.0
    state.income_clock = 0.4
    state.income_timer_active = True
    state.survival_time = 12.0
    state.game_over = True
    before = (state.gold, state.income_clock, state.survival_time)
    state.tick(5.0)
    assert (state.gold, state.income_clock, state.survival_time) == before


def test_loss_restart_clears_the_entire_run() -> None:
    state = GameState(mode="big_combo")
    state.gold = 999
    state.wave = 4
    state.game_over = True
    state._spawn("scout")
    ok, message = state.action({"type": "restart"})
    assert ok, message
    assert not state.game_over
    assert state.wave == 0 and not state.enemies and not state.towers
    assert state.gold == state.difficulty["gold"]
    assert state.mode == "big_combo"


def test_build_rejects_non_integer_and_out_of_bounds_coordinates() -> None:
    state = GameState()
    before = (state.gold, len(state.towers))
    for cell in ([1.5, 1], [True, 1], [-1, 1], [20, 1], [1], "1,1"):
        ok, _ = state.action({"type": "build", "tower": "archer", "cell": cell})
        assert not ok
        assert (state.gold, len(state.towers)) == before


def test_bounty_hunter_starts_waves_automatically() -> None:
    state = GameState(mode="bounty_hunter")
    state.tick(1 / 30)
    assert state.wave == 0 and state.plan is None
    assert state.action({"type": "start_wave"})[0]
    assert state.wave == 1


def test_big_combo_starts_waves_and_applies_percentage_investment() -> None:
    state = GameState(mode="big_combo")
    state.tick(1 / 30)
    assert state.wave == 0 and state.plan is None
    assert state.action({"type": "start_wave"})[0]
    assert state.wave == 1 and state.plan is not None
    state.tick(0.31)
    state.enemies.clear()

    state.gold = 1000
    ok, _ = state.action({"type": "invest", "percent": 50})
    assert ok and state.investment_percent == 50 and state.last_investment_amount == 500 and state.gold == 500
    state.plan = WavePlan(number=1, queue=[], active=True)
    state.enemies.clear()
    state.gold = 500
    state.tick(0.0)
    assert state.last_wave_income == 0 and state.gold == 500
    state.tick(30.0)
    assert state.last_wave_income == state.round_income and state.gold == 500 + state.round_income
    assert not state.action({"type": "withdraw_reserve", "amount": 999})[0]


def test_automatic_modes_wait_before_the_next_wave() -> None:
    state = GameState(mode="big_combo")
    assert state.action({"type": "start_wave"})[0]
    state.plan = WavePlan(number=1, queue=[], active=True)
    state.enemies.clear()
    state.tick(0.0)
    assert state.next_wave_timer == state.auto_wave_delay
    state.tick(7.0)
    assert state.wave == 1
    state.tick(1.1)
    assert state.wave == 2


def test_big_combo_preview_matches_plan_and_investment_has_diminishing_returns() -> None:
    state = GameState(mode="big_combo")
    state.gold = 5000
    assert state.action({"type": "invest", "percent": 20})[0]
    assert state.round_income > 100 and state.gold == 4000
    assert state.action({"type": "start_wave"})[0]
    preview = state.snapshot()["wave_preview"]
    assert preview["number"] == state.wave
    assert preview["remaining"] == state.plan.remaining


def test_big_combo_director_is_seeded_and_changes_combinations() -> None:
    plans = [WavePlan.build(number, mode="big_combo", seed=44) for number in range(1, 5)]
    assert len({plan.combo_name for plan in plans}) >= 2
    special = WavePlan.build(5, mode="big_combo", seed=44)
    assert special.combo_name == "Boss-Belagerung"
    assert {"boss", "shield", "healer", "siege"}.issubset(set(special.queue))
    assert special.preview() == WavePlan.build(5, mode="big_combo", seed=44).preview()


def test_build_plan_is_atomic_and_charges_only_after_full_validation() -> None:
    state = GameState()
    cells = list(state.map.pads)[:2]
    state.gold = 200
    before = (state.gold, len(state.towers))
    ok, _ = state.action({"type": "build_plan", "actions": [
        {"tower": "archer", "cell": list(cells[0])},
        {"tower": "archer", "cell": [999, 999]},
    ]})
    assert not ok and (state.gold, len(state.towers)) == before
    ok, message = state.action({"type": "build_plan", "actions": [
        {"tower": "archer", "cell": list(cells[0])},
        {"tower": "mg", "cell": list(cells[1])},
    ]})
    assert ok, message
    assert len(state.towers) == 2 and state.gold == before[0] - 145


if __name__ == "__main__":
    test_bfs_keeps_a_route_or_reports_a_full_block()
    test_predefined_maps_keep_their_original_routes()
    test_five_towers_and_specialization_data_are_real()
    test_research_is_credit_paid_and_wave_locked()
    test_big_combo_builds_role_based_special_wave_and_investment_income()
    test_megalomania_pays_income_every_thirty_seconds()
    test_enemy_roles_have_mechanical_capabilities()
    test_loss_freezes_survival_time_and_income()
    test_bounty_hunter_starts_waves_automatically()
    test_big_combo_starts_waves_and_applies_percentage_investment()
    test_automatic_modes_wait_before_the_next_wave()
    test_big_combo_preview_matches_plan_and_investment_has_diminishing_returns()
    test_big_combo_director_is_seeded_and_changes_combinations()
    test_build_plan_is_atomic_and_charges_only_after_full_validation()
    print("Gameplay expansion tests passed.")
