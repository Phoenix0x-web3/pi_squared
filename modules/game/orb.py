from __future__ import annotations
import math
import sys
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

ANSI = {
    "reset":"\x1b[0m","ring":"\x1b[38;5;129m",
    "yellow":"\x1b[38;5;220m","green":"\x1b[38;5;46m",
    "red":"\x1b[38;5;196m","blue":"\x1b[38;5;39m",
    "orange":"\x1b[38;5;208m","mag":"\x1b[35m",
    "gray":"\x1b[38;5;244m","white":"\x1b[97m",
}

@dataclass
class ReactorGeometry:
    container_px: int = 256        # 256 (w-64) or 288 (md:w-72)
    orbit_radius_px: int = 80      # translateX(80px)
    orb_size_px: int = 56          # 56px => hit r = 28
    rotation_period_s: float = 40.0
    @property
    def arena_radius_px(self) -> float: return self.container_px * 0.46
    @property
    def orb_hit_r_px(self) -> int: return self.orb_size_px // 2
    @property
    def omega_deg_per_sec(self) -> float: return 360.0 / self.rotation_period_s  # 9°/s

class FrontAccurateOrbArena:
    def __init__(
        self, *,
        cx:int, cy:int,
        geom:ReactorGeometry,
        grid_w:int=61, grid_h:int=33,
        cell_aspect_y_over_x: float = 2.0,
        clear_screen:bool=True,
        colors: Optional[List[str]] = None,
        randomize_order: bool = True,
        random_phase: bool = True,
    ):
        self.cx, self.cy = int(cx), int(cy)
        self.g = geom
        self.w, self.h = int(grid_w), int(grid_h)
        self.cx_col, self.cy_row = self.w//2, self.h//2
        self.aspect = float(cell_aspect_y_over_x)
        self.clear = clear_screen
        self.t0 = time.time()

        base_palette = colors[:] if colors else ["yellow","green","red","blue","orange"]
        if randomize_order:
            random.shuffle(base_palette)
        self.colors = base_palette

        self.phase0_deg = random.uniform(0.0, 360.0) if random_phase else 0.0

        self._last_click: Optional[Tuple[int,int]] = None
        self._last_hit: Optional[str] = None
        self.stats: Dict[str,int] = {c:0 for c in self.colors} | {"MISS":0,"OUT":0}
        self.header_note = ""

    def _theta(self, index:int) -> float:
        dt = time.time() - self.t0
        return (self.g.omega_deg_per_sec * dt + self.phase0_deg + (72.0*index - 90.0)) % 360.0

    def color_center_now(self, color:str) -> Tuple[int,int]:
        idx = self.colors.index(color)
        ang = math.radians(self._theta(idx))
        return (int(round(self.cx + self.g.orbit_radius_px * math.cos(ang))),
                int(round(self.cy + self.g.orbit_radius_px * math.sin(ang))))

    @staticmethod
    def _dist2(x1:int,y1:int,x2:int,y2:int)->int:
        dx, dy = x1-x2, y1-y2
        return dx*dx + dy*dy

    def detect_color(self, x:int, y:int) -> str:
        R2 = self.g.arena_radius_px * self.g.arena_radius_px
        if self._dist2(x,y,self.cx,self.cy) > R2: return "OUT"
        r2 = self.g.orb_hit_r_px * self.g.orb_hit_r_px
        for c in self.colors:
            ox, oy = self.color_center_now(c)
            if self._dist2(x,y,ox,oy) <= r2: return c
        return "MISS"

    def _px_to_cell(self, x:int, y:int) -> Tuple[int,int]:
        R = self.g.arena_radius_px
        nx = (x - self.cx) / R
        ny = (y - self.cy) / R
        col = int(round(self.cx_col + max(-1.0, min(1.0, nx)) * (self.w//2)))
        row = int(round(self.cy_row + max(-1.0, min(1.0, ny)) * (self.h//2) / self.aspect))
        return max(0, min(self.h-1,row)), max(0, min(self.w-1,col))

    def _ring_mask(self, rr:int, cc:int) -> bool:
        nx = (cc - self.cx_col) / (self.w//2)
        ny = (rr - self.cy_row) / (self.h//2) * self.aspect
        d = math.hypot(nx, ny)
        return abs(d - 1.0) < 0.03

    def render(self, *, target_color:str, ms_left:int):
        buf: List[List[str]] = [[" " for _ in range(self.w)] for _ in range(self.h)]
        for rr in range(self.h):
            for cc in range(self.w):
                if self._ring_mask(rr, cc):
                    buf[rr][cc] = f"{ANSI['ring']}·{ANSI['reset']}"
        r_cells_x = max(1, int(round(self.g.orb_hit_r_px / self.g.arena_radius_px * (self.w//2))))
        r_cells_y = max(1, int(round(self.g.orb_hit_r_px / self.g.arena_radius_px * (self.h//2) / self.aspect)))
        for c in self.colors:
            ox, oy = self.color_center_now(c)
            orow, ocol = self._px_to_cell(ox, oy)
            col = ANSI.get(c, ANSI["white"])
            for dr in range(-r_cells_y, r_cells_y+1):
                rr = orow + dr
                if not (0 <= rr < self.h): continue
                for dc in range(-r_cells_x, r_cells_x+1):
                    cc = ocol + dc
                    if not (0 <= cc < self.w): continue
                    if (dc*dc + (dr*self.aspect)*(dr*self.aspect)) <= (r_cells_x*r_cells_x):
                        buf[rr][cc] = f"{col}●{ANSI['reset']}"
        buf[self.cy_row][self.cx_col] = f"{ANSI['mag']}◉{ANSI['reset']}"

        if self._last_click:
            rr, cc = self._px_to_cell(*self._last_click)
            hit = self._last_hit or "MISS"
            col = ANSI.get(hit, ANSI["gray"])
            buf[rr][cc] = f"{col}{('X' if hit not in ('MISS','OUT') else 'x')}{ANSI['reset']}"

        if self.clear:
            sys.stdout.write("\x1b[2J\x1b[H")
        for row in buf:
            sys.stdout.write("".join(row) + "\n")
        sys.stdout.flush()

    def add_click(self, x:int, y:int, *, target_color:str, ms_left:int) -> str:
        self._last_click = (x, y)
        hit = self.detect_color(x, y)
        self._last_hit = hit
        self.stats[hit] = self.stats.get(hit, 0) + 1
        self.render(target_color=target_color, ms_left=ms_left)
        return hit


class StaticArenaOverlay:
    def __init__(self, arena: FrontAccurateOrbArena):
        self.arena = arena
        self._bg_grid: Optional[List[List[str]]] = None
        self._grid_top_row = 0
        self._last_cell: Optional[Tuple[int, int]] = None

    def _goto_cell(self, row: int, col: int):
        term_row = self._grid_top_row + row + 1
        term_col = col + 1
        sys.stdout.write(f"\x1b[{term_row};{term_col}H")

    def draw_static(self, *, target_color: str, ms_left: int):
        buf: List[List[str]] = [[" " for _ in range(self.arena.w)] for _ in range(self.arena.h)]
        for rr in range(self.arena.h):
            for cc in range(self.arena.w):
                if self.arena._ring_mask(rr, cc):
                    buf[rr][cc] = f"{ANSI['ring']}·{ANSI['reset']}"
        r_cells_x = max(1, int(round(self.arena.g.orb_hit_r_px / self.arena.g.arena_radius_px * (self.arena.w // 2))))
        r_cells_y = max(1, int(round(self.arena.g.orb_hit_r_px / self.arena.g.arena_radius_px * (self.arena.h // 2) / self.arena.aspect)))
        for c in self.arena.colors:
            ox, oy = self.arena.color_center_now(c)
            orow, ocol = self.arena._px_to_cell(ox, oy)
            col = ANSI.get(c, ANSI["white"])
            for dr in range(-r_cells_y, r_cells_y + 1):
                rr = orow + dr
                if not (0 <= rr < self.arena.h): continue
                for dc in range(-r_cells_x, r_cells_x + 1):
                    cc = ocol + dc
                    if not (0 <= cc < self.arena.w): continue
                    if (dc * dc + (dr * self.arena.aspect) * (dr * self.arena.aspect)) <= (r_cells_x * r_cells_x):
                        buf[rr][cc] = f"{col}●{ANSI['reset']}"
        buf[self.arena.cy_row][self.arena.cx_col] = f"{ANSI['mag']}◉{ANSI['reset']}"

        if self.arena.clear:
            sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write("\n\n")
        for rr in range(self.arena.h):
            sys.stdout.write("".join(buf[rr]) + "\n")
        sys.stdout.flush()

        self._bg_grid = buf
        self._grid_top_row = 2

    def update_header(self, *, header_line: str, stats_line: str):
        sys.stdout.write("\x1b[1;1H\x1b[2K" + header_line + "\n")
        sys.stdout.write("\x1b[2;1H\x1b[2K" + stats_line + "\n")
        sys.stdout.flush()

    def update_click(self, x: int, y: int, *, color: str):
        assert self._bg_grid is not None, "call draw_static() first"
        row, col = self.arena._px_to_cell(x, y)
        if self._last_cell is not None:
            pr, pc = self._last_cell
            self._goto_cell(pr, pc)
            sys.stdout.write(self._bg_grid[pr][pc])
        self._goto_cell(row, col)
        c = ANSI.get(color if color in ANSI else "gray", ANSI["gray"])
        sys.stdout.write(f"{c}X{ANSI['reset']}")
        sys.stdout.flush()
        self._last_cell = (row, col)
