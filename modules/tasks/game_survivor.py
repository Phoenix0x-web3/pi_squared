import asyncio
import random
from time import time

from loguru import logger

from .http_client import BaseHttpClient


class GameSurvivor(BaseHttpClient):
    __module__ = "PiPortal Game Survivor"
    BASE_LINK = "https://pisquared-api.pulsar.money/api/v1/game-sessions"
    GAME_ID = None

    async def complete_game(self):
        logger.info(f"{self.user} start Survivor Game")
        await self.start_game()
        if not self.GAME_ID:
            raise Exception("Can't start game")
        start_game_time = time()
        completed_actions = await self.make_random_actions(start_time=start_game_time)
        logger.debug(completed_actions)
        duration = str(random.uniform(63.0, 63.05)) + str(random.randint(1, 9))
        end_game = await self.end_game(
            score=completed_actions["Pickup"], tps=random.uniform(4.0, 5.5), duration=float(duration), level=1, pi_stage=0
        )
        if not end_game:
            raise Exception("Can't end game")
        logger.success(f"{self.user} success complete survivor game. With {completed_actions['Pickup']} points")
        return True

    async def start_game(self):
        json_data = {
            "gameType": "survivor",
        }
        success, data = await self.request(
            url=f"{self.BASE_LINK}/start", method="POST", use_refresh_token=False, json_data=json_data, close_session=False
        )
        logger.debug(data)
        if success and isinstance(data, dict):
            self.GAME_ID = data["id"]

    async def make_random_actions(self, start_time: float, move_x_start=False, move_y_start=False, completed_actions={}):
        if not completed_actions:
            completed_actions = {"MoveXStart": 0, "MoveXStop": 0, "MoveYStart": 0, "MoveYStop": 0, "Bomb": 0, "Pickup": 0}
        if start_time + 63 < time():
            return completed_actions
        action = []
        action.append("Pickup")
        if move_x_start:
            action.append("MoveXStop")
        else:
            action.append("MoveXStart")
        if move_y_start:
            action.append("MoveYStop")
        else:
            action.append("MoveYStart")
        if random.randint(1, 100) < 25:
            action.append("Bomb")
        action = random.choice(action)
        if action == "MoveXStart":
            move_x_start = True
        elif action == "MoveYStart":
            move_y_start = True
        elif action == "MoveXStop":
            move_x_start = False
        elif action == "MoveYStop":
            move_y_start = False
        completed_actions[action] += 1
        logger.debug(f"{self.user} complete action {action}")
        await self.complete_action(action_name=action)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        return await self.make_random_actions(
            start_time=start_time, move_x_start=move_x_start, move_y_start=move_y_start, completed_actions=completed_actions
        )

    async def end_game(self, score: int, tps: float, duration: float, level: int, pi_stage: int):
        json_data = {
            "score": score,
            "tps": tps,
            "duration": duration,
            "level": level,
            "piStageReached": f"{pi_stage}",
            "gameType": "survivor",
        }
        success, data = await self.request(
            url=f"{self.BASE_LINK}/{self.GAME_ID}/end", method="PUT", use_refresh_token=False, json_data=json_data
        )
        logger.debug(data)
        return success

    async def complete_action(self, action_name: str):
        json_data = {
            "color": action_name,
            "isCorrect": True,
            "energyGenerated": 0,
            "x": 0,
            "y": 0,
            "timestamp": int(time() * 1000),
            "gameType": "survivor",
        }
        logger.debug(json_data)
        success, data = await self.request(
            url=f"{self.BASE_LINK}/{self.GAME_ID}/click",
            method="POST",
            use_refresh_token=False,
            json_data=json_data,
            close_session=False,
            retries=1,
        )
        if success and isinstance(data, dict):
            return data["success"]
        return False
