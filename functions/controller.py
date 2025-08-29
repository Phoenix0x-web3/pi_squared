import asyncio
import random

import time, random

from loguru import logger

from data.settings import Settings
from modules.game.clicker import PiClicker
from modules.tasks.quests_client import QuestsClient
from modules.tasks.authorization import AuthClient
from modules.tasks.clicker_client import ClickerClient
from utils.db_api.models import Wallet
from utils.logs_decorator import controller_log

BOX_SIZE_MAP = [
    # {'BASE_X': 442, 'BASE_Y': 543, 'CONTAINER_PX': 276},
    # {'BASE_X': 415, 'BASE_Y': 410, 'CONTAINER_PX': 276},
    {'BASE_X': 895, 'BASE_Y': 269, 'CONTAINER_PX': 288},
    {'BASE_X': 557, 'BASE_Y': 161, 'CONTAINER_PX': 288},
    {'BASE_X': 557, 'BASE_Y': 224, 'CONTAINER_PX': 288},
    {'BASE_X': 981, 'BASE_Y': 345, 'CONTAINER_PX': 288},
    # {'BASE_X': 514, 'BASE_Y': 358, 'CONTAINER_PX': 276},
]

class Controller:
    __controller__ = 'Controller'

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        
        self.auth_client = AuthClient(user=self.wallet)
        self.quests_client = QuestsClient(user=self.wallet)
        self.clicker_client = PiClicker(wallet=self.wallet)


    async def register(self):
        session = await self.auth_client.login()
        return session
    
    async def complete_quests(self):
        session = await self.register()
        if session:
            await self.quests_client.complete_quests()

    async def complete_games(self):
        session = await self.register()
        if not session:
            return False
        total_play, best_score = await self.quests_client.get_game_stats()

        await self.handle_clicker(total_play=total_play, best_score=best_score)

    @controller_log('PiClicker')
    async def clicker_controller(self, box: dict, clicks: int | None = None):

        settings = Settings()
        if not clicks:
            clicks = random.randint(settings.clicks_min, settings.clicks_max)

        logger.info(f"{self.wallet} | {self.__controller__} | Clicker Handle | trying to click {clicks} times in a session")

        return await self.clicker_client.run_session_with_engine(
            base_x=box['BASE_X'],
            base_y=box['BASE_Y'],
            clicks=clicks,
            container_px=box['CONTAINER_PX'],
            show_viz=False,
        )

    async def handle_clicker(self, total_play: int, best_score: int, number_of_games: int = None):

        box = random.choice(BOX_SIZE_MAP)

        if total_play >= 30 and best_score >= 105:
            logger.success(f"{self.wallet} | {self.__controller__} | Clicker Handle | already played {total_play} games and have {best_score} best score")
            return True

        if number_of_games:
            games_to_play = number_of_games

        else:
            random_total_play = random.randint(Settings().games_min, Settings().games_max)
            random_total_play -= total_play
            games_to_play = random_total_play

            if games_to_play <= 0:
                logger.success(f"{self.wallet} | {self.__controller__} | Clicker Handle | already played {total_play} games")
                return True

        # generate random clicks
        clicks_list = [random.randint(Settings().clicks_min, Settings().clicks_max) for _ in range(games_to_play)]

        # guarantee at least one > 105
        if all(c <= 105 for c in clicks_list):
            idx = random.randrange(games_to_play)
            clicks_list[idx] = random.randint(106, 150)

        random.shuffle(clicks_list)

        for clicks in clicks_list:
            try:
                clicks_result = await self.clicker_controller(box=box, clicks=clicks)
                logger.success(clicks_result)
                random_sleep = random.randint(Settings().random_pause_between_actions_min,
                                              Settings().random_pause_between_actions_max)
                await asyncio.sleep(random_sleep)

            except Exception as e:
                logger.error(f"{e} | can't play game, continue")
                await asyncio.sleep(5)
                continue
        return True

    async def run_all_tasks(self, timeout_s: int = 3600):
        session = await self.register()

        if not session:
            return False

        settings = Settings()
        deadline = time.monotonic() + timeout_s
        
        while time.monotonic() < deadline:
 
            total_play, best_score = await self.quests_client.get_game_stats()
            if random.random() < 0.60:  # 60% chance  
                await self.quests_client.complete_quests(random_stop=True)

            else:
                #number_of_games = random.randint(1, 30)
                number_of_games = random.randint(settings.games_min, settings.games_max)

                await self.handle_clicker(total_play=total_play, best_score=best_score, number_of_games=number_of_games)
                   
            if total_play >= 30 and best_score >= 105:
                break

        await self.quests_client.complete_quests()
