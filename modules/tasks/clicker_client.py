import random
import asyncio
from loguru import logger
from modules.game.clicker import PiClicker
from data.settings import Settings
from utils.retry import async_retry

class ClickerClient(PiClicker):

    @async_retry()
    async def clicker_controller(self, clicks: int | None = None):

        box_size_map = [
            #{'BASE_X': 442, 'BASE_Y': 543, 'CONTAINER_PX': 276},
            #{'BASE_X': 415, 'BASE_Y': 410, 'CONTAINER_PX': 276},
            {'BASE_X': 895, 'BASE_Y': 269, 'CONTAINER_PX': 288},
            {'BASE_X': 557, 'BASE_Y': 161, 'CONTAINER_PX': 288},
            {'BASE_X': 557, 'BASE_Y': 224, 'CONTAINER_PX': 288},
            {'BASE_X': 981, 'BASE_Y': 345, 'CONTAINER_PX': 288},
            #{'BASE_X': 514, 'BASE_Y': 358, 'CONTAINER_PX': 276},
        ]

        settings = Settings()

        if not clicks:
            clicks = random.randint(settings.clicks_min, settings.clicks_max)
        box = random.choice(box_size_map)
        logger.info(f"{self.wallet} trying to click {clicks} times in a session")

        return await self.run_session_with_engine(
            base_x=box['BASE_X'],
            base_y=box['BASE_Y'],
            clicks=clicks,
            container_px=box['CONTAINER_PX'],
            show_viz=False,
        )

    async def handle_clicker(self, total_play: int, best_score: int, number_of_games : int = None):
        
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
            
        clicks = None
        for _ in range(games_to_play):
            try:
                if best_score < 105:
                    clicks = random.randint(106, 150)
                    best_score = clicks
                clicks_result = await self.clicker_controller(clicks=clicks)
                logger.success(clicks_result)
                random_sleep = random.randint(Settings().random_pause_between_actions_min, Settings().random_pause_between_actions_max)
                await asyncio.sleep(random_sleep)
            except Exception:
                logger.error(f"{self.wallet} can't play game continue")
                await asyncio.sleep(5)
                continue
        return True

        

