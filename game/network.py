from __future__ import annotations
import json
import queue
import socket
import threading
from typing import Dict, List, Optional, Tuple


def _encode(message: Dict) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


class HostServer:
    """Non-blocking threaded TCP host using newline-delimited JSON messages."""
    def __init__(self, port: int) -> None:
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.port = int(self.sock.getsockname()[1])
        self.sock.listen()
        self.sock.settimeout(0.5)
        self.clients: List[socket.socket] = []
        self.clients_lock = threading.Lock()
        self.actions: "queue.Queue[Dict]" = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._accept_loop, name="host-accept", daemon=True)
        self.thread.start()

    @property
    def player_count(self) -> int:
        with self.clients_lock:
            return 1 + len(self.clients)

    def _accept_loop(self) -> None:
        while self.running:
            try:
                client, _ = self.sock.accept()
                client.settimeout(0.5)
                with self.clients_lock:
                    self.clients.append(client)
                threading.Thread(target=self._receive_loop, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _receive_loop(self, client: socket.socket) -> None:
        buffer = b""
        try:
            while self.running:
                try:
                    chunk = client.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    try:
                        message = json.loads(raw.decode("utf-8"))
                        if isinstance(message, dict) and message.get("type") != "state":
                            self.actions.put(message)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
        finally:
            self._remove(client)

    def drain_actions(self) -> List[Dict]:
        actions: List[Dict] = []
        while True:
            try:
                actions.append(self.actions.get_nowait())
            except queue.Empty:
                return actions

    def broadcast(self, snapshot: Dict) -> None:
        data = _encode(snapshot)
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            try:
                client.sendall(data)
            except OSError:
                self._remove(client)

    def _remove(self, client: socket.socket) -> None:
        with self.clients_lock:
            if client in self.clients:
                self.clients.remove(client)
        try:
            client.close()
        except OSError:
            pass

    def close(self) -> None:
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            self._remove(client)


class NetworkClient:
    def __init__(self, host: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect((host, port))
        self.sock.settimeout(0.5)
        self.latest_state: Optional[Dict] = None
        self.lock = threading.Lock()
        self.connected = True
        self.thread = threading.Thread(target=self._receive_loop, name="client-receive", daemon=True)
        self.thread.start()

    def _receive_loop(self) -> None:
        buffer = b""
        try:
            while self.connected:
                try:
                    chunk = self.sock.recv(8192)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    try:
                        message = json.loads(raw.decode("utf-8"))
                        if isinstance(message, dict) and message.get("type") == "state":
                            with self.lock:
                                self.latest_state = message
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
        finally:
            self.connected = False
            with self.lock:
                self.latest_state = None

    def state(self) -> Optional[Dict]:
        with self.lock:
            return dict(self.latest_state) if self.latest_state else None

    def send_action(self, action: Dict) -> bool:
        if not self.connected:
            return False
        try:
            self.sock.sendall(_encode(action))
            return True
        except OSError:
            self.connected = False
            return False

    def close(self) -> None:
        self.connected = False
        try:
            self.sock.close()
        except OSError:
            pass
