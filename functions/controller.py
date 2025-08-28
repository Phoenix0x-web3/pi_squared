import random

from loguru import logger

from data.settings import Settings
from modules.tasks.quests_client import QuestsClient
from modules.tasks.authorization import AuthClient
from modules.tasks.clicker_client import ClickerClient
from utils.db_api.models import Wallet
from utils.logs_decorator import controller_log


class Controller:
    __controller__ = 'Controller'

    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        
        self.auth_client = AuthClient(user=self.wallet)
        self.quests_client = QuestsClient(user=self.wallet)
        self.clicker_client = ClickerClient(wallet=self.wallet)


    async def register(self):
        session = await self.auth_client.login()
        return session
    
    async def complete_quests(self):
        session = await self.register()
        if session:
            await self.quests_client.complete_quests()

    async def complete_games(self):
        await self.clicker_client.handle_clicker(total_play=total_play, best_score=best_score)

    async def run_all_tasks(self):
        session = await self.register()
        if not session:
            return False
        await self.quests_client.complete_quests(random_stop=True)
        total_play, best_score = await self.quests_client.get_game_stats()
        await self.clicker_client.handle_clicker(total_play=total_play, best_score=best_score)
        await self.quests_client.complete_quests(random_stop=True)
