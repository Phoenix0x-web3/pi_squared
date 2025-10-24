import asyncio
import random
import re
from datetime import datetime, timedelta

from loguru import logger

from data.settings import Settings
from libs.fastset_async.client import FastSetClient
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import mark_discord_as_bad, update_discord_connect, update_points_and_top, db
from utils.discord.discord import DiscordOAuth
from utils.logs_decorator import controller_log
from utils.resource_manager import ResourceManager
from utils.twitter.twitter_client import TwitterClient, TwitterStatuses
from .authorization import AuthClient

from .http_client import BaseHttpClient


class WalletClient:
    __module__ = "Wallet"
    BASE_LINK = "https://pisquared-api.pulsar.money/api/v1"

    def __init__(self, user: Wallet ):
        self.wallet = user
        self.fastset_client = FastSetClient(private_key=self.wallet.private_key, proxy=self.wallet.proxy)
        self.auth_client = AuthClient(user=self.wallet)

    async def get_nonce(self):
        success, data = await self.auth_client.request(
            url=f"{self.BASE_LINK}/auth/fastset/nonce", use_refresh_token=False, method="GET")
        logger.debug(data)
        if success and isinstance(data, dict):
            return data.get('nonce')

    @controller_log('Connect Wallet')
    async def connect_wallet(self):
        if not self.wallet.private_key:
            self.wallet.private_key = self.fastset_client.account.private_key_hex()
            db.commit()

        await self.auth_client.login()

        nonce  = await self.get_nonce()

        signature = await self.fastset_client.account.sign_message(message=nonce)

        json_data = {
            'address': self.fastset_client.account.address,
            'signature': signature.hex(),
            'publicKey': self.fastset_client.account.public_key_hex(),
            'nonce': nonce,
        }

        success, data = await self.auth_client.request(
            url=f"{self.BASE_LINK}/auth/fastset/link",
            json_data=json_data,
            use_refresh_token=False,
            method="POST")
        logger.debug(data)
        if success and isinstance(data, dict):
            return 'Wallet Connected'

        return f'Failed to connect wallet | {data}'

    @controller_log('Faucet')
    async def faucet(self):

        time = datetime.now()

        balance = await self.fastset_client.wallet.get_balance()
        logger.debug(f'{self.wallet} | Balance: {balance} SET')

        if balance == 0:
            try:
                faucet = await self.fastset_client.wallet.faucet_drip(
                    recipient_set=self.fastset_client.account.address,
                    amount=1000
                )
                return f'Success Faucet 1000 SET {faucet}'

            except Exception as e:
                cooldown = str(e)
                match = re.search(r"cooldown time remaining:\s*(\d+)", cooldown)

                if match:
                    minutes = int(match.group(1))
                    cooldown_until = datetime.now() + timedelta(minutes=minutes)
                    self.wallet.next_faucet_time = cooldown_until
                    db.commit()

                    return f'Failed, faucet availible on {cooldown_until}'

        #if self.wallet.next_faucet_time <= time:

        return False

    async def send_tokens(self):
        pass

    async def mint_token(self):
        pass