import asyncio
import random
import time

from eth_utils.crypto import keccak
from loguru import logger
from web3.types import TxParams

from libs.eth_async.client import Client
from libs.eth_async.data.models import Network, Networks, RawContract, TokenAmount
from libs.fastset_async.client import FastSetClient
from libs.fastset_async.utils.account import set_to_bytes
from utils.browser import Browser
from utils.db_api.models import Wallet
from utils.retry import async_retry

from .http_client import BaseHttpClient

bridge_abi = [
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "bytes32", "name": "ft3_account_id", "type": "bytes32"},
        ],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]
BRIDGE_CONTRACT = RawContract(title="BRIDGE", address="0xaDB4f3334825E645dD201de5CF1778a09515936f", abi=bridge_abi)


class OmniClient(BaseHttpClient):
    def __init__(self, user: Wallet):
        super().__init__(user)
        self.fastset_client = FastSetClient(private_key=user.private_key, proxy=user.proxy)
        self.evm_client = Client(private_key=user.evm_private_key)
        self.browser = Browser(wallet=user)

    @async_retry()
    async def bridge_to_evm(self, token_withdraw: str = "SET"):
        if token_withdraw == "SET":
            token_id = "0xfa575e7000000000000000000000000000000000000000000000000000000000"
            evm_token_address = "0xc6d2bd6437655fbc6689bfc987e09846ac4367ed"
        else:
            token_id = "0x37bb8861c49c6f59d869634557245b8640c2de6a2d3dffd6ad4065f6f67989f1"
            evm_token_address = "0xfff9976782d46cc05630d1f6ebab18b2324d6b14"

        id_arr = list(bytes.fromhex(token_id.removeprefix("0x")))
        balance = await self.fastset_client.wallet.get_balance(token_balances_filter=[id_arr])
        if float(TokenAmount(balance, wei=True).Ether) < 0.001 and token_withdraw == "ETH":
            await self.bridge_to_fastet(token_deposit="ETH")
            await asyncio.sleep(random.randint(10, 30))
            balance = await self.fastset_client.wallet.get_balance(token_balances_filter=[id_arr])
            if not balance:
                raise Exception(f"No {token_withdraw} balance on FastSet after deposit")

        if token_withdraw == "SET":
            balance = int(TokenAmount(amount=balance, wei=False).Ether)
            withdraw_amount = str(random.randint(1, int(int(balance) / 2) if int(balance) < 1000 else 500))
            withdraw_for_log = withdraw_amount
        else:
            balance = float(TokenAmount(amount=balance, wei=True).Ether)
            withdraw_amount = round(random.uniform(0.0001, balance if balance < 0.001 else 0.001), 5)
            withdraw_for_log = withdraw_amount
            withdraw_amount = TokenAmount(amount=withdraw_amount).Wei
            withdraw_amount = hex(withdraw_amount)

        logger.info(f"{self.user} | Start Bridge {withdraw_for_log} {token_withdraw} from FastSet to Sepolia")

        recipient = "set1la44katfwdhv9tqvskjrjc5cmy7ufjwvufwz4suuvazua5dtf4js08rgrz"
        tx_transfer = await self.fastset_client.transactions.build_token_transfer(
            recipient_address_set=recipient,
            amount_hex=withdraw_amount,
            token_id=bytes.fromhex(token_id.removeprefix("0x")),
        )
        signed_transfer = await self.fastset_client.transactions.sign(tx_transfer)
        transfer_cert = await self.fastset_client.transactions.submit(signed_transfer)
        raw_result = transfer_cert.raw if isinstance(transfer_cert, object) else {}
        success_obj = raw_result.get("Success", {}) if isinstance(raw_result, dict) else {}
        sig_pairs_lists = success_obj.get("signatures", [])
        signatures_transfer = []
        for pair in sig_pairs_lists:
            if isinstance(pair, list) and len(pair) == 2:
                r_lst, s_lst = pair
                r_bytes = bytes(r_lst)
                s_bytes = bytes(s_lst)
                signatures_transfer.append((r_bytes, s_bytes))
        resp_transfer = await self.fastset_client.transactions.evm_sign_certificate(
            signed_transfer,
            signatures=signatures_transfer,
        )
        transfer_hash = self.ethereum_signed_message_hash(transaction=bytes(resp_transfer["transaction"]))
        encoded_transfer_claim = bytes(resp_transfer.get("transaction", []))
        transfer_proof = resp_transfer.get("signature", "")
        transfer_claim_id = self.fastset_client.transactions.compute_claim_id(encoded_transfer_claim)

        external_address = self.evm_client.account.address

        claim_data_hex = self.build_withdraw_intent_varvar(
            token=evm_token_address, addr=self.evm_client.account.address, transfer_hash=transfer_hash
        )

        tx_claim = await self.fastset_client.transactions.build_external_claim(
            claim_data=bytes.fromhex(claim_data_hex[2:]),
            verifier_committee=[],
            verifier_quorum=0,
            signatures=[],
        )
        signed_claim = await self.fastset_client.transactions.sign(tx_claim)
        claim_cert = await self.fastset_client.transactions.submit(signed_claim)
        raw_intent = claim_cert.raw if isinstance(claim_cert, object) else {}
        success_intent = raw_intent.get("Success", {}) if isinstance(raw_intent, dict) else {}
        sig_pairs_intent = success_intent.get("signatures", [])
        signatures_intent: list[tuple[bytes, bytes]] = []
        for pair in sig_pairs_intent:
            if isinstance(pair, list) and len(pair) == 2:
                r_lst, s_lst = pair
                r_bytes = bytes(r_lst)
                s_bytes = bytes(s_lst)
                signatures_intent.append((r_bytes, s_bytes))
        resp_intent = await self.fastset_client.transactions.evm_sign_certificate(
            signed_claim,
            signatures=signatures_intent,
        )
        encoded_intent_claim = bytes(resp_intent.get("transaction", []))
        intent_proof = resp_intent.get("signature", "")
        intent_claim_id = self.fastset_client.transactions.compute_claim_id(encoded_intent_claim)

        relay_url = "https://omniset.fastset.xyz/ethereum-sepolia-relayer/relay"
        relay_resp = await self.fastset_client.transactions.relay_transfer(
            encoded_transfer_claim=encoded_transfer_claim,
            transfer_proof_hex=transfer_proof,
            transfer_claim_id_hex=transfer_claim_id,
            fastset_address_set=self.fastset_client.account.address,
            external_address_hex=external_address,
            encoded_intent_claim=encoded_intent_claim,
            intent_proof_hex=intent_proof,
            intent_claim_id_hex=intent_claim_id,
            external_token_address_hex=evm_token_address,
            relay_url=relay_url,
        )
        if isinstance(relay_resp, dict) and relay_resp.get("success"):
            logger.success(f"{self.user} bridge {withdraw_for_log} {token_withdraw} from FastSet to Sepolia confirmed")
            return relay_resp
        logger.error(f"{self.user} relay failed: {relay_resp}")
        raise Exception(f"{self.user} Relay Bridge failed")

    def ethereum_signed_message_hash(self, transaction: bytes) -> str:
        prefix = b"\x19Ethereum Signed Message:\n" + str(len(transaction)).encode()
        message = prefix + transaction
        return "0x" + keccak(message).hex()

    def build_withdraw_intent_varvar(self, token, addr, transfer_hash):
        template = (
            "0000000000000000000000000000000000000000000000000000000000000020"
            "{type_hash}"
            "0000000000000000000000000000000000000000000000000000000000000040"
            "0000000000000000000000000000000000000000000000000000000000000001"
            "0000000000000000000000000000000000000000000000000000000000000020"
            "0000000000000000000000000000000000000000000000000000000000000001"
            "0000000000000000000000000000000000000000000000000000000000000060"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000040"
            "000000000000000000000000{token}"
            "000000000000000000000000{addr}"
        )

        token_clean = token.lower().replace("0x", "").rjust(40, "0")
        addr_clean = addr.lower().replace("0x", "").rjust(40, "0")
        type_hash_clean = transfer_hash.lower().replace("0x", "").rjust(64, "0")

        final = template.format(type_hash=type_hash_clean, token=token_clean, addr=addr_clean)
        return "0x" + final

    @async_retry()
    async def bridge_to_fastet(self, token_deposit: str = "ETH"):
        balance = await self.evm_client.wallet.balance()
        if balance.Ether < 0.001:
            bridge = await self.gas_zip_bridge()
            if not bridge:
                raise Exception(f"Balance Sepolia < 0.001 ETH and can't bridge to Sepolia Network!")
            balance = await self.evm_client.wallet.balance()
        if token_deposit == "ETH":
            token = self.evm_client.w3.to_checksum_address("0x0000000000000000000000000000000000000000")
            balance = float(balance.Ether)
            amount = round(random.uniform(0.0001, balance / 2 if balance > 0.001 else 0.001), 3)
            amount = TokenAmount(amount=amount)
            data_amount = amount.Wei
        else:
            token = self.evm_client.w3.to_checksum_address("0xC6d2Bd6437655FBc6689Bfc987E09846aC4367Ed")
            balance = await self.evm_client.wallet.balance(token=token)
            if balance.Ether < 2:
                await self.bridge_to_evm(token_withdraw="SET")
                await asyncio.sleep(10, 30)
                balance = await self.evm_client.wallet.balance(token=token)
                if not balance:
                    raise Exception(f"{self.user} No {token_deposit} balance on Sepolia after withdraw from Fastet")
            balance = int(balance.Ether)
            amount = random.randint(int(balance / 2), balance)
            amount = TokenAmount(amount=amount)
            data_amount = int(amount.Ether)
            approve = await self.evm_client.transactions.approve(token=token, spender=BRIDGE_CONTRACT.address, amount=amount)
            receipt = await approve.wait_for_receipt(client=self.evm_client, timeout=300)

        logger.info(f"{self.user} | Start Bridge {amount.Ether} {token_deposit} from Sepolia to FastSet")
        c = await self.evm_client.contracts.get(contract_address=BRIDGE_CONTRACT)
        data = c.encode_abi("deposit", args=[token, data_amount, set_to_bytes(addr=self.fastset_client.account.address)])

        tx = await self.evm_client.transactions.sign_and_send(
            TxParams(
                to=c.address,
                data=data,
                value=amount.Wei if token_deposit == "ETH" else 0,
            )
        )

        await asyncio.sleep(random.randint(2, 4))
        receipt = await tx.wait_for_receipt(client=self.evm_client, timeout=300)

        if receipt and receipt["status"] == 1:
            logger.success(f"{self.user} success Bridge {amount.Ether} {token_deposit} from Sepolia to FastSet")
            return f"Success Bridge {amount.Ether} {token_deposit} from Sepolia to FastSet"

        return Exception(f"Failed to Bridge {amount.Ether} {token_deposit} from Sepolia to FastSet Network")

    @async_retry()
    async def gas_zip_bridge(self):
        logger.info(f"{self.user} start Gas Zip bridge to Sepolia ETH")
        client = await self.choose_available_client()
        if not client:
            return False
        params = {
            "from": self.evm_client.account.address,
            "to": self.evm_client.account.address,
        }
        balance = await client.wallet.balance()
        min_amount = 0.000005
        max_amount = 0.00001
        amount = random.uniform(min_amount, max_amount)
        amount = TokenAmount(amount)

        url_quote = f"https://backend.gas.zip/v2/quotes/{client.network.chain_id}/{amount.Wei}/11155111"
        response = await self.browser.get(url=url_quote, params=params)
        data = response.json()
        logger.debug(data)
        trans_data = data["contractDepositTxn"]["data"]
        to = data["contractDepositTxn"]["to"]
        value = data["contractDepositTxn"]["value"]
        tx_params = TxParams(to=to, data=trans_data, value=value)
        await client.transactions.sign_and_send(tx_params)

        await asyncio.sleep(random.randint(4, 6))
        return await self.wait_deposit(client=self.evm_client, start_balance=balance)

    async def choose_available_client(self):
        network_values = [value for key, value in Networks.__dict__.items() if isinstance(value, Network)]
        skip_network = [Networks.Ethereum, Networks.Sepolia]
        random.shuffle(network_values)
        for network in network_values:
            try:
                if network in skip_network or network.coin_symbol != "ETH":
                    continue
                logger.debug(network.name)
                client = Client(private_key=self.evm_client.account._private_key.hex(), network=network, proxy=self.evm_client.proxy)
                balance = await client.wallet.balance()
                if float(balance.Ether) > 0.00001:
                    return client
            except Exception as e:
                logger.warning(f"{self.user} can't check network {network.name} error: {e}")
                continue
        return None

    @async_retry()
    async def wait_deposit(self, start_balance: TokenAmount):
        timeout = 600
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"{self.user} deposit to {self.evm_client.network.name} did not arrive after {timeout} seconds")
                return False

            logger.info(f"{self.user} waiting for deposit to {self.evm_client.network.name} (elapsed: {int(elapsed)}s)")
            balance = await self.evm_client.wallet.balance()

            if start_balance.Wei < balance.Wei:
                logger.info(f"{self.user} deposit detected")
                return True

            await asyncio.sleep(5)
