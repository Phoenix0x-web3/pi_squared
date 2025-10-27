import random
import re
from datetime import datetime, timedelta

from faker import Faker
from loguru import logger

from libs.fastset_async.client import FastSetClient
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from utils.logs_decorator import controller_log

from .authorization import AuthClient


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

        try:
            faucet = await self.fastset_client.wallet.faucet_drip(
                recipient_set=self.fastset_client.account.address,
                amount=1000
            )

            cooldown_until = datetime.now() + timedelta(minutes=1440)
            self.wallet.next_faucet_time = cooldown_until

            return f'Success Faucet 1000 SET'

        except Exception as e:
            cooldown = str(e)
            match = re.search(r"cooldown time remaining:\s*(\d+)", cooldown)

            if match:
                minutes = int(match.group(1))
                cooldown_until = datetime.now() + timedelta(minutes=minutes)
                self.wallet.next_faucet_time = cooldown_until
                db.commit()

                return f'Failed, faucet availible on {cooldown_until}'
            else:
                return str(e)

    @controller_log('Send Tokens')
    async def send_tokens(self):
        balance = await self.fastset_client.wallet.get_balance()
        percent = random.randint(1, 5)
        amount = balance * percent // 100

        send = await self.fastset_client.transactions.send_token_transfer(
            recipient_address_set=self.fastset_client.account.address,
            amount=amount
        )

        if send:
            return f"Success send tokens to self: {self.fastset_client.account.address}"

        return 'Failed'

    @controller_log('Create Assets')
    async def mint_token(self):
        name = Faker().word()
        length = random.randint(3, 6)

        name = name[:length].upper()

        mint = await self.fastset_client.transactions.create_token(
            token_name=name,
            decimals=18,
            initial_amount=str(random.randint(3,10) * 10**random.randint(22, 26)),
            mints_set_addresses=[],
        )

        if mint:
            return f"Success created token {name}: {self.fastset_client.account.address}"

        return 'Failed'
