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
import math
import sys
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Deque, Optional

from config import SimConfig
from state import GameState
from systems.time import Timekeeper
from enemies.kinds import EnemyKind
from ants.roles import Role
from colony.history import EventKind
from colony.narrator import chronicle_lines
from colony.directives import DirectiveKind
from persistence.store import SaveStore

WEB_DIR = Path(__file__).parent / "web"
DEFAULT_PORT = 8765


def _ending_text(state: GameState) -> Optional[str]:
    if state.ending is None:
        return None
    for ev in reversed(state.history.saga):
        if ev.kind == EventKind.ENDING:
            return ev.data.get("text")
    return None


def _garrison(state: GameState) -> dict:
    """Soldiers actually holding the nest.

    Worth its own readout: every colony death measured, played or
    passive, is the queen killed with this at zero. Nothing else in the
    interface showed the number that decides the game.
    """
    nest_x, nest_y = state.nest_pos
    radius_sq = 22.0 * 22.0
    total = home = 0
    for a in state.colony.ants:
        if a.role not in (Role.SOLDIER, Role.PRAETORIAN):
            continue
        total += 1
        dx, dy = a.x - nest_x, a.y - nest_y
        if dx * dx + dy * dy <= radius_sq:
            home += 1
    return {"home": home, "total": total,
            "floor": state.cfg.DIRECTIVE_DEFEND_MIN_GARRISON}


def _heading(mover) -> float:
    """Facing, in radians. Zero when standing still, which reads as
    "unchanged" rather than snapping east."""
    if not mover.vx and not mover.vy:
        return 0.0
    return round(math.atan2(mover.vy, mover.vx), 3)


def _count_kinds(enemies) -> dict:
    counts = {k.value: 0 for k in EnemyKind}
    for e in enemies:
        counts[e.kind.value] += 1
    return counts


def _audio_config(cfg: SimConfig) -> dict:
    """The browser's mix, published from the same config as the sim.

    Keys are lowercased without the AUDIO_ prefix, so AUDIO_DRONE_BASE
    arrives as levels.drone_base. The page carries matching defaults and
    merges these over them, so an older page and a newer server disagree
    only about the values they share.
    """
    levels = {
        name[len("AUDIO_"):].lower(): getattr(cfg, name)
        for name in vars(SimConfig)["__annotations__"]
        if name.startswith("AUDIO_") and name != "AUDIO_EVENT_VOICES"
    }
    events = {
        kind: [voice, freq, dur, gain]
        for kind, voice, freq, dur, gain in cfg.AUDIO_EVENT_VOICES
    }
    return {"levels": levels, "events": events}


# ---------- player actions ----------
#
# These live at module level, not on the runner, so that anything driving
# the game drives it the same way. A scripted player that reached into
# GameState directly would be measuring an oracle rather than a player:
# it could do things no one holding the interface can do, and any result
# about how much play matters would be worth nothing.

def _place(state: GameState, cfg: SimConfig, cmd: dict) -> bool:
    kind = DirectiveKind(str(cmd["kind"]).upper())
    x = min(max(0.0, float(cmd["x"])), float(cfg.WORLD_W))
    y = min(max(0.0, float(cmd["y"])), float(cfg.WORLD_H))
    state.directives.place(kind, x, y, state.t)
    state.history.emit(
        state.t, state.tick, EventKind.DIRECTIVE_PLACED,
        {"kind": kind.value, "x": round(x, 1), "y": round(y, 1)},
        cause="player_order", tags=["directive"]
    )
    return True


def _set_policy(state: GameState, cfg: SimConfig, cmd: dict) -> bool:
    scout = cmd.get("scout")
    soldier = cmd.get("soldier")
    state.policy.set_targets(
        cfg,
        None if scout is None else float(scout),
        None if soldier is None else float(soldier),
    )
    if cmd.get("auto_defense") is not None:
        state.policy.auto_defense = bool(cmd["auto_defense"])
    if cmd.get("praetorian") is not None:
        state.policy.set_praetorian_target(cfg, int(cmd["praetorian"]))
    state.history.emit(
        state.t, state.tick, EventKind.POLICY_CHANGED,
        {"text": (f"Standing orders change: {state.policy.soldier_target:.0%} soldiers, "
                  f"{state.policy.scout_target:.0%} scouts, "
                  f"{state.policy.praetorian_target} praetorians."),
         "scout": state.policy.scout_target,
         "soldier": state.policy.soldier_target,
         "auto_defense": state.policy.auto_defense},
        cause="player_order", tags=["policy"]
    )
    return True


