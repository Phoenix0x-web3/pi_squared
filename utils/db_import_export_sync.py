import os
import random
from types import SimpleNamespace
from typing import List, Dict, Optional

from loguru import logger

from data.config import FILES_DIR

from utils.db_api.wallet_api import db, get_wallet_by_email_data
from utils.db_api.models import Wallet

def parse_proxy(proxy: str | None) -> Optional[str]:
    if not proxy:
        return None
    if proxy.startswith('http'):
        return proxy
    elif "@" in proxy and not proxy.startswith('http'):
        return "http://" + proxy
    else:
        value = proxy.split(':')
        if len(value) == 4:
            ip, port, login, password = value
            return f'http://{login}:{password}@{ip}:{port}'
        else:
            print(f"Invalid proxy format: {proxy}")
            return None 

def remove_line_from_file(value: str, filename: str) -> bool:
    file_path = os.path.join(FILES_DIR, filename)

    if not os.path.isfile(file_path):
        return False

    with open(file_path, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    original_len = len(lines)

    keep = [line for line in lines if line.strip() != value.strip()]

    if len(keep) == original_len:
        return False

    with open(file_path, "w", encoding="utf-8") as f:
        for line in keep:
            f.write(line + "\n")
    return True

def read_lines(path: str) -> List[str]:

    file_path = os.path.join(FILES_DIR, path)
    if not os.path.isfile(file_path):
        return []
    with open(file_path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]
    
class Import:

    @staticmethod
    def parse_wallet_from_txt() -> List[Dict[str, Optional[str]]]:

        proxies        = read_lines("proxy.txt")
        twitter_tokens = read_lines("twitter_tokens.txt")
        email_data = read_lines("email_data.txt")

        record_count = len(email_data)

        def pick_proxy(i: int) -> Optional[str]:
            if not proxies:
                return None
            if i < len(proxies):
                return proxies[i % len(proxies)]

            return random.choice(proxies)

        wallets: List[Dict[str, Optional[str]]] = []
        for i in range(record_count):
            wallets.append({
                "email_data": email_data[i] if i < len(email_data) else None,
                "proxy": parse_proxy(pick_proxy(i)),
                "twitter_token": twitter_tokens[i] if i < len(twitter_tokens) else None,
            })

        return wallets


    @staticmethod
    async def wallets():
        raw_wallets = Import.parse_wallet_from_txt()

        wallets = [SimpleNamespace(**w) for w in raw_wallets]

        imported: list[Wallet] = []
        edited: list[Wallet] = []
        total = len(wallets)


        for wl in wallets:


            wallet_instance = get_wallet_by_email_data(wl.email_data)

            if wallet_instance:
                changed = False

                if wallet_instance.proxy != parse_proxy(wl.proxy):
                    wallet_instance.proxy = wl.proxy
                    changed = True

                if hasattr(wallet_instance, "twitter_token") and wallet_instance.twitter_token != wl.twitter_token:
                    wallet_instance.twitter_token = wl.twitter_token
                    changed = True


                if hasattr(wallet_instance, "email_data") and wallet_instance.email_data != wl.email_data:
                    wallet_instance.email_data = wl.email_data
                    changed = True

                if changed:
                    db.commit()
                    edited.append(wallet_instance)

                continue

            wallet_instance = Wallet(
                proxy=wl.proxy,
                twitter_token=wl.twitter_token,
                email_data=wl.email_data,
            )

            if not wallet_instance.twitter_token:
                logger.warning(f'{wallet_instance.id} | Twitter Token not found, Twitter Action will be skipped')

            db.insert(wallet_instance)
            imported.append(wallet_instance)

        logger.success(
            f'Done! imported wallets: {len(imported)}/{total}; '
            f'edited wallets: {len(edited)}/{total}; total: {total}'
        )

       
    
class Sync:
    
    @staticmethod
    def parse_tokens_and_proxies_from_txt() -> List[Dict[str, Optional[str]]]:

        proxies        = read_lines("proxy.txt")
        twitter_tokens = read_lines("twitter_tokens.txt")
        email_data = read_lines("email_data.txt")
        
        record_count = len(twitter_tokens)

        def pick_proxy(i: int) -> Optional[str]:
            if not proxies:
                return None
            if i < len(proxies):
                return proxies[i % len(proxies)]

            return random.choice(proxies)

        wallets: List[Dict[str, Optional[str]]] = []
        for i in range(record_count):
            wallets.append({
                "proxy": parse_proxy(pick_proxy(i)),
                "twitter_token": twitter_tokens[i] if i < len(twitter_tokens) else None,
                "email_data": email_data[i] if i < len(email_data) else None,
            })

        return wallets
    

    @staticmethod
    async def sync_wallets_with_tokens_and_proxies():
       
        wallet_auxiliary_data_raw  = Sync.parse_tokens_and_proxies_from_txt()

        wallet_auxiliary_data = [SimpleNamespace(**w) for w in wallet_auxiliary_data_raw]
          
        wallets = db.all(Wallet)

 
        if len(wallet_auxiliary_data) != len(wallets):
            logger.warning("Mismatch between wallet data and tokens/proxies data. Exiting sync.")
            return
        
        if len(wallets) <= 0:
            logger.warning("No wallets in DB, nothing to update")
            return
        
        total = len(wallets)

        logger.info(f"Start syncing wallets: {total}")
        
        edited: list[Wallet] = []
        for wl in wallets:

            wallet_instance = get_wallet_by_email_data(wl.email_data)

            if wallet_instance:
                changed = False

                wallet_data  = wallet_auxiliary_data [wallet_instance.id - 1]
                if wallet_instance.proxy != wallet_data.proxy:
                    wallet_instance.proxy = wallet_data.proxy
                    changed = True

                if hasattr(wallet_instance, "twitter_token") and wallet_instance.twitter_token != wallet_data.twitter_token:
                    wallet_instance.twitter_token = wallet_data.twitter_token
                    changed = True

                if hasattr(wallet_instance, "email_data") and wallet_instance.email_data != wallet_data.email_data:
                    wallet_instance.email_data = wallet_data.email_data
                    changed = True

                if changed:
                    db.commit()
                    edited.append(wallet_instance)


        logger.success(f'Done! edited wallets: {len(edited)}/{total}; total: {total}')
        
class Export:

    _FILES = {
        "proxy":         "exported_proxy.txt",
        "twitter_token": "exported_twitter_tokens.txt",
        "email_data": "exported_email_data.txt",
    }

    @staticmethod
    def _write_lines(filename: str, lines: List[Optional[str]]) -> None:

        path = os.path.join(FILES_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write((line or "") + "\n")

    @staticmethod
    async def wallets_to_txt() -> None:

        wallets: List[Wallet] = db.all(Wallet)

        if not wallets:
            logger.warning("Export: no wallets in db, skip....")
            return

        buf = {key: [] for key in Export._FILES.keys()}

        for w in wallets:
            buf["proxy"].append(w.proxy or "")
            buf["twitter_token"].append(w.twitter_token or "")
            buf["email_data"].append(w.email_data or "")

        for field, filename in Export._FILES.items():
            Export._write_lines(filename, buf[field])

        logger.success(f"Export: exported {len(wallets)} wallets in {FILES_DIR}")
