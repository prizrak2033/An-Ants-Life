"""
Local web server for An Ant's Life.

Runs the simulation in a background thread (the exact same
GameState.step() pipeline the console runner uses) and serves it as
JSON over HTTP, alongside a static HTML/canvas frontend that polls
for a live view.

Run with:  python3 server.py [port]
Then open: http://127.0.0.1:8765
"""
from __future__ import annotations
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config import SimConfig
from state import GameState
from systems.time import Timekeeper

WEB_DIR = Path(__file__).parent / "web"
DEFAULT_PORT = 8765


def _build_snapshot(state: GameState, paused: bool) -> dict:
    cfg = state.cfg
    colony = state.colony
    chapter = state.milestones.chapter
    territory = state.territory
    phero = state.pheromones

    return {
        "tick": state.tick,
        "t": round(state.t, 2),
        "paused": paused,
        "game_over": colony.queen.hp <= 0,
        "world": {"w": cfg.WORLD_W, "h": cfg.WORLD_H},
        "nest": [state.nest_pos[0], state.nest_pos[1]],
        "queen": {"hp": colony.queen.hp, "hp_max": colony.queen.hp_max},
        "colony": {
            "food_store": round(colony.food_store, 2),
            "stress": round(colony.stress, 3),
            "hunger": round(colony.emergency.get("hunger", 0.0), 3),
            "famine": bool(colony.emergency.get("famine_active", False)),
            "pressure": round(colony.emergency.get("territory_pressure", 0.0), 3),
            "population": len(colony.ants),
        },
        "metrics": dict(colony.metrics),
        # Ants/enemies/food are packed as flat arrays (not objects) to keep
        # the payload small at ~10 snapshots/sec: [x, y, role, carrying]
        "ants": [
            [a.x, a.y, a.role.value, 1 if a.carrying > 0 else 0]
            for a in colony.ants
        ],
        "enemies": [[e.x, e.y] for e in state.enemies],
        "food_sources": [
            [s.x, s.y, round(s.amount, 1), 1 if s.claimed else 0]
            for s in state.world.food_sources
        ],
        # Grids are flattened column-major: index = cx * rows + cy
        "territory": {
            "cell": cfg.TERR_CELL, "cols": territory.cols, "rows": territory.rows,
            "grid": [round(v, 3) for col in territory.grid for v in col],
        },
        "pheromones": {
            "cell": cfg.PHERO_GRID, "cols": phero.cols, "rows": phero.rows,
            "food": [round(v, 3) for col in phero.grids["food"] for v in col],
            "home": [round(v, 3) for col in phero.grids["home"] for v in col],
        },
        "chapter": {"active": chapter.active, "title": chapter.title if chapter.active else None},
        "chronicle": [e.headline() for e in state.history.recent(10)],
    }


class SimRunner:
    """Owns the simulation thread and the latest served snapshot."""

    def __init__(self) -> None:
        self.cfg = SimConfig()
        self.state = GameState(self.cfg)
        self.clock = Timekeeper(self.cfg)
        self.paused = False
        self.snapshot: dict = _build_snapshot(self.state, self.paused)
        self._restart_requested = False

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def request_restart(self) -> None:
        self._restart_requested = True

    def get_snapshot(self) -> dict:
        return self.snapshot  # reference swap is atomic under the GIL

    def run_forever(self) -> None:
        while True:
            dt = self.clock.step()

            if self._restart_requested:
                self.state = GameState(self.cfg)
                self._restart_requested = False
                self.paused = False

            if not self.paused and self.state.colony.queen.hp > 0:
                self.state.step(dt)

            self.snapshot = _build_snapshot(self.state, self.paused)


class Handler(BaseHTTPRequestHandler):
    server_version = "AnAntsLife/1.0"

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", (WEB_DIR / "index.html").read_bytes())
        elif self.path == "/app.js":
            self._send(200, "application/javascript; charset=utf-8", (WEB_DIR / "app.js").read_bytes())
        elif self.path == "/state":
            body = json.dumps(self.server.runner.get_snapshot()).encode("utf-8")
            self._send(200, "application/json", body)
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self) -> None:  # noqa: N802 (stdlib method name)
        if self.path != "/control":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            payload = {}

        runner = self.server.runner
        action = payload.get("action")
        if action == "pause_toggle":
            runner.toggle_pause()
        elif action == "restart":
            runner.request_restart()

        self._send(200, "application/json", b'{"ok": true}')

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # keep the console quiet; the HUD isn't used in web mode


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

    runner = SimRunner()
    threading.Thread(target=runner.run_forever, daemon=True).start()

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.runner = runner
    print(f"An Ant's Life running at http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