def _set_rally(state: GameState, cfg: SimConfig, on: bool) -> bool:
    if state.policy.rally == on:
        return False
    state.policy.rally = on
    state.history.emit(
        state.t, state.tick,
        EventKind.RALLY_CALLED if on else EventKind.RALLY_ENDED,
        {}, cause="player_order", tags=["rally"]
    )
    return True


WORK_COSTS = {"nursery": "BUILD_NURSERY_COST", "garden": "BUILD_GARDEN_COST"}


def work_cost(cfg: SimConfig, work: str) -> Optional[float]:
    attr = WORK_COSTS.get(work)
    return None if attr is None else float(getattr(cfg, attr))


def _build(state: GameState, cfg: SimConfig, cmd: dict) -> bool:
    """Spend food on something permanent. True if it was actually built.

    Refused rather than queued when it cannot be afforded: a work is a
    decision about what to do with food the colony has now, and letting
    it sit pending would quietly commit every future delivery to it.
    A refusal has to be visible to the caller, or a player cannot tell
    a spent 55 food from an ignored click.
    """
    work = str(cmd.get("work", "")).lower()
    cost = work_cost(cfg, work)
    if not cfg.BUILD_ENABLE or cost is None:
        return False
    if work in state.colony.works or state.colony.food_store < cost:
        return False

    state.colony.food_store -= cost
    state.colony.works.append(work)
    state.history.emit(
        state.t, state.tick, EventKind.WORK_BUILT,
        {"work": work, "cost": round(cost, 1)},
        cause="player_order", impact={"food_spent": cost}, tags=["works"]
    )
    return True


PLAYER_ACTIONS = frozenset({
    "place_directive", "remove_directive", "clear_directives",
    "set_policy", "set_rally", "build",
})


def apply_player_action(state: GameState, cfg: SimConfig, cmd: dict) -> bool:
    """Apply one in-world command. True if it changed the world.

    This is the complete set of things a player can do to the colony.
    Pausing, saving and restarting act on the runner rather than the
    world and stay with it.

    False covers two different things, and the caller usually wants to
    know which: a command that is not a move at all, and a legal move
    the colony declined (a work it cannot afford, a rally already
    called). `PLAYER_ACTIONS` separates them -- membership is legality,
    the return value is effect.
    """
    action = cmd.get("action")
    if action == "place_directive":
        return _place(state, cfg, cmd)
    if action == "remove_directive":
        return state.directives.remove(int(cmd["id"]))
    if action == "clear_directives":
        return state.directives.clear() > 0
    if action == "set_policy":
        return _set_policy(state, cfg, cmd)
    if action == "set_rally":
        return _set_rally(state, cfg, bool(cmd.get("on")))
    if action == "build":
        return _build(state, cfg, cmd)
    return False


def _assault_view(state: GameState) -> Optional[dict]:
    """The war band, if one is gathering or on its way.

    This is the game's only actionable warning. Everything else arrives
    faster than an order can be given: a lone warrior crosses from the
    border and is dead or at the queen inside two seconds. A band holds
    at the edge first, which is the only reason recall can be the right
    answer to anything.
    """
    t = state.t
    mustering = [e for e in state.enemies if e.band and e.muster_until_t > t]
    if mustering:
        return {
            "phase": "mustering",
            "size": len(mustering),
            "seconds": round(max(e.muster_until_t for e in mustering) - t, 1),
            "x": round(sum(e.x for e in mustering) / len(mustering), 1),
            "y": round(sum(e.y for e in mustering) / len(mustering), 1),
        }
    inbound = [e for e in state.enemies if e.band and e.muster_until_t <= 0.0]
    if inbound:
        return {
            "phase": "advancing",
            "size": len(inbound),
            "seconds": 0.0,
            "x": round(sum(e.x for e in inbound) / len(inbound), 1),
            "y": round(sum(e.y for e in inbound) / len(inbound), 1),
        }
    return None


SPEEDS = (1, 2, 4)


