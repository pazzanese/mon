from decimal import Decimal
from typing import Dict, List, Optional
from web3 import Web3
from web3.exceptions import ContractLogicError
from tabulate import tabulate
from loguru import logger
from eth_account import Account

from utils.networks import MonadRPC
from .constants import CONTRACT_ADDRESS, CONTRACT_ABI, TOKENS


class BalanceChecker:
    def __init__(self, private_key: str, proxy: Optional[str] = None):
        """
        Инициализация BalanceChecker

        Args:
            private_key (str): Приватный ключ кошелька
            proxy (Optional[str]): Прокси для подключения
        """
        self.private_key = private_key
        self.proxy = proxy
        self.account = Account.from_key(private_key)

        # Инициализация Web3 и контракта
        self.web3 = Web3(
            Web3.HTTPProvider(
                MonadRPC,
                request_kwargs={
                    "proxies": {"http": f"http://{self.proxy}"} if self.proxy else None,
                    "verify": False,
                },
            )
        )

        if not self.web3.is_connected():
            raise ConnectionError("Не удалось подключиться к Monad RPC")

        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI
        )

    def get_balances(self, wallets: List[str]) -> List[Dict]:
        """
        Получение балансов для списка кошельков

        Args:
            wallets (List[str]): Список адресов кошельков

        Returns:
            List[Dict]: Список словарей с балансами
        """
        try:
            # Подготовка данных
            wallet_addresses = [Web3.to_checksum_address(wallet) for wallet in wallets]
            token_addresses = [
                Web3.to_checksum_address(TOKENS[token]["address"])
                for token in TOKENS.keys()
            ]

            # Получение балансов через контракт
            balances = self.contract.functions.balances(
                wallet_addresses, token_addresses
            ).call()

            # Обработка результатов
            results = []
            tokens_count = len(TOKENS)

            for i, wallet in enumerate(wallet_addresses):
                wallet_balances = {"wallet": wallet, "index": i + 1}

                # Получаем балансы для текущего кошелька
                wallet_balances_list = balances[
                    i * tokens_count : (i + 1) * tokens_count
                ]

                for j, token in enumerate(TOKENS.keys()):
                    balance = Decimal(wallet_balances_list[j]) / Decimal(
                        10 ** TOKENS[token]["decimals"]
                    )
                    # Используем фиксированное количество знаков после запятой (4)
                    wallet_balances[token] = f"{float(balance):.4f}"

                results.append(wallet_balances)

            return results

        except ContractLogicError as e:
            logger.error(f"Ошибка контракта при получении балансов: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении балансов: {e}")
            raise

    def display_balances(self, results: List[Dict]):
        """
        Отображение результатов в виде таблицы

        Args:
            results (List[Dict]): Список словарей с балансами
        """
        try:
            # Подготовка заголовков
            headers = ["№", "Wallet"] + list(TOKENS.keys())

            # Подготовка данных
            table_data = []
            for result in results:
                row = [result["index"], result["wallet"]]
                for token in TOKENS.keys():
                    row.append(result[token])
                table_data.append(row)

            # Вывод таблицы
            print("\nБалансы токенов:")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))

        except Exception as e:
            logger.error(f"Ошибка при отображении балансов: {e}")
            raise

    async def run(self, wallets: List[str]):
        """
        Основной метод для проверки балансов

        Args:
            wallets (List[str]): Список адресов кошельков
        """
        try:
            logger.info("Начало проверки балансов")

            # Получение балансов
            results = self.get_balances(wallets)

            # Отображение результатов
            self.display_balances(results)

            logger.success("Проверка балансов завершена")

        except Exception as e:
            logger.error(f"Ошибка при выполнении проверки балансов: {e}")
            raise
