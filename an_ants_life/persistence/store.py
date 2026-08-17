"""
Where saves live, and how they get written.

Two kinds of file. A save is a colony you can resume. The archive is the
shelf of colonies that have finished - their chapters, milestones and
how they ended - which is the point of persisting anything here: the
game's substance is the story a colony leaves, and a story that dies
with the process is not much of a record.

Writes go through a temporary file and a rename, because the autosave
fires while the simulation is running and a half-written save that
replaced a good one would be worse than no autosave at all.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from persistence.codec import dump_state, load_state

# Sits next to the package rather than inside it, so saves are not mixed
# in with source.
DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "saves"
ARCHIVE_NAME = "archive.json"
AUTOSAVE_NAME = "autosave.json"
ARCHIVE_LIMIT = 200


class SaveStore:
    def __init__(self, directory: Optional[Path] = None) -> None:
        self.dir = Path(directory) if directory else DEFAULT_DIR

    # ---------- plumbing ----------

    def _ensure_dir(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: Any) -> None:
        """Write via temp file + rename so a crash mid-write cannot leave
        a truncated file where a working one used to be."""
        self._ensure_dir()
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(path)

    def _read_json(self, path: Path) -> Optional[Any]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _safe_name(self, name: str) -> str:
        """Save names come from the client, so keep them to a basename."""
        cleaned = "".join(c for c in (name or "") if c.isalnum() or c in "-_ ").strip()
        return (cleaned or "save")[:60]

    # ---------- saves ----------

    def save_path(self, name: str) -> Path:
        return self.dir / f"{self._safe_name(name)}.json"

    def save(self, state, name: str = "autosave") -> Path:
        path = self.dir / AUTOSAVE_NAME if name == "autosave" else self.save_path(name)
        payload = dump_state(state)
        payload["saved_at"] = time.time()
        payload["label"] = name
        self._write_json(path, payload)
        return path

    def load(self, name: str = "autosave"):
        path = self.dir / AUTOSAVE_NAME if name == "autosave" else self.save_path(name)
        data = self._read_json(path)
        if data is None:
            return None
        return load_state(data)

    def list_saves(self) -> List[Dict[str, Any]]:
        if not self.dir.exists():
            return []
        out = []
        for path in sorted(self.dir.glob("*.json")):
            if path.name == ARCHIVE_NAME:
                continue
            data = self._read_json(path)
            if not isinstance(data, dict):
                continue
            out.append({
                "name": path.stem,
                "label": data.get("label", path.stem),
                "colony": data.get("colony_name"),
                "t": round(float(data.get("t", 0.0)), 1),
                "saved_at": data.get("saved_at"),
                "ending": data.get("ending"),
                "population": len(((data.get("colony") or {}).get("ants") or [])),
            })
        out.sort(key=lambda r: r.get("saved_at") or 0, reverse=True)
        return out

    def delete_save(self, name: str) -> bool:
        path = self.dir / AUTOSAVE_NAME if name == "autosave" else self.save_path(name)
        try:
            path.unlink()
            return True
        except (FileNotFoundError, OSError):
            return False

    # ---------- archive ----------

    def read_archive(self) -> List[Dict[str, Any]]:
        data = self._read_json(self.dir / ARCHIVE_NAME)
        return data if isinstance(data, list) else []

    def archive_colony(self, state) -> Dict[str, Any]:
        """Record a finished colony. Idempotent per run, so an ended game
        sitting on screen is not filed again on every autosave tick."""
        entries = self.read_archive()
        run_id = f"{state.colony_name}-{int(state.t)}"
        if any(e.get("id") == run_id for e in entries):
            return {}

        tracker = state.milestones
        chapters = [{"title": c.title, "started_t": round(c.started_t, 1),
                     "duration": round(c.duration, 1)} for c in tracker.past_chapters]
        if tracker.chapter.active:
            chapters.append({"title": tracker.chapter.title,
                             "started_t": round(tracker.chapter.started_t, 1),
                             "duration": round(state.t - tracker.chapter.started_t, 1)})

        ending_text = None
        for ev in reversed(state.history.saga):
            if ev.kind == "ending":
                ending_text = ev.data.get("text")
                break

        entry = {
            "id": run_id,
            "colony": state.colony_name,
            "ended_at": time.time(),
            "duration": round(state.t, 1),
            "ending": state.ending,
            "ending_text": ending_text,
            "final_population": len(state.colony.ants),
            "queen_hp": state.colony.queen.hp,
            "chapters": chapters,
            "milestones": [{"title": m["title"], "t": round(m["t"], 1)}
                           for m in tracker.milestones],
            "metrics": dict(state.colony.metrics),
        }
        entries.append(entry)
        self._write_json(self.dir / ARCHIVE_NAME, entries[-ARCHIVE_LIMIT:])
        return entry
