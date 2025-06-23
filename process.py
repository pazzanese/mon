import sys
import os
import random
from pathlib import Path

# Добавляем путь к корневой директории проекта
ROOT_DIR = Path(__file__).parent
sys.path.append(str(ROOT_DIR))

# Импортируем настройки
from general_settings import ACCOUNT_TO_WORK
from src.modulse.runner import Runner
from utils.config import Config


class Process:
    def __init__(self):
        self.accounts = None
        self.get_accounts_data()

    def get_accounts_data(self):
        """Получает данные аккаунтов"""
        try:
            from utils.tools import get_accounts_data

            self.accounts = get_accounts_data()
        except Exception as e:
            print(f"❌ Ошибка получения данных аккаунтов: {str(e)}")
            # sys.exit(1)
            raise RuntimeError(f"Ошибка получения данных аккаунтов: {str(e)}")

    def get_accounts_to_work(self) -> list:
        """Определяет какие аккаунты нужно обработать"""
        try:
            # Если ACCOUNT_TO_WORK = 0, обрабатываем все аккаунты
            if ACCOUNT_TO_WORK == 0:
                return list(range(len(self.accounts[0])))

            # Если ACCOUNT_TO_WORK = [1, 3], обрабатываем диапазон
            if isinstance(ACCOUNT_TO_WORK, list) and len(ACCOUNT_TO_WORK) == 2:
                start, end = ACCOUNT_TO_WORK
                return list(range(start - 1, end))

            # Если ACCOUNT_TO_WORK = 1, 3, 5, обрабатываем конкретные аккаунты
            if isinstance(ACCOUNT_TO_WORK, (int, list)):
                if isinstance(ACCOUNT_TO_WORK, int):
                    return [ACCOUNT_TO_WORK - 1]
                return [acc - 1 for acc in ACCOUNT_TO_WORK]

            raise ValueError("Неверный формат ACCOUNT_TO_WORK")

        except Exception as e:
            print(f"❌ Ошибка определения аккаунтов для обработки: {str(e)}")
            # sys.exit(1)
            raise RuntimeError(f"Ошибка определения аккаунтов для обработки: {str(e)}")

    def start(self, exit_on_finish=True):
        """Запускает процесс обработки аккаунтов"""
        try:
            accounts_to_work = self.get_accounts_to_work()
            config = Config()  # Создаем экземпляр конфигурации

            for account_index in accounts_to_work:
                try:
                    account_name = self.accounts[0][account_index]
                    private_key = self.accounts[1][account_index]
                    proxy = self.accounts[2][account_index]

                    print(f"\n🔄 Обработка аккаунта {account_name}")

                    # Создаем и запускаем Runner для текущего аккаунта
                    runner = Runner(
                        account_name=account_name,
                        proxy=proxy,
                        private_key=private_key,
                        config=config,
                    )

                    # Запускаем выполнение заданий
                    runner.execute_tasks()

                except Exception as e:
                    print(f"❌ Ошибка при обработке аккаунта {account_name}: {str(e)}")
                    continue

            print("\n✅ Все задания выполнены. Программа завершает работу...")
            if exit_on_finish:
                sys.exit(0)  # Завершаем программу с кодом 0 (успешное завершение)
            return

        except Exception as e:
            print(f"❌ Ошибка в процессе выполнения: {str(e)}")
            # sys.exit(1)  # Завершаем программу с кодом 1 (ошибка)
            if exit_on_finish:
                sys.exit(1)
            else:
                raise


def main():
    process = Process()
    process.start()


if __name__ == "__main__":
    main()
