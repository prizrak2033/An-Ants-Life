"""
Terrain: biomes and obstacles.

Ground stops being interchangeable: sand burns trails off fast, leaf
litter is where food collects, rock is slow going, water cannot be
crossed at all.

Nothing here pathfinds - ants steer straight at their target - so the
map is built to stay navigable. Water is the only hard barrier and is
kept to small ponds; rock is cost terrain instead, which the colony
crosses slowly. That choice is load-bearing rather than cosmetic: with
rock impassable too, ~12% of the map was solid and measurement put
~42% of ants grinding against a face at any moment, because steering
agents with no path graph cannot get around a wall reliably. As cost
terrain it needs no pathfinding at all and the trail system handles
routing on its own, since a path over fast ground gets walked (and so
reinforced) more often than one over slow.

Generation still guarantees the rest: the nest keeps a clear apron,
and any pocket the colony cannot walk to is filled in rather than left
as a trap holding food nobody can reach.
"""
from __future__ import annotations
import math
import random
from collections import deque
from enum import Enum
from typing import List, Tuple


class Terrain(Enum):
    SOIL = "SOIL"      # default ground, no modifiers
    SAND = "SAND"      # slow going, trails evaporate fast
    LITTER = "LITTER"  # leaf litter: slightly slow, where food collects
    ROCK = "ROCK"      # rough scree: crossable, but slow
    WATER = "WATER"    # impassable


# Stable order, used for the compact wire encoding sent to the browser.
_ORDER = (Terrain.SOIL, Terrain.SAND, Terrain.LITTER, Terrain.ROCK, Terrain.WATER)
_CODE = {t: str(i) for i, t in enumerate(_ORDER)}

# Only water truly blocks. Rock is rough going the colony can cross
# slowly: hard walls need pathfinding nothing here has, and measured at
# ~12% coverage they left ~42% of ants grinding against faces. As cost
# terrain the trail system routes around it on its own, because a path
# over fast ground gets reinforced more often than one over slow.
IMPASSABLE = (Terrain.WATER,)


