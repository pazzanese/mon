import random
import io
import msoffcrypto
import asyncio
import pandas as pd
import sys
import os

from termcolor import cprint
from getpass import getpass
from msoffcrypto.exceptions import DecryptionError, InvalidKeyError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from general_settings import (
    SLEEP_TIME_MODULES,
    EXCEL_PASSWORD,
    EXCEL_FILE_PATH,
    EXCEL_PAGE_NAME,
)

from eth_account import Account
from src.modulse.balance_checker.balance_checker import BalanceChecker

async def sleep(self, min_time=SLEEP_TIME_MODULES[0], max_time=SLEEP_TIME_MODULES[1]):
    duration = random.randint(min_time, max_time)
    print()
    self.logger_msg(*self.client.acc_info, msg=f"💤 Sleeping for {duration} seconds")
    await asyncio.sleep(duration)


def get_accounts_data():
    try:
        decrypted_data = io.BytesIO()
        with open(EXCEL_FILE_PATH, "rb") as file:
            if EXCEL_PASSWORD:
                cprint("⚔️ Введите пароль degen", color="light_blue")
                password = getpass()
                office_file = msoffcrypto.OfficeFile(file)

                try:
                    office_file.load_key(password=password)
                except msoffcrypto.exceptions.DecryptionError:
                    cprint(
                        "\n⚠️ Неверный пароль для расшифровки Excel файла! ⚠️",
                        color="light_red",
                        attrs=["blink"],
                    )
                    raise DecryptionError("Incorrect password")

                try:
                    office_file.decrypt(decrypted_data)
                except msoffcrypto.exceptions.InvalidKeyError:
                    cprint(
                        "\n⚠️ Неверный пароль для расшифровки Excel файла! ⚠️",
                        color="light_red",
                        attrs=["blink"],
                    )
                    raise InvalidKeyError("Incorrect password")

                except msoffcrypto.exceptions.DecryptionError:
                    cprint(
                        "\n⚠️ Сначала установите пароль на ваш Excel файл! ⚠️",
                        color="light_red",
                        attrs=["blink"],
                    )
                    raise DecryptionError("Excel without password")

                office_file.decrypt(decrypted_data)

                try:
                    wb = pd.read_excel(decrypted_data, sheet_name=EXCEL_PAGE_NAME)
                except ValueError as error:
                    cprint("\n⚠️ Неверное имя страницы! ⚠️", color="light_red", attrs=["blink"])
                    raise ValueError(f"{error}")
            else:
                try:
                    wb = pd.read_excel(file, sheet_name=EXCEL_PAGE_NAME)
                except ValueError as error:
                    cprint("\n⚠️ Неверное имя страницы! ⚠️", color="light_red", attrs=["blink"])
                    raise ValueError(f"{error}")

            accounts_data = {}
            for index, row in wb.iterrows():
                account_name = row["Name"]
                private_key = row["Private Key"]
                proxy = row["Proxy"]
                email_address = row["Email Address"]
                email_password = row["Email Password"]

                accounts_data[int(index) + 1] = {
                    "account_number": account_name,
                    "private_key": private_key,
                    "proxy": proxy,
                    "email_address": email_address,
                    "email_password": email_password,
                }

            acc_names, private_keys, proxies, email_addresses, email_passwords = (
                [],
                [],
                [],
                [],
                [],
            )
            for k, v in accounts_data.items():
                acc_names.append(
                    v["account_number"]
                    if isinstance(v["account_number"], (int, str))
                    else None
                )
                private_keys.append(v["private_key"])
                proxies.append(v["proxy"] if isinstance(v["proxy"], str) else None)
                email_addresses.append(
                    v["email_address"] if isinstance(v["email_address"], str) else None
                )
                email_passwords.append(
                    v["email_password"]
                    if isinstance(v["email_password"], str)
                    else None
                )

            acc_names = [str(item) for item in acc_names if item is not None]
            proxies = [item for item in proxies if item is not None]
            email_addresses = [item for item in email_addresses if item is not None]
            email_passwords = [item for item in email_passwords if item is not None]

            return acc_names, private_keys, proxies, email_addresses, email_passwords
    except (DecryptionError, InvalidKeyError, DecryptionError, ValueError):
        sys.exit()

    except ImportError:
        cprint(
            f"\nВы уверены, что EXCEL_PASSWORD указан в general_settings.py?",
            color="light_red",
        )
        sys.exit()

    except Exception as error:
        cprint(
            f"\nОшибка в функции <get_accounts_data>! Ошибка: {error}\n",
            color="light_red",
        )
        sys.exit()

async def check_balances():
    """Функция для проверки балансов"""
    print("\nПроверка балансов кошельков")
    
    # Получаем данные всех аккаунтов
    accounts_data = get_accounts_data()
    if not accounts_data:
        print("Нет доступных аккаунтов")
        return
    
    # Получаем адреса кошельков из приватных ключей
    wallets = []
    for private_key in accounts_data[1]:  # Берем список приватных ключей
        account = Account.from_key(private_key)
        wallets.append(account.address)
    
    # Используем первый аккаунт для проверки балансов
    private_key = accounts_data[1][0]  # Первый приватный ключ
    proxy = accounts_data[2][0]  # Первый прокси
    
    checker = BalanceChecker(private_key, proxy)
    await checker.run(wallets)