def _clamp_speed(value) -> int:
    """Nearest allowed speed, or 1 for anything unusable. The UI only
    offers three, but the endpoint is open to anyone with curl."""
    try:
        want = int(value)
    except (TypeError, ValueError):
        return 1
    return min(SPEEDS, key=lambda s: abs(s - want))


def _build_snapshot(state: GameState, paused: bool, save_note: Optional[str] = None,
                    speed: int = 1) -> dict:
    cfg = state.cfg
    colony = state.colony
    chapter = state.milestones.chapter
    territory = state.territory
    phero = state.pheromones

    return {
        "tick": state.tick,
        "t": round(state.t, 2),
        "paused": paused,
        "speed": speed,
        "game_over": state.ending is not None,
        "world": {"w": cfg.WORLD_W, "h": cfg.WORLD_H},
        # Static for the life of a map; sent as a compact digit string
        # (column-major) rather than an array of ints.
        "terrain": {
            "cell": cfg.TERRAIN_CELL,
            "cols": state.terrain.cols,
            "rows": state.terrain.rows,
            "tiles": state.terrain.code_string(),
        },
        "nest": [state.nest_pos[0], state.nest_pos[1]],
        "queen": {"hp": colony.queen.hp, "hp_max": colony.queen.hp_max},
        "colony": {
            "food_store": round(colony.food_store, 2),
            "stress": round(colony.stress, 3),
            "hunger": round(colony.emergency.get("hunger", 0.0), 3),
            "famine": bool(colony.emergency.get("famine_active", False)),
            "pressure": round(colony.emergency.get("territory_pressure", 0.0), 3),
            "population": len(colony.ants),
            "income_per_sec": round(colony.emergency.get("income_per_sec", 0.0), 3),
            "upkeep_per_sec": round(colony.emergency.get("upkeep_per_sec", 0.0), 3),
            "food_balance": round(colony.emergency.get("food_balance", 0.0), 3),
            "carrying_capacity": round(colony.emergency.get("carrying_capacity", 0.0), 1),
        },
        "garrison": _garrison(state),
        "assault": _assault_view(state),
        "works": {
            "built": list(colony.works),
            "costs": {w: work_cost(cfg, w) for w in WORK_COSTS},
        },
        "enemy_counts": _count_kinds(state.enemies),
        "metrics": dict(colony.metrics),
        # Ants/enemies/food are packed as flat arrays (not objects) to keep
        # the payload small at ~10 snapshots/sec.
        #
        # The heading is there so the view can draw something facing the way
        # it is going. Derived here rather than in the browser because the
        # array carries no ids: entries shift as ants are born and die, so
        # a client differencing positions between polls would be reading
        # one ant's movement off another's.
        # [x, y, role, carrying, heading]
        "ants": [
            [a.x, a.y, a.role.value, 1 if a.carrying > 0 else 0, _heading(a)]
            for a in colony.ants
        ],
        # [x, y, kind, carrying_loot, heading]
        "enemies": [
            [e.x, e.y, e.kind.value, 1 if e.carrying > 0 else 0, _heading(e)]
            for e in state.enemies
        ],
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
        "chapter": {
            "active": chapter.active,
            "title": chapter.title if chapter.active else None,
            "started_t": round(chapter.started_t, 1) if chapter.active else None,
        },
        # Narrated, and filtered to events that carry the story - a plain
        # tail of the log is ~82% routine foraging and combat churn.
        # `kind` rides along for the audio layer, which picks a sound from
        # it and reuses the same significance filter the text does.
        "chronicle": [
            {"t": round(l["t"], 1), "kind": l["kind"], "text": l["text"],
             "major": l["major"], "repeat": l["repeat"]}
            for l in chronicle_lines(state.history, 14)
        ],
        "saga": {
            "chapters": [
                {"title": c.title, "started_t": round(c.started_t, 1),
                 "duration": round(c.duration, 1)}
                for c in state.milestones.past_chapters
            ],
            "milestones": [
                {"title": m["title"], "text": m["text"], "t": round(m["t"], 1)}
                for m in state.milestones.milestones
            ],
        },
        "directives": [
            {"id": d.id, "kind": d.kind.value, "x": round(d.x, 2), "y": round(d.y, 2),
             "strength": round(d.strength, 3), "recruits": d.recruits,
             "cap": cfg.DIRECTIVE_RECRUIT_CAP if d.kind is DirectiveKind.FORAGE else None}
            for d in state.directives.items
        ],
        "policy": {
            "scout_target": round(state.policy.scout_target, 3),
            "soldier_target": round(state.policy.soldier_target, 3),
            "auto_defense": state.policy.auto_defense,
            "rally": state.policy.rally,
            "effective_soldier_target": round(
                state.policy.effective_soldier_target(
                    cfg, colony.emergency.get("territory_pressure", 0.0)), 3),
            "max_scout": cfg.POLICY_MAX_SCOUT_FRAC,
            "max_soldier": cfg.POLICY_MAX_SOLDIER_FRAC,
            "max_per_kind": cfg.DIRECTIVE_MAX_PER_KIND,
            "defend_share": cfg.DIRECTIVE_DEFEND_MAX_SHARE,
            "praetorian_target": state.policy.praetorian_target,
            "max_praetorian": cfg.PRAETORIAN_MAX,
        },
        "ending": state.ending,
        "ending_text": _ending_text(state),
        "colony_name": state.colony_name,
        "save_note": save_note,
    }


