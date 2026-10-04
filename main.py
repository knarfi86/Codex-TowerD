from __future__ import annotations
import argparse
import sys

from game.app import GameApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CreepGrid - sofort startbares Tower-Defense-Spiel"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true", help="Partie hosten (Standard)")
    mode.add_argument("--connect", metavar="IP", help="Mit einem Host verbinden")
    parser.add_argument("--port", type=int, default=5000, help="TCP-Port (Standard: 5000)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not (1 <= args.port <= 65535):
        print("Fehler: Der Port muss zwischen 1 und 65535 liegen.", file=sys.stderr)
        return 2
    try:
        host_mode = args.connect is None
        app = GameApp(host_mode=host_mode, host=args.connect or "", port=args.port)
        app.run()
        return 0
    except ConnectionRefusedError:
        print("Fehler: Verbindung abgelehnt. Läuft der Host und ist der Port freigegeben?", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Netzwerkfehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
