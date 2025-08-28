import asyncio
import random
from datetime import datetime, timedelta

from loguru import logger

from functions.controller import Controller
from utils.db_api.models import Wallet
from utils.db_api.wallet_api import db
from data.settings import Settings

async def random_sleep_before_start(wallet):
    random_sleep = random.randint(Settings().random_pause_start_wallet_min, Settings().random_pause_start_wallet_max)
    now = datetime.now()

    logger.info(f"{wallet} Start at {now + timedelta(seconds=random_sleep)} sleep {random_sleep} seconds before start actions")
    await asyncio.sleep(random_sleep)
    
async def execute(wallets : Wallet, task_func, timeout_hours : int = 0):
    
    while True:
        
        semaphore = asyncio.Semaphore(min(len(wallets), Settings().threads))

        if Settings().shuffle_wallets:
            random.shuffle(wallets)

        async def sem_task(wallet : Wallet):
            async with semaphore:
                try:
                    await task_func(wallet)
                except Exception as e:
                    logger.error(f"[{wallet.id}] failed: {e}")

        tasks = [asyncio.create_task(sem_task(wallet)) for wallet in wallets]
        await asyncio.gather(*tasks)

        if timeout_hours == 0:
            break
        
        logger.info(f"Sleeping for {timeout_hours} hours before the next iteration")
        await asyncio.sleep(timeout_hours * 60 * 60)
        

async def activity(action: int):

    wallets = db.all(Wallet)
   

    range_wallets = Settings().range_wallets_to_run
    if range_wallets != [0, 0]: 
        start, end = range_wallets
        wallets = [
            wallet for i, wallet in enumerate(wallets, start=1)
            if start <= i <= end
        ]
    else:
        if Settings().exact_wallets_to_run:
            wallets = [
                wallet for i, wallet in enumerate(wallets, start=1)
                if i in Settings().exact_wallets_to_run
            ]

    if action == 1:
        await execute(wallets, register)

    if action == 2:
        await execute(wallets, complete_quests)

async def register(wallet):
    
    await random_sleep_before_start(wallet=wallet)
    
    controller = Controller(wallet=wallet)

    c = await controller.register()

async def complete_quests(wallet):
    
    await random_sleep_before_start(wallet=wallet)
    
    controller = Controller(wallet=wallet)

    c = await controller.complete_quests()
