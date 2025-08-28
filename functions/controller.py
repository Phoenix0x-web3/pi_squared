from modules.tasks.authorization import AuthClient
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from utils.logs_decorator import controller_log


class Controller:

    def __init__(self, wallet: Wallet):
        #super().__init__(client)
        self.wallet = wallet

    async def register(self):
        auth_client = AuthClient(user=self.wallet)
        await auth_client.login()
        return

