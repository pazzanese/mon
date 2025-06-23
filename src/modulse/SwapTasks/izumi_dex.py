import urllib3
import random

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
from typing import Dict, Optional, List, Tuple
from eth_account import Account
from web3 import Web3
from utils.networks import MonadRPC
from src.modulse.SwapTasks.constants import IZUMI_CONTRACT, IZUMI_ABI, IZUMI_TOKENS
from utils.constants import ERC20_ABI
from utils.config import Config
from decimal import Decimal
from utils.logger import logger
from general_settings import PAUSE_BETWEEN_SWAPS, PERCENTAGE_TO_SWAP, NUMBER_OF_SWAPS


class IzumiDex:
    def __init__(
        self, private_key: str, proxy: Optional[str] = None, config: Config = None
    ):
        self.web3 = Web3(
            Web3.HTTPProvider(
                MonadRPC,
                request_kwargs={
                    "proxies": {"http": f"http://{proxy}"},
                    "verify": False,
                    "timeout": 30,
                },
            )
        )
        self.account = Account.from_key(private_key)
        self.proxy = proxy
        self.router_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(IZUMI_CONTRACT), abi=IZUMI_ABI
        )
        self.config = config

    def get_gas_params(self) -> Dict[str, int]:
        latest_block = self.web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = self.web3.eth.max_priority_fee
        max_fee = base_fee + max_priority_fee

        gas_params = {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }
        return gas_params

    def convert_to_wei(self, amount: float, token: str) -> int:
        try:
            if token == "native":
                return int(Decimal(str(amount)) * Decimal(str(10 ** 18)))
            if token not in IZUMI_TOKENS:
                logger.error(f"IzumiDex: Токен {token} не найден в списке поддерживаемых токенов")
                return 0
            decimals = IZUMI_TOKENS[token]["decimals"]
            return int(Decimal(str(amount)) * Decimal(str(10 ** decimals)))
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка в convert_to_wei для {token}: {repr(e)}")
            return 0

    def convert_from_wei(self, amount: int, token: str) -> float:
        try:
            if token == "native":
                return float(Decimal(str(amount)) / Decimal(str(10 ** 18)))
            if token not in IZUMI_TOKENS:
                logger.error(f"IzumiDex: Токен {token} не найден в списке поддерживаемых токенов")
                return 0
            decimals = IZUMI_TOKENS[token]["decimals"]
            return float(Decimal(str(amount)) / Decimal(str(10 ** decimals)))
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка в convert_from_wei для {token}: {repr(e)}")
            return 0

    def get_tokens_with_balance(self) -> List[Tuple[str, float]]:
        tokens_with_balance = []

        # Проверяем баланс нативного токена (MON)
        try:
            native_balance = self.web3.eth.get_balance(self.account.address)
            if native_balance > 10**14:  # Больше 0.0001 MON
                native_amount = float(self.web3.from_wei(native_balance, "ether"))
                tokens_with_balance.append(("native", native_amount))
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка при получении баланса native: {repr(e)}")

        # Проверяем балансы остальных токенов
        for token in IZUMI_TOKENS:
            if token == "wmon":  # WMON обрабатывается отдельно
                continue
            try:
                token_contract = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(
                        IZUMI_TOKENS[token]["address"]
                    ),
                    abi=ERC20_ABI,
                )
                balance = token_contract.functions.balanceOf(
                    self.account.address
                ).call()

                min_amount = 10 ** (IZUMI_TOKENS[token]["decimals"] - 4)
                if balance >= min_amount:
                    decimals = IZUMI_TOKENS[token]["decimals"]
                    amount = float(Decimal(str(balance)) / Decimal(str(10**decimals)))
                    tokens_with_balance.append((token, amount))
            except Exception as e:
                logger.error(f"IzumiDex: Ошибка при получении баланса {token}: {repr(e)}")
                continue

        return tokens_with_balance

    def approve_token(self, token: str, amount: int) -> Optional[str]:
        try:
            if token not in IZUMI_TOKENS:
                logger.error(f"IzumiDex: Токен {token} не найден в списке поддерживаемых токенов")
                return None

            logger.info(f"IzumiDex: Начинаю approve для токена {token} на сумму {amount}")

            token_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(IZUMI_TOKENS[token]["address"]),
                abi=ERC20_ABI,
            )

            current_allowance = token_contract.functions.allowance(
                self.account.address, IZUMI_CONTRACT
            ).call()

            if current_allowance >= amount:
                logger.info(f"IzumiDex: Текущий allowance для {token} достаточен ({current_allowance} >= {amount})")
                return None

            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_params = self.get_gas_params()

            transaction = token_contract.functions.approve(
                IZUMI_CONTRACT, amount
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 100000,
                    "maxFeePerGas": gas_params["maxFeePerGas"],
                    "maxPriorityFeePerGas": gas_params["maxPriorityFeePerGas"],
                }
            )

            return self.execute_transaction(transaction)

        except Exception as e:
            logger.error(f"IzumiDex: Ошибка при approve токена {token}: {repr(e)}")
            return None

    def execute_transaction(self, tx_data: dict) -> Optional[str]:
        try:
            current_balance = self.web3.eth.get_balance(self.account.address)
            gas_price = self.web3.eth.gas_price
            gas_limit = tx_data.get("gas", 21000)

            required_balance = gas_price * gas_limit
            if tx_data.get("value", 0) > 0:
                required_balance += tx_data["value"]

            if current_balance < required_balance:
                logger.error(
                    f"IzumiDex: Недостаточно баланса. Требуется: {required_balance}, Доступно: {current_balance}"
                )
                return None

            signed_tx = self.web3.eth.account.sign_transaction(tx_data, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logger.info(f"IzumiDex: Транзакция отправлена: {tx_hash.hex()}")

            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            logger.success(f"IzumiDex: Транзакция подтверждена: {tx_hash.hex()}")
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка при выполнении транзакции: {repr(e)}")
            return None

    def swap(self, percentage_to_swap: float = None, type: str = "swap") -> list:
        try:
            tokens_with_balance = self.get_tokens_with_balance()
            if not tokens_with_balance:
                logger.error("IzumiDex: Нет токенов для свапа")
                return []

            tx_hashes = []

            if type == "collect":
                # Собираем все токены (кроме native и wmon) в native
                tokens_to_collect = [
                    (token, amount)
                    for token, amount in tokens_with_balance
                    if token not in ["native", "wmon"]
                ]
                if not tokens_to_collect:
                    logger.info("IzumiDex: Нет токенов для сбора в native")
                    return []
                random.shuffle(tokens_to_collect)
                for token, amount in tokens_to_collect:
                    amount_in = self.convert_to_wei(amount, token)
                    if amount_in == 0:
                        logger.error(f"IzumiDex: Некорректное количество для {token}")
                        continue
                    # Approve если нужно
                    if token != "native":
                        self.approve_token(token, amount_in)
                        time.sleep(random.randint(2, 5))
                    # Генерируем swap_data
                    swap_data = self.generate_swap_data(token, "native", amount_in, 0)
                    if not swap_data:
                        logger.error(f"IzumiDex: Не удалось сгенерировать swap_data для {token}")
                        continue
                    # Собираем multicall
                    multicall_tx = self.router_contract.functions.multicall(swap_data).build_transaction({
                        "from": self.account.address,
                        "nonce": self.web3.eth.get_transaction_count(self.account.address),
                        **self.get_gas_params(),
                        "gas": 500000,
                        "value": 0
                    })
                    tx_hash = self.execute_transaction(multicall_tx)
                    if tx_hash:
                        tx_hashes.append(tx_hash)
                        logger.success(f"IzumiDex: Успешно свапнуто {token} в native: {tx_hash}")
                    time.sleep(random.randint(PAUSE_BETWEEN_SWAPS[0], PAUSE_BETWEEN_SWAPS[1]))
                return tx_hashes
            else:
                num_swaps = random.randint(NUMBER_OF_SWAPS[0], NUMBER_OF_SWAPS[1])
                logger.info(f"IzumiDex: Количество свапов: {num_swaps}")
                for _ in range(num_swaps):
                    # Выбираем токен для свапа
                    token_in, amount = random.choice(tokens_with_balance)
                    if token_in == "native":
                        available_tokens = [t for t in IZUMI_TOKENS.keys() if t != "wmon"]
                    else:
                        available_tokens = [t for t in IZUMI_TOKENS.keys() if t not in [token_in, "wmon"]]
                    if not available_tokens:
                        logger.error(f"IzumiDex: Нет токенов для обмена с {token_in}")
                        continue
                    token_out = random.choice(available_tokens)
                    # Рандомизация процента для каждого свапа
                    if percentage_to_swap is None:
                        percentage = random.uniform(PERCENTAGE_TO_SWAP[0], PERCENTAGE_TO_SWAP[1])
                    else:
                        percentage = percentage_to_swap
                    logger.info(f"IzumiDex: % свапа: {round(percentage, 2)}%")
                    amount_in = int(self.convert_to_wei(amount, token_in) * percentage / 100)
                    if amount_in == 0:
                        logger.error(f"IzumiDex: Некорректное количество для {token_in}")
                        continue
                    # Approve если нужно
                    if token_in != "native":
                        self.approve_token(token_in, amount_in)
                        time.sleep(random.randint(2, 5))
                    # Генерируем swap_data
                    swap_data = self.generate_swap_data(token_in, token_out, amount_in, 0)
                    if not swap_data:
                        logger.error(f"IzumiDex: Не удалось сгенерировать swap_data для {token_in}")
                        continue
                    # Собираем multicall
                    multicall_tx = self.router_contract.functions.multicall(swap_data).build_transaction({
                        "from": self.account.address,
                        "nonce": self.web3.eth.get_transaction_count(self.account.address),
                        **self.get_gas_params(),
                        "gas": 500000,
                        "value": 0
                    })
                    tx_hash = self.execute_transaction(multicall_tx)
                    if tx_hash:
                        tx_hashes.append(tx_hash)
                        logger.success(f"IzumiDex: Успешно свапнуто {token_in} в {token_out}: {tx_hash}")
                    time.sleep(random.randint(PAUSE_BETWEEN_SWAPS[0], PAUSE_BETWEEN_SWAPS[1]))
                return tx_hashes
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка в swap: {repr(e)}")
            return []

    def estimate_gas(self, tx_data: dict) -> int:
        try:
            return self.web3.eth.estimate_gas(tx_data)
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка при оценке газа: {repr(e)}")
            return 0

    def _get_token_address(self, token: str) -> str:
        if token == "native":
            return IZUMI_TOKENS["wmon"]["address"]
        return IZUMI_TOKENS[token]["address"]

    def generate_swap_data(self, token_in: str, token_out: str, amount_in: int, min_amount_out: int) -> List[dict]:
        try:
            data = []
            recipient = self.account.address
            deadline = int(time.time() + 3600 * 6)  # 6 часов
            min_acquired = min_amount_out  # Обычно 0

            # Формируем path с учетом подстановки WMON вместо native
            path = (
                bytes.fromhex(self._get_token_address(token_in)[2:]) +
                bytes.fromhex(self._get_token_address(token_out)[2:])
            )

            swap_params = (
                path,
                recipient,
                amount_in,
                min_acquired,
                deadline
            )
            swap_data = self.router_contract.encode_abi("swapAmount", [swap_params])
            data.append(swap_data)

            # Если получаем native (MON), добавляем unwrapWETH9
            if token_out == "native":
                unwrap_data = self.router_contract.encode_abi(
                    "unwrapWETH9",
                    [0, recipient]
                )
                data.append(unwrap_data)

            # Добавляем refundETH всегда
            refund_data = self.router_contract.encode_abi("refundETH", [])
            data.append(refund_data)

            return data
        except Exception as e:
            logger.error(f"IzumiDex: Ошибка при генерации swap_data: {repr(e)}")
            return [] 