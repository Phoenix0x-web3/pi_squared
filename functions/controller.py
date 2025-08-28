from modules.tasks.authorization import AuthClient
from modules.tasks.quests_client import QuestsClient
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from utils.logs_decorator import controller_log


class Controller:

    def __init__(self, wallet: Wallet):
        #super().__init__(client)
        self.wallet = wallet
        self.auth_client = AuthClient(user=self.wallet)
        self.quests_client = QuestsClient(user=self.wallet)

    async def register(self):
        session = await self.auth_client.login()
        if session:
            return True
        return False
    
    async def complete_quests(self):
        session = await self.register()
        if session:
            await self.quests_client.complete_quests()


