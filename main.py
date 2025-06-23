import sys
import os
from pathlib import Path

# Добавляем путь к корневой директории проекта
ROOT_DIR = Path(__file__).parent
sys.path.append(str(ROOT_DIR))
sys.path.append(str(ROOT_DIR / "src"))  # Добавляем путь к src

from process import Process
from src.modulse.balance_checker.balance_checker import BalanceChecker
from config import ACCOUNT_NAMES, PRIVATE_KEYS, PROXIES
from utils.tools import get_accounts_data, check_balances  # Импортирую check_balances из tools
from eth_account import Account
import asyncio



def print_menu():
    """Выводит меню программы"""
    menu = """
МЕНЮ ПРОГРАММЫ

1. Запуск главного процесса
2. Проверка балансов
0. Выход из программы
"""
    print(menu)


def main():
    while True:
        print_menu()
        choice = input("Выберите пункт меню: ")

        if choice == "1":
            process = Process()
            process.start()
        elif choice == "2":
            asyncio.run(check_balances())
        elif choice == "0":
            print("Выход из программы...")
            break
        else:
            print("Неверный выбор. Попробуйте снова.")


if __name__ == "__main__":
    main()
