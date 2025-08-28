import random

from loguru import logger

from data.settings import Settings
from modules.game.clicker import PiClicker
from modules.tasks.authorization import AuthClient
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from utils.logs_decorator import controller_log


class Controller:
    __controller__ = 'Controller'

    def __init__(self, wallet: Wallet):
        #super().__init__(client)
        self.wallet = wallet
        self.pi_clicker = PiClicker(wallet=wallet)

    async def register(self):
        auth_client = AuthClient(user=self.wallet)
        await auth_client.login()
        return

    @controller_log('Pi Clicker')
    async def clicker_controller(self):

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

        clicks = random.randint(settings.clicks_min, settings.clicks_max)

        box = random.choice(box_size_map)
        logger.info(f"{self.wallet} | {self.__controller__} | trying to click {clicks} times in a session")

        return await self.pi_clicker.run_session_with_engine(
            base_x=box['BASE_X'],
            base_y=box['BASE_Y'],
            clicks=clicks,
            container_px=box['CONTAINER_PX'],
            show_viz=False,
        )
