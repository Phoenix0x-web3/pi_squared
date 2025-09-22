import asyncio
import random

import time, random

from loguru import logger

from data.settings import Settings
from modules.game.clicker import PiClicker
from modules.tasks.quests_client import QuestsClient
from modules.tasks.authorization import AuthClient
from utils.db_api.models import Wallet
from utils.logs_decorator import controller_log
from modules.hs_form import HSForm

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

    async def register(self):
        return await self.auth_client.login()
    
    async def complete_quests(self):
        session = await self.register()
        if session:
            await self.quests_client.complete_quests()

    async def complete_games(self):
        session = await self.register()
        if not session:
            return False
        await self.handle_clicker( )

    @controller_log('PiClicker')
    async def clicker_controller(self, box: dict, clicks: int | None = None):

        settings = Settings()
        if not clicks:
            clicks = random.randint(settings.clicks_min, settings.clicks_max)

        logger.info(f"{self.wallet} | {self.__controller__} | Clicker Handle | trying to click {clicks} times in a session")

        clicker_client = PiClicker(wallet=self.wallet)
        return await clicker_client.run_session_with_engine(
            base_x=box['BASE_X'],
            base_y=box['BASE_Y'],
            clicks=clicks,
            container_px=box['CONTAINER_PX'],
            show_viz=False,
        )

    async def handle_clicker(self):

        games_to_play = random.randint(Settings().games_min, Settings().games_max)
        
        # generate random clicks
        clicks_list = [random.randint(Settings().clicks_min, Settings().clicks_max) for _ in range(games_to_play)]

        # guarantee at least one > 105
        if all(c <= 105 for c in clicks_list):
            idx = random.randrange(games_to_play)
            clicks_list[idx] = random.randint(106, 150)

        random.shuffle(clicks_list)
        logger.info(f"{self.wallet} | {self.__controller__} | Clicker Handle | Playing {games_to_play} games")
        for clicks in clicks_list:
            try:
                box = random.choice(BOX_SIZE_MAP)
                clicks_result = await self.clicker_controller(box=box, clicks=clicks)
                logger.success(clicks_result)
                random_sleep = random.randint(Settings().random_pause_between_actions_min,
                                              Settings().random_pause_between_actions_max)
                await asyncio.sleep(random_sleep)

            except Exception as e:
                logger.error(f"{self.wallet} {e} | can't play game, continue")
                await asyncio.sleep(5)
                continue
        return True

    async def run_all_tasks(self):
        session = await self.register()

        if not session:
            return False

        if random.random() < 0.60:  # 60% chance  
            await self.quests_client.complete_quests(random_stop=True)
        else:
            await self.handle_clicker()
                
        await self.quests_client.complete_quests()

    async def update_points(self):
        session = await self.register()
        if session:
            return await self.quests_client.get_and_update_points()

    @controller_log('HS Form')
    async def fill_hs_form(self):
        instance = HSForm(wallet=self.wallet)
        
        return await instance.fill_form()