class SimRunner:
    """Owns the simulation thread and the latest served snapshot.

    Player input arrives on HTTP threads while the simulation runs on its
    own, so commands are queued rather than applied where they land -
    mutating directives or policy mid-tick would race the systems reading
    them. The queue is drained at a tick boundary, which also means an
    action either lands wholly within one tick or not at all.
    """

    def __init__(self) -> None:
        self.cfg = SimConfig()
        self.state = GameState(self.cfg)
        self.clock = Timekeeper(self.cfg)
        self.paused = False
        self.speed = 1
        self.snapshot: dict = _build_snapshot(self.state, self.paused)
        # deque.append / popleft are atomic under the GIL, so no lock.
        self._commands: Deque[dict] = deque()
        self.store = SaveStore()
        self._next_autosave_t = self.cfg.AUTOSAVE_EVERY_SECONDS
        self._archived_run = False
        self.last_save_note: Optional[str] = None

    def submit(self, cmd: dict) -> None:
        """Called from HTTP threads; never touches simulation state."""
        self._commands.append(cmd)

    def get_snapshot(self) -> dict:
        return self.snapshot  # reference swap is atomic under the GIL

    def _drain(self) -> None:
        while True:
            try:
                cmd = self._commands.popleft()
            except IndexError:
                return
            try:
                self._apply(cmd)
            except (KeyError, TypeError, ValueError):
                # A malformed request must never take the sim thread down.
                continue

    def _apply(self, cmd: dict) -> None:
        action = cmd.get("action")
        state = self.state
        cfg = self.cfg

        if action == "pause_toggle":
            self.paused = not self.paused
        elif action == "set_speed":
            # Runner control, like pause - it changes how fast the world
            # is watched, not anything in it, so it does not belong with
            # the player actions.
            self.speed = _clamp_speed(cmd.get("speed"))
        elif action == "restart":
            self._archive_if_finished()
            self.state = GameState(cfg)
            self.paused = False
            self._reset_save_cycle()
        elif action == "save":
            name = str(cmd.get("name") or "autosave")
            self.store.save(state, name)
            self.last_save_note = f"Saved as “{name}”."
        elif action == "load":
            self._load(str(cmd.get("name") or "autosave"))
        elif action == "delete_save":
            self.store.delete_save(str(cmd.get("name") or ""))
        else:
            # Everything that acts on the world rather than on the runner.
            apply_player_action(state, cfg, cmd)

    def _reset_save_cycle(self) -> None:
        self._next_autosave_t = self.state.t + self.cfg.AUTOSAVE_EVERY_SECONDS
        self._archived_run = False

    def _load(self, name: str) -> None:
        try:
            loaded = self.store.load(name)
        except (ValueError, KeyError, TypeError):
            self.last_save_note = "That save could not be read."
            return
        if loaded is None:
            self.last_save_note = "No such save."
            return
        self.state = loaded
        self.paused = False
        # Leave the archive flag clear even for a finished colony: it may
        # have been saved after ending but before it was ever filed.
        # archive_colony dedups by run, so filing twice is harmless while
        # never filing at all would silently lose the record.
        self._reset_save_cycle()
        self.last_save_note = f"Resumed “{name}”."

    def _archive_if_finished(self) -> None:
        """File a finished colony on the shelf, once."""
        if self._archived_run or self.state.ending is None:
            return
        self._archived_run = True
        try:
            self.store.archive_colony(self.state)
        except OSError:
            pass  # a failed archive write must not stop the game

    def run_forever(self) -> None:
        while True:
            dt = self.clock.step()
            self._drain()

            if not self.paused and self.state.ending is None:
                # Faster means more ticks per frame, not a bigger dt.
                # Every rate in this simulation was converted to per-second
                # and is clamped at MAX_DT, so scaling dt would either be
                # silently clipped or would change the physics - a 4x dt is
                # a different game, four steps is the same game sooner.
                for _ in range(self.speed):
                    self.state.step(dt)
                    if self.state.ending is not None:
                        break

            if self.state.ending is not None:
                self._archive_if_finished()
            elif self.cfg.AUTOSAVE_ENABLE and self.state.t >= self._next_autosave_t:
                self._next_autosave_t = self.state.t + self.cfg.AUTOSAVE_EVERY_SECONDS
                try:
                    self.store.save(self.state, "autosave")
                except OSError:
                    pass  # keep playing even if the disk is unhappy

            self.snapshot = _build_snapshot(self.state, self.paused,
                                            self.last_save_note, self.speed)


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
        elif self.path == "/audio.js":
            self._send(200, "application/javascript; charset=utf-8", (WEB_DIR / "audio.js").read_bytes())
        elif self.path == "/audio-config":
            # Its own route rather than a block on /state: the mix is
            # fixed for the session and /state is polled several times a
            # second, so this is fetched once at load.
            self._send(200, "application/json",
                       json.dumps(_audio_config(self.server.runner.cfg)).encode("utf-8"))
        elif self.path == "/state":
            body = json.dumps(self.server.runner.get_snapshot()).encode("utf-8")
            self._send(200, "application/json", body)
        elif self.path == "/saves":
            # Reads are safe against the sim thread's writes: saves are
            # written to a temp file and renamed, so a reader sees either
            # the old file or the new one, never a partial one.
            body = json.dumps(self.server.runner.store.list_saves()).encode("utf-8")
            self._send(200, "application/json", body)
        elif self.path == "/archive":
            body = json.dumps(self.server.runner.store.read_archive()).encode("utf-8")
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

        if isinstance(payload, dict) and payload.get("action"):
            self.server.runner.submit(payload)

        self._send(200, "application/json", b'{"ok": true}')

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # keep the console quiet; the HUD isn't used in web mode


