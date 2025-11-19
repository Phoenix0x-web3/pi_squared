import asyncio
import random

import time, random
from datetime import datetime

from loguru import logger

from data.settings import Settings
from modules.game.clicker import PiClicker
from modules.tasks.quests_client import QuestsClient
from modules.tasks.authorization import AuthClient
from modules.tasks.wallet import WalletClient
from modules.tasks.game_survivor import GameSurvivor
from modules.tasks.omni_set import OmniClient
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from utils.logs_decorator import controller_log
from utils.twitter.twitter_client import TwitterClient
from modules.hs_form import HSForm

BOX_SIZE_MAP = [
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
        self.onchain = WalletClient(user=self.wallet)
        self.game_survivor = GameSurvivor(user=self.wallet)
        self.omni_client = OmniClient(user=self.wallet)

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

    async def complete_survivor_game(self):
        session = await self.register()
        if session:
            await self.game_survivor.complete_game()

    async def complete_bridges(self):
        if not self.wallet.evm_private_key:
            logger.error(f"{self.wallet} doesn't have evm private key for bridges")
            return False
        actions = [lambda: self.omni_client.bridge_to_fastet("SET"), lambda: self.omni_client.bridge_to_evm("ETH")]
        random.shuffle(actions)
        for action in actions:
            await action()

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
        
        if games_to_play == 0:
            logger.info(f"{self.wallet} | {self.__controller__} | Clicker Handle | No games to play as per settings")
            return True
        
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
        
        if random.random() < 0.40:  # 40% chance  
            await self.quests_client.complete_quests(random_stop=True)
        else:
            actions = [self.wallet_actions, self.handle_clicker, self.complete_survivor_game]
            random.shuffle(actions)

            for action in actions:
                await action()
                
        await self.quests_client.complete_quests()

    async def update_points(self):
        session = await self.register()
        if session:
            return await self.quests_client.get_and_update_points()

    @controller_log('HS Form')
    async def fill_hs_form(self):
        instance = HSForm(wallet=self.wallet)
        
        return await instance.fill_form()
    
    async def reconnect_twitter(self):
        session = await self.register()

        if not session:
            return False
        
        delete_replace = await self.quests_client.delete_twitter_replace_token()
        if delete_replace:
            twitter_client = TwitterClient(user=self.wallet)
            init = await twitter_client.initialize()
            if not init:
                logger.warning(f"{self.wallet} can't initialize twitter")
                return False
            connect = await self.quests_client.connect_twitter_to_portal(twitter_client=twitter_client)
            if not connect:
                logger.warning(f"{self.wallet} can't connect twitter")
                return False
        return True

    async def wallet_actions(self):

        time = datetime.now()

        await self.auth_client.login()

        if not self.wallet.private_key:
            self.wallet.private_key = self.onchain.fastset_client.account.private_key_hex()
            db.commit()

        try:
            balance = await self.onchain.fastset_client.wallet.get_balance()

            data = await self.auth_client.get_session()
            if not data.get('user').get('extensionWalletAddress'):
                connect_wallet = await self.onchain.connect_wallet()
                logger.success(connect_wallet)

            if balance == 0:
                faucet = await self.onchain.faucet()
                if 'Failed' not in faucet:
                    logger.success(faucet)
                    await asyncio.sleep(random.randint(5, 10))

            if self.wallet.next_faucet_time:
                if self.wallet.next_faucet_time <= time:
                    faucet = await self.onchain.faucet()
                    logger.success(faucet)
                    await asyncio.sleep(random.randint(5, 10))

            uncompleted_tasks = await self.quests_client.get_uncompleted_tasks()

            for task in uncompleted_tasks:
                if 'Create and transfer assets using FastSet wallet extension' in task['title']:
                    transfer_to_self = await self.onchain.send_tokens()
                    if 'Failed' not in transfer_to_self:
                        logger.success(transfer_to_self)
                        await asyncio.sleep(random.randint(5, 10))

                    create_assets = await self.onchain.mint_token()
                    if 'Failed' not in create_assets:
                        logger.success(create_assets)
                        await asyncio.sleep(random.randint(5, 10))


            cube = random.randint(1, 7)

            if cube == 2:
                transfer_to_self = await self.onchain.send_tokens()
                if 'Failed' not in transfer_to_self:
                    logger.success(transfer_to_self)
                    await asyncio.sleep(random.randint(5, 10))

            if cube == 5:
                create_assets = await self.onchain.mint_token()
                if 'Failed' not in create_assets:
                    logger.success(create_assets)
                    await asyncio.sleep(random.randint(5, 10))

            return 'Success Done wallet actions'

        except Exception as e:
            msg = f"{self.wallet} | Controller | Wallet Actions | Failed | {e}"
            return msg