class TerrainMap:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cell = cfg.TERRAIN_CELL
        self.cols = max(1, int(cfg.WORLD_W // self.cell) + 1)
        self.rows = max(1, int(cfg.WORLD_H // self.cell) + 1)

        self.tiles: List[List[Terrain]] = [
            [Terrain.SOIL] * self.rows for _ in range(self.cols)
        ]

        if cfg.TERRAIN_ENABLE:
            self._generate()
            self._clear_nest_apron()
            self._seal_unreachable_pockets()

        self._build_lookups()

    # ---------- generation ----------

    def _generate(self) -> None:
        cfg = self.cfg
        plan = (
            (Terrain.ROCK, cfg.TERRAIN_ROCK_BLOBS),
            (Terrain.WATER, cfg.TERRAIN_WATER_BLOBS),
            (Terrain.SAND, cfg.TERRAIN_SAND_BLOBS),
            (Terrain.LITTER, cfg.TERRAIN_LITTER_BLOBS),
        )
        for kind, count in plan:
            for _ in range(count):
                self._blob(kind)

    def _blob(self, kind: Terrain) -> None:
        cfg = self.cfg
        cx = random.uniform(0, cfg.WORLD_W)
        cy = random.uniform(0, cfg.WORLD_H)
        max_r = cfg.TERRAIN_WATER_MAX_R if kind is Terrain.WATER else cfg.TERRAIN_BLOB_MAX_R
        r = random.uniform(cfg.TERRAIN_BLOB_MIN_R, max_r)

        gx0, gy0 = self._cell_of(cx - r, cy - r)
        gx1, gy1 = self._cell_of(cx + r, cy + r)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                wx, wy = (gx + 0.5) * self.cell, (gy + 0.5) * self.cell
                # Ragged edge so blobs don't read as circles.
                if math.hypot(wx - cx, wy - cy) <= r * random.uniform(0.7, 1.15):
                    self.tiles[gx][gy] = kind

    def _clear_nest_apron(self) -> None:
        """The colony always gets open ground to live and forage on."""
        cfg = self.cfg
        r = cfg.TERRAIN_NEST_CLEAR_RADIUS
        gx0, gy0 = self._cell_of(cfg.NEST_X - r, cfg.NEST_Y - r)
        gx1, gy1 = self._cell_of(cfg.NEST_X + r, cfg.NEST_Y + r)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                wx, wy = (gx + 0.5) * self.cell, (gy + 0.5) * self.cell
                if math.hypot(wx - cfg.NEST_X, wy - cfg.NEST_Y) <= r:
                    self.tiles[gx][gy] = Terrain.SOIL

    def _seal_unreachable_pockets(self) -> None:
        """Fill any open ground the colony cannot actually walk to.

        Left alone, a sealed pocket still spawns food and still reads as
        open on screen, so foragers would stream toward a pile they can
        never reach. Filling it in keeps every passable tile connected.
        """
        start = self._cell_of(self.cfg.NEST_X, self.cfg.NEST_Y)
        seen = [[False] * self.rows for _ in range(self.cols)]
        q = deque([start])
        seen[start[0]][start[1]] = True
        while q:
            gx, gy = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = gx + dx, gy + dy
                if not (0 <= nx < self.cols and 0 <= ny < self.rows):
                    continue
                if seen[nx][ny] or self.tiles[nx][ny] in IMPASSABLE:
                    continue
                seen[nx][ny] = True
                q.append((nx, ny))

        for gx in range(self.cols):
            for gy in range(self.rows):
                if not seen[gx][gy] and self.tiles[gx][gy] not in IMPASSABLE:
                    self.tiles[gx][gy] = Terrain.WATER

    def _build_lookups(self) -> None:
        cfg = self.cfg
        speed = {
            Terrain.SOIL: 1.0,
            Terrain.SAND: cfg.SAND_SPEED_MULT,
            Terrain.LITTER: cfg.LITTER_SPEED_MULT,
            Terrain.ROCK: cfg.ROCK_SPEED_MULT,
            Terrain.WATER: 1.0,
        }
        decay = {
            Terrain.SOIL: 1.0,
            Terrain.SAND: cfg.SAND_PHERO_DECAY_MULT,
            Terrain.LITTER: cfg.LITTER_PHERO_DECAY_MULT,
            Terrain.ROCK: 1.0,
            Terrain.WATER: 1.0,
        }
        self._passable = [
            [self.tiles[gx][gy] not in IMPASSABLE for gy in range(self.rows)]
            for gx in range(self.cols)
        ]
        self._speed = [
            [speed[self.tiles[gx][gy]] for gy in range(self.rows)]
            for gx in range(self.cols)
        ]
        self._decay = [
            [decay[self.tiles[gx][gy]] for gy in range(self.rows)]
            for gx in range(self.cols)
        ]

    # ---------- queries ----------

    def _cell_of(self, x: float, y: float) -> Tuple[int, int]:
        gx = min(self.cols - 1, max(0, int(x // self.cell)))
        gy = min(self.rows - 1, max(0, int(y // self.cell)))
        return gx, gy

    def at(self, x: float, y: float) -> Terrain:
        gx, gy = self._cell_of(x, y)
        return self.tiles[gx][gy]

    def passable(self, x: float, y: float) -> bool:
        gx, gy = self._cell_of(x, y)
        return self._passable[gx][gy]

    def speed_mult(self, x: float, y: float) -> float:
        gx, gy = self._cell_of(x, y)
        return self._speed[gx][gy]

    def decay_mult(self, x: float, y: float) -> float:
        gx, gy = self._cell_of(x, y)
        return self._decay[gx][gy]

    def move(self, x: float, y: float, nx: float, ny: float):
        """Attempt a move. Returns ((x, y), blocked).

        `blocked` means axis-sliding could not salvage any progress -
        which is the head-on case, where the mover is aimed square at a
        face and has no tangential component to slide on. Callers answer
        that by deflecting; sliding alone leaves them vibrating in place.
        """
        if self._passable_fast(nx, ny):
            return (nx, ny), False

        # An axis slide can "succeed" while going essentially nowhere: aimed
        # square at a vertical face, the surviving axis is the one that was
        # already ~zero. Judge on distance actually covered, or a head-on
        # hit reports success and never triggers a deflection.
        want = math.hypot(nx - x, ny - y)
        floor = want * 0.35
        if self._passable_fast(nx, y):
            return (nx, y), abs(nx - x) < floor
        if self._passable_fast(x, ny):
            return (x, ny), abs(ny - y) < floor
        return (x, y), True

    def deflect(self, x: float, y: float, vx: float, vy: float, dt: float,
                prefer: int = 1):
        """Find a heading that clears the obstruction.

        `prefer` is the side (+1/-1) the mover already committed to for
        this encounter, and it is tried at every turn magnitude before the
        other side. Sticking to one side is what makes an obstacle get
        walked around: choosing afresh each time, a mover peels left off
        one face and right off the next and just rocks in the corner.

        Looks several ticks ahead so it commits to genuinely open ground
        rather than to the next tile happening to be free. Returns
        (vx, vy, side) or None when boxed in.
        """
        speed = math.hypot(vx, vy)
        if speed < 1e-6:
            return None
        base = math.atan2(vy, vx)
        look = max(speed * dt * 8.0, self.cell * 3.0)
        for mag in (0.6, 1.1, 1.6, 2.2, 2.8):
            for side in (prefer, -prefer):
                h = base + side * mag
                cx, sy = math.cos(h), math.sin(h)
                if self._passable_fast(x + cx * look, y + sy * look):
                    return cx * speed, sy * speed, side
        return None

    def _passable_fast(self, x: float, y: float) -> bool:
        gx = int(x // self.cell)
        gy = int(y // self.cell)
        if gx < 0 or gy < 0 or gx >= self.cols or gy >= self.rows:
            return False
        return self._passable[gx][gy]

    def code_string(self) -> str:
        """Compact column-major encoding for the browser."""
        return "".join(
            _CODE[self.tiles[gx][gy]]
            for gx in range(self.cols)
            for gy in range(self.rows)
        )
