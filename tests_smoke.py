from __future__ import annotations
import json
import time

from game.constants import ENEMY_DEFS, TOWER_DEFS
from game.network import HostServer, NetworkClient
from game.state import GameState


def test_rules() -> None:
    assert ENEMY_DEFS["scout"]["reward"] == 6
    assert TOWER_DEFS["cannon"]["damage"] == 32
    assert TOWER_DEFS["cannon"]["splash"] == 1.38
    assert TOWER_DEFS["artillery"]["splash"] > TOWER_DEFS["cannon"]["splash"]
    assert TOWER_DEFS["artillery"]["splash"] == 3.45
    assert TOWER_DEFS["artillery"]["range"] == 3.1
    state = GameState(map_index=1, difficulty="hard")
    assert state.map_index == 1
    assert state.gold == 235
    assert state.lives == 16
    ok, _ = state.action({"type": "build", "tower": "archer", "cell": [2, 3]})
    if not ok:
        ok, _ = state.action({"type": "build", "tower": "archer", "cell": [1, 1]})
    assert ok
    tower_id = next(iter(state.towers))
    ok, _ = state.action({"type": "priority", "tower_id": tower_id})
    assert ok and state.towers[tower_id].priority == "strong"
    ok, _ = state.action({"type": "upgrade", "tower_id": tower_id})
    assert ok and state.towers[tower_id].level == 2
    ok, _ = state.action({"type": "start_wave"})
    assert ok
    for _ in range(140):
        state.tick(1 / 30)
    snapshot = state.snapshot(1)
    assert snapshot["wave"] == 1
    assert snapshot["enemies"]
    json.dumps(snapshot)


def test_network() -> None:
    server = HostServer(0)
    client = NetworkClient("127.0.0.1", server.port)
    try:
        time.sleep(0.12)
        state = GameState()
        pad = list(state.map.pads)[0]
        assert client.send_action({"type": "build", "tower": "archer", "cell": list(pad)})
        assert client.send_action({"type": "start_wave"})
        deadline = time.monotonic() + 2
        actions = []
        while time.monotonic() < deadline and len(actions) < 2:
            actions.extend(server.drain_actions())
            time.sleep(0.02)
        assert [action["type"] for action in actions] == ["build", "start_wave"]
        for action in actions:
            ok, message = state.action(action)
            assert ok, message
        server.broadcast(state.snapshot(server.player_count))
        deadline = time.monotonic() + 2
        received = None
        while time.monotonic() < deadline and received is None:
            received = client.state()
            time.sleep(0.02)
        assert received is not None and received["type"] == "state"
        assert received["wave"] == 1 and len(received["towers"]) == 1
    finally:
        client.close()
        server.close()


if __name__ == "__main__":
    test_rules()
    test_network()
    print("Smoke test passed: rules and TCP state sync are working.")
