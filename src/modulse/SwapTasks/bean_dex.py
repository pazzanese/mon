import urllib3
import random

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
from typing import Dict, Optional, List, Tuple
from eth_account import Account
from web3 import Web3
from utils.networks import MonadRPC
from src.modulse.SwapTasks.constants import BEAN_CONTRACT, BEAN_ABI, BEAN_TOKENS
from utils.constants import ERC20_ABI
from utils.config import Config
from decimal import Decimal
from utils.logger import logger
from general_settings import PAUSE_BETWEEN_SWAPS, PERCENTAGE_TO_SWAP, NUMBER_OF_SWAPS


class BeanDex:
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
            address=self.web3.to_checksum_address(BEAN_CONTRACT), abi=BEAN_ABI
        )
        self.config = config


    def get_gas_params(self) -> Dict[str, int]:
        # try:
        latest_block = self.web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = self.web3.eth.max_priority_fee
        max_fee = base_fee + max_priority_fee

        gas_params = {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

        return gas_params


    def get_token_balance(self, token: str) -> float:
        try:
            if token == "native":
                balance_wei = self.web3.eth.get_balance(self.account.address)
                return float(self.web3.from_wei(balance_wei, "ether"))

            token_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(BEAN_TOKENS[token]["address"]),
                abi=ERC20_ABI,
            )
            balance = token_contract.functions.balanceOf(self.account.address).call()
            decimals = BEAN_TOKENS[token]["decimals"]
            amount = float(Decimal(str(balance)) / Decimal(str(10**decimals)))
            return amount

        except Exception as e:
            logger.error(f"Failed to get {token} balance: {repr(e)}")
            return 0

    def get_tokens_with_balance(
        self,
    ) -> List[Tuple[str, float]]:
        # Получение токенов с не нулевым балансом. Иначе возращает пустой список.
        """Get list of tokens with non-zero balances."""
        tokens_with_balance = []

        # Check native token balance
        native_balance = self.web3.eth.get_balance(self.account.address)
        if native_balance > 0:
            native_amount = float(self.web3.from_wei(native_balance, "ether"))
            tokens_with_balance.append(("native", native_amount))

        # Check other tokens
        for token in BEAN_TOKENS:
            try:
                token_contract = self.web3.eth.contract(
                    address=self.web3.to_checksum_address(
                        BEAN_TOKENS[token]["address"]
                    ),
                    abi=ERC20_ABI,
                )
                balance = token_contract.functions.balanceOf(
                    self.account.address
                ).call()

                if balance > 0:
                    decimals = BEAN_TOKENS[token]["decimals"]
                    amount = float(Decimal(str(balance)) / Decimal(str(10**decimals)))
                    tokens_with_balance.append((token, amount))

            except Exception as e:
                logger.error(f"Failed to get balance for {token}: {repr(e)}")
                continue

        return tokens_with_balance

    def approve_token(self, token: str, amount: int) -> Optional[str]:
        try:
            # Проверяем существование токена
            if token not in BEAN_TOKENS:
                logger.error(f"BeanDex: Token {token} не найден в списке поддерживаемых токенов")
                return None

            logger.info(
                f"BeanDex: Начинаю approve для токена {token} на сумму {amount}"
            )

            # Создаем контракт токена
            token_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(BEAN_TOKENS[token]["address"]),
                abi=ERC20_ABI,
            )

            logger.info(f"BeanDex: Контракт токена {token} успешно создан")

            # Проверяем текущий апрув
            current_allowance = token_contract.functions.allowance(
                self.account.address, BEAN_CONTRACT
            ).call()

            # Если текущий апрув достаточен, не делаем новый
            if current_allowance >= amount:
                logger.info(
                    f"BeanDex: Текущий allowance для {token} достаточен ({current_allowance} >= {amount})"
                )
                return None

            logger.info(
                f"BeanDex: Текущий allowance для {token}: {current_allowance}, требуется: {amount}"
            )
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            # Получаем параметры газа
            gas_params = self.get_gas_params()

            # Создаем транзакцию для апрува
            transaction = token_contract.functions.approve(
                BEAN_CONTRACT, amount
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 100000,  # Лимит газа для апрува
                    "maxFeePerGas": gas_params[
                        "maxFeePerGas"
                    ],  # Максимальная цена газа
                    "maxPriorityFeePerGas": gas_params[
                        "maxPriorityFeePerGas"
                    ],  # Приоритетная цена газа
                }
            )

            # Отправляем транзакцию через execute_transaction
            return self.execute_transaction(transaction)

        except Exception as e:
            logger.error(f"BeanDex: Ошибка при approve токена {token}: {repr(e)}")
            return None

    def execute_transaction(self, tx_data: dict) -> str:
        """
        Выполняет транзакцию и ждет подтверждения

        Args:
            tx_data (dict): Данные транзакции

        Returns:
            str: Хеш транзакции
        """
        try:
            # Проверяем баланс
            current_balance = self.web3.eth.get_balance(self.account.address)
            gas_price = self.web3.eth.gas_price
            gas_limit = tx_data.get("gas", 21000)

            required_balance = gas_price * gas_limit
            if tx_data.get("value", 0) > 0:
                required_balance += tx_data["value"]

            if current_balance < required_balance:
                logger.error(
                    f"BeanDex: Недостаточно баланса. Требуется: {required_balance}, Доступно: {current_balance}"
                )
                return None

            # Подписываем транзакцию
            signed_tx = self.web3.eth.account.sign_transaction(
                tx_data, self.account.key
            )

            # Отправляем подписанную транзакцию, используя raw_transaction
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Ждем подтверждения с таймаутом
            receipt = self.web3.eth.wait_for_transaction_receipt(
                tx_hash, poll_latency=2, timeout=120
            )

            if receipt["status"] == 1:
                logger.info(f"BeanDex: Транзакция успешна: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                logger.error(f"BeanDex: Транзакция не удалась: {tx_hash.hex()}")
                return None

        except Exception as e:
            logger.error(f"BeanDex: Ошибка при отправке транзакции: {repr(e)}")
            return None

    def generate_swap_data(
        self, token_in: str, token_out: str, amount_in: int, min_amount_out: int
    ) -> Dict:
        """
        Генерация данных для транзакции обмена токенов

        Args:
            token_in: Символ входящего токена
            token_out: Символ исходящего токена
            amount_in: Количество входящего токена
            min_amount_out: Минимальное количество исходящего токена

        Returns:
            Dict: Данные для транзакции
        """
        try:
            # Проверяем, не пытаемся ли мы менять токен сам на себя
            if token_in == token_out:
                logger.error(f"BeanDex: Нельзя обменять токен {token_in} сам на себя")
                return {}

            logger.info(
                f"BeanDex: Генерация данных для свапа {token_in} -> {token_out}"
            )

            # Устанавливаем временной лимит для транзакции
            current_time = int(time.time())
            deadline = current_time + 1800  # дедлайн через 30 минут


            # Создаем путь обмена токенов
            path = []

            # Обмен нативного токена (MON) на другой токен
            if token_in == "native":
                if token_out == "wmon":
                    # Прямой обмен MON -> WMON (wrap)
                    path = [BEAN_TOKENS[token_out]["address"]]
                    logger.info("BeanDex: Direct MON -> WMON (wrap) swap")
                else:
                    # Через промежуточный WMON
                    path = [
                        BEAN_TOKENS["wmon"]["address"],
                        BEAN_TOKENS[token_out]["address"],
                    ]
                    logger.info(f"BeanDex: MON -> {token_out} swap through WMON")

            # Обмен токена на нативный (MON)
            elif token_out == "native":
                if token_in == "wmon":
                    # Прямой обмен WMON -> MON (unwrap)
                    path = [BEAN_TOKENS[token_in]["address"]]
                    logger.info("BeanDex: Direct WMON -> MON (unwrap) swap")
                else:
                    # Через промежуточный WMON
                    path = [
                        BEAN_TOKENS[token_in]["address"],
                        BEAN_TOKENS["wmon"]["address"],
                    ]
                    logger.info(f"BeanDex: {token_in} -> MON swap through WMON")

            # Обмен между токенами
            else:
                if token_in == "wmon":
                    # Прямой обмен WMON -> другой токен
                    path = [
                        BEAN_TOKENS[token_in]["address"],
                        BEAN_TOKENS[token_out]["address"],
                    ]
                    logger.info(f"BeanDex: Direct WMON -> {token_out} swap")
                elif token_out == "wmon":
                    # Прямой обмен токен -> WMON
                    path = [
                        BEAN_TOKENS[token_in]["address"],
                        BEAN_TOKENS[token_out]["address"],
                    ]
                    logger.info(f"BeanDex: Direct {token_in} -> WMON swap")
                else:
                    # Через промежуточный WMON
                    path = [
                        BEAN_TOKENS[token_in]["address"],
                        BEAN_TOKENS["wmon"]["address"],
                        BEAN_TOKENS[token_out]["address"],
                    ]
                    logger.info(f"BeanDex: {token_in} -> {token_out} swap through WMON")

            #logger.info(f"BeanDex: Swap path: {' -> '.join(path)}")

            # Определяем метод обмена и значение value
            if token_in == "native":
                swap_method = self.router_contract.functions.swapExactETHForTokens(
                    min_amount_out, path, self.account.address, deadline
                )
                value = amount_in
            elif token_out == "native":
                swap_method = self.router_contract.functions.swapExactTokensForETH(
                    amount_in, min_amount_out, path, self.account.address, deadline
                )
                value = 0
            else:
                swap_method = self.router_contract.functions.swapExactTokensForTokens(
                    amount_in, min_amount_out, path, self.account.address, deadline
                )
                value = 0

            # Оцениваем газ для транзакции
            gas_estimate = swap_method.estimate_gas(
                {"from": self.account.address, "value": value}
            )

            # Добавляем 30% к оценке газа для надежности
            gas_limit = int(gas_estimate * 1.3)

            # Создаем транзакцию
            tx_data = swap_method.build_transaction(
                {
                    "from": self.account.address,
                    "value": value,
                    "gas": gas_limit,  # Используем gas_limit вместо gas_estimate
                    "nonce": self.web3.eth.get_transaction_count(self.account.address),
                    "maxFeePerGas": self.get_gas_params()["maxFeePerGas"],
                    "maxPriorityFeePerGas": self.get_gas_params()[
                        "maxPriorityFeePerGas"
                    ],
                }
            )

            return tx_data

        except Exception as e:
            logger.error(f"BeanDex: Error generating swap data: {repr(e)}")
            return {}

    def swap(self, percentage_to_swap: float = None, type: str = "swap") -> list:
        try:
            tokens_with_balance = self.get_tokens_with_balance()
            if not tokens_with_balance:
                raise ValueError("BeanDex: No tokens available for swap")

            if type == "collect":
                # Фильтруем токены, исключая native и wmon
                tokens_to_collect = [
                    (token, amount)
                    for token, amount in tokens_with_balance
                    if token not in ["native", "wmon"]
                ]

                if not tokens_to_collect:
                    logger.info("BeanDex: No tokens to collect to MON")
                    return None

                logger.info(
                    f"BeanDex: Starting token collection to MON: {tokens_to_collect}"
                )

                random.shuffle(tokens_to_collect)

                for token, amount in tokens_to_collect:
                    try:
                        # Проверяем, является ли это последним токеном
                        is_last_token = token == tokens_to_collect[-1][0]

                        # Получаем адрес токена и его decimals
                        token_address = BEAN_TOKENS[token]["address"]
                        decimals = BEAN_TOKENS[token]["decimals"]

                        # Конвертируем amount в wei
                        amount_wei = int(amount * (10**decimals))

                        # Проверяем allowance
                        token_contract = self.web3.eth.contract(
                            address=self.web3.to_checksum_address(token_address),
                            abi=ERC20_ABI,
                        )
                        allowance = token_contract.functions.allowance(
                            self.account.address, BEAN_CONTRACT
                        ).call()

                        # Если allowance недостаточно, делаем approve
                        if allowance < amount_wei:
                            logger.info(f"BeanDex: Approving {token}")
                            self.approve_token(token, amount_wei)

                            # Добавляем случайную паузу после approve, если это не последний токен
                            if not is_last_token:
                                pause = random.randint(
                                    PAUSE_BETWEEN_SWAPS[0], PAUSE_BETWEEN_SWAPS[1]
                                )
                                logger.info(
                                    f"BeanDex: Pause {pause} seconds after approve"
                                )
                                time.sleep(pause)

                        # Генерируем данные для свапа
                        swap_data = self.generate_swap_data(
                            token_in=token,
                            token_out="native",
                            amount_in=amount_wei,
                            min_amount_out=0,  # TODO: Добавить расчет min_amount_out
                        )

                        if not swap_data:
                            logger.error(
                                f"BeanDex: Failed to generate swap data for {token}"
                            )
                            continue

                        # Выполняем свап
                        tx_hash = self.execute_transaction(swap_data)
                        if tx_hash:
                            logger.success(
                                f"BeanDex: Successfully swapped {token} to MON: {tx_hash}"
                            )
                        else:
                            logger.error(f"BeanDex: Failed to swap {token} to MON")

                        # Добавляем случайную паузу между свапами
                        pause = random.randint(
                            PAUSE_BETWEEN_SWAPS[0], PAUSE_BETWEEN_SWAPS[1]
                        )
                        logger.info(f"BeanDex: Pause {pause} seconds before next swap")
                        time.sleep(pause)

                    except Exception as e:
                        error_message = (
                            repr(e).encode("utf-8", errors="ignore").decode("utf-8")
                        )
                        logger.error(
                            f"BeanDex: Error collecting {token}: {error_message}"
                        )
                        continue

                return None
            else:  # режим swap
                num_swaps = random.randint(NUMBER_OF_SWAPS[0], NUMBER_OF_SWAPS[1])
                logger.info(f"BeanDex: Количество свапов: {num_swaps}")
                tx_hashes = []
                for i in range(num_swaps):
                    # Генерируем новый процент для каждого свапа
                    percentage_to_swap = random.uniform(
                        PERCENTAGE_TO_SWAP[0], PERCENTAGE_TO_SWAP[1]
                    )
                    logger.info(f"BeanDex: % свапа: {round(percentage_to_swap, 2)}%")

                    # 1. Выбор входного токена
                    token_in, amount_in = random.choice(tokens_with_balance)
                    logger.info(
                        f"BeanDex: Selected input token {token_in} with balance {amount_in}"
                    )

                    # 2. Определение доступных токенов для обмена
                    available_tokens = []
                    if token_in == "native":
                        available_tokens = [
                            token for token in BEAN_TOKENS.keys() if token != "wmon"
                        ]
                    else:
                        available_tokens = ["native"] + [
                            token
                            for token in BEAN_TOKENS.keys()
                            if token not in [token_in, "wmon"]
                        ]

                    if not available_tokens:
                        logger.error("BeanDex: No available tokens for swap")
                        continue

                    token_out = random.choice(available_tokens)
                    logger.info(f"BeanDex: Selected output token {token_out}")

                    # 4. Расчет количества для обмена
                    if token_in == "native":
                        amount_wei = int(amount_in * (10**18))
                        swap_amount_wei = int(amount_wei * percentage_to_swap / 100)
                        swap_amount = float(swap_amount_wei / (10**18))
                    else:
                        decimals = BEAN_TOKENS[token_in]["decimals"]
                        amount_wei = int(amount_in * (10**decimals))
                        swap_amount_wei = int(amount_wei * percentage_to_swap / 100)
                        swap_amount = float(swap_amount_wei / (10**decimals))

                    logger.info(f"BeanDex: Swap amount: {swap_amount} {token_in}")

                    # 5. Approve для не-нативных токенов
                    if token_in != "native":
                        logger.info(f"BeanDex: Approving {token_in}")
                        self.approve_token(token_in, swap_amount_wei)
                        pause = random.randint(5, 10)
                        logger.info(f"BeanDex: Pause {pause} seconds after approve")
                        time.sleep(pause)

                    # 6. Выполнение обмена
                    swap_data = self.generate_swap_data(
                        token_in=token_in,
                        token_out=token_out,
                        amount_in=swap_amount_wei,
                        min_amount_out=0,
                    )

                    if not swap_data:
                        logger.error("BeanDex: Failed to generate swap data")
                        continue

                    tx_hash = self.execute_transaction(swap_data)
                    if tx_hash:
                        logger.success(
                            f"BeanDex: Successfully swapped {token_in} to {token_out}: {tx_hash}"
                        )
                        tx_hashes.append(tx_hash)
                    else:
                        logger.error(
                            f"BeanDex: Failed to swap {token_in} to {token_out}"
                        )

                    # Пауза между свапами
                    pause = random.randint(
                        PAUSE_BETWEEN_SWAPS[0], PAUSE_BETWEEN_SWAPS[1]
                    )
                    logger.info(f"BeanDex: Pause {pause} seconds before next swap")
                    time.sleep(pause)
                return tx_hashes

        except Exception as e:
            logger.error(f"BeanDex: Ошибка при выполнении свапа: {repr(e)}")
            return []
