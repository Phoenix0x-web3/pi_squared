import random
import asyncio
from loguru import logger
from modules.game.clicker import PiClicker
from data.settings import Settings
from utils.retry import async_retry

class ClickerClient(PiClicker):



    async def handle_clicker(self, total_play: int, best_score: int, number_of_games: int = None):
        if total_play >= 30 and best_score >= 105:
            logger.success(f"{self.wallet} already played {total_play} games and have {best_score} best score")
            return True

        if number_of_games:
            games_to_play = number_of_games
        else:
            random_total_play = random.randint(Settings().games_min, Settings().games_max)
            random_total_play -= total_play
            games_to_play = random_total_play

            if games_to_play <= 0:
                logger.success(f"{self.wallet} already played {total_play} games")
                return True

        # generate random clicks  
        clicks_list = [random.randint(Settings().clicks_min, Settings().clicks_max) for _ in range(games_to_play)]

        # guarantee at least one > 105
        if all(c <= 105 for c in clicks_list):
            idx = random.randrange(games_to_play)
            clicks_list[idx] = random.randint(106, 150)

    
        random.shuffle(clicks_list)

        # --- play loop ---
        for clicks in clicks_list:
            try:
                clicks_result = await self.clicker_controller(clicks=clicks)
                logger.success(clicks_result)
                random_sleep = random.randint(Settings().random_pause_between_actions_min,Settings().random_pause_between_actions_max)
                await asyncio.sleep(random_sleep)
            except Exception:
                logger.error(f"{self.wallet} can't play game, continue")
                await asyncio.sleep(5)
                continue

        return True

        

