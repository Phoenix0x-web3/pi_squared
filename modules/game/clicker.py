from __future__ import annotations

import asyncio
import json
import math
import random
import time
from typing import Any, Dict, Optional, List, Tuple
from loguru import logger

from modules.game.core import ReactorGameEngine
from modules.game.orb import ReactorGeometry, FrontAccurateOrbArena, StaticArenaOverlay, ANSI
from modules.game.scheduler import TargetScheduler
from modules.game.stages import default_stage_plan
from utils.retry import async_retry
from utils.browser import Browser
from utils.db_api.models import Wallet


class PiClicker:
    __module__ = 'Pi Clicker'
    BASE = "https://pisquared-api.pulsar.money/api/v1"

    def __init__(self, wallet: Wallet):
        self.session = Browser(wallet=wallet)
        self.wallet = wallet
        self._auth = self.wallet.bearer_token

        self.base_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Authorization': f" Bearer {self.wallet.bearer_token}",
            'Origin': 'https://portal.pi2.network',
            'Referer': 'https://portal.pi2.network/',
            'Host': 'pisquared-api.pulsar.money',
        }

    @async_retry()
    async def start_game_session(self):
        url = f'{self.BASE}/game-sessions/start'
        r = await self.session.post(url=url, headers=self.base_headers, timeout=20)

        if not r.status_code <= 202:
            raise Exception(f"{r.status_code} | {r.text}")
        try:
            return r.json()
        except Exception as e:
            raise Exception(f"Start Session | {e} | {r.status_code} | {r.text}")

    @async_retry()
    async def click(
        self,
        game_session_id: str,
        *,
        x: int,
        y: int,
        color: str = "red",
        is_correct: bool = True,
        energy_generated: int = 1,
        timestamp_ms: Optional[int] = None,
    ):
        ts = int(time.time() * 1000) if timestamp_ms is None else int(timestamp_ms)
        json_data: Dict[str, Any] = {
            "color": color,
            "isCorrect": is_correct,
            "energyGenerated": energy_generated,
            "x": x,
            "y": y,
            "timestamp": ts,
        }
        url = f"{self.BASE}/game-sessions/{game_session_id}/click"

        r = await self.session.post(url=url, headers=self.base_headers, json=json_data)

        if not r.status_code <= 202:
            raise Exception(f"{r.status_code} | {r.text}")
        try:
            return r.json()
        except Exception as e:
            raise Exception(f"Start Session | {e} | {r.status_code} | {r.text}")

    async def end_game_session(self, game_session_id: str, payload: Dict[str, Any]):
        """payload = {'score','tps','duration','level','piStageReached'}"""
        url = f"{self.BASE}/game-sessions/{game_session_id}/end"
        r = await self.session.put(url=url, headers=self.base_headers, json=payload)

        if not r.status_code <= 202:
            raise Exception(f"End Game Session | {r.status_code} | {r.text}")
        try:
            return r.json()

        except Exception as e:
            raise Exception(f"End Game Session | {e} | {r.status_code} | {r.text}")


    @staticmethod
    def _rand_near(cx: int, cy: int, *, max_r: int = 10, min_r: int = 2) -> Tuple[int, int]:
        a = random.random() * 2 * math.pi
        r = random.uniform(min_r, max_r)
        return int(cx + r * math.cos(a)), int(cy + r * math.sin(a))

    async def run_session_with_engine(self,
            base_x: int,
            base_y: int,
            clicks: int = 100,
            container_px: int = 256,
            show_viz: bool = True,
            stage_speeds_ms: Optional[List[int]] = None,
            tps_mode: str = "random", # 'peak' | 'avg' | 'random'
            override_level: Optional[int] = None,
            override_pi_stage: Optional[str] = None,
    ):

        engine = ReactorGameEngine(default_stage_plan())

        geom = ReactorGeometry(container_px=container_px)
        arena = FrontAccurateOrbArena(
            cx=base_x,
            cy=base_y,
            geom=geom,
            grid_w=61,
            grid_h=33,
            clear_screen=True,
            colors=None,
            randomize_order=True,
            random_phase=True,
        )
        palette = arena.colors

        # --- start ---
        start_resp = await self.start_game_session()

        session_id = start_resp.get("id") if isinstance(start_resp, dict) else json.loads(start_resp).get("id")
        logger.debug(f"{self.wallet} | {self.__module__} | Started GameSessionID: {session_id}")

        stage_speeds_ms = stage_speeds_ms or [4000, 3000, 2200, 1700, 1300, 1100, 800, 400]

        cur_idx = engine.current_stage_index
        sched = TargetScheduler(palette, interval_ms=stage_speeds_ms[cur_idx])

        last_stage = cur_idx
        i = 0

        while i < clicks:
            target_color, ms_left, changed = sched.tick()

            if changed:

                logger.debug(
                    f"{self.wallet} | {self.__module__} | COLOR→ {target_color} | stage={engine.current_stage_index} "
                    f"interval={sched.interval_ms}ms (prev lasted ~{sched.last_change_ms}ms)"
                )

            cx, cy = arena.color_center_now(target_color)
            x, y = self._rand_near(cx, cy, max_r=8, min_r=2)
            ts_ms = int(time.time() * 1000)

            if show_viz:
                detected = arena.add_click(x, y, target_color=target_color, ms_left=ms_left)
            else:
                detected = target_color

            is_ok = (detected == target_color)
            color_for_backend = detected

            _ = await self.click(
                session_id,
                x=x, y=y,
                color=color_for_backend,
                is_correct=is_ok,
                energy_generated=(1 if is_ok else 0),
                timestamp_ms=ts_ms,
            )
            logger.debug(f"{self.wallet} | {self.__module__} | clicked x={x} y={y} color={target_color}")
            engine.register_click(energy_generated=(1 if is_ok else 0))
            i += 1

            # accelerate with last stage
            if engine.current_stage_index != last_stage:
                last_stage = engine.current_stage_index
                speed = stage_speeds_ms[min(last_stage, len(stage_speeds_ms) - 1)]
                sched.set_speed(speed)
                arena.header_note = f"stage→{last_stage} speed={speed}ms"

            await asyncio.sleep(random.uniform(0.0001, 0.005))

        end_payload = engine.build_end_payload(
            tps_mode=tps_mode,
            override_level=override_level,
            override_pi_stage=override_pi_stage,
        )

        end_resp = await self.end_game_session(session_id, payload=end_payload)

        if end_resp.get('score') > 0:
            result = f"[Score: {end_resp.get('score')}, TPS: {end_resp.get('tps')}, PiReached: {end_resp.get('piStageReached')}]"
            return f"Success Clicked {result}"