def parse_port(argv) -> int:
    """The port, however it was asked for.

    `python3 -m server 8731` was the only accepted form and anything else
    died on int(). `--port 8731` is what most people type first, and a
    traceback is a poor greeting for someone opening the game for the
    first time - so both work, and a bad one says so in a sentence rather
    than a stack trace.
    """
    args = list(argv)
    if args and args[0] in ("-p", "--port"):
        args = args[1:]
        if not args:
            raise SystemExit("--port needs a number, e.g. --port 8731")
    elif args and args[0].startswith("--port="):
        args = [args[0].split("=", 1)[1]]
    elif args and args[0] in ("-h", "--help"):
        raise SystemExit("usage: python3 -m server [PORT | --port PORT]")

    if not args:
        return DEFAULT_PORT
    try:
        port = int(args[0])
    except ValueError:
        raise SystemExit(f"{args[0]!r} is not a port number. "
                         f"Try: python3 -m server {DEFAULT_PORT}")
    if not (1 <= port <= 65535):
        raise SystemExit(f"{port} is not a usable port (1-65535).")
    return port


def main() -> None:
    port = parse_port(sys.argv[1:])

    runner = SimRunner()
    threading.Thread(target=runner.run_forever, daemon=True).start()

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as err:
        raise SystemExit(f"Could not open port {port}: {err}. "
                         f"Something else may already be using it - "
                         f"try another, e.g. python3 -m server {port + 1}.")
    httpd.runner = runner
    print(f"An Ant's Life running at http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
