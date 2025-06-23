from general_settings import TASKS, SLEEP_TIME_MODULES
from src.modulse.SwapTasks.bean_dex import BeanDex
from src.modulse.test2.test2 import Test2
from utils.config import Config
from utils.logger import logger
import random
import time
from src.modulse.SwapTasks.izumi_dex import IzumiDex


class Runner:
    def __init__(
        self,
        account_name: str,
        proxy: str,
        private_key: str,
        config: Config,
    ):
        self.account_name = account_name
        self.proxy = proxy
        self.private_key = private_key
        self.config = config

    def check_tasks(self) -> bool:
        if not TASKS:
            logger.warning(f"Аккаунт {self.account_name}: Нет доступных заданий в TASKS")
            return False

        logger.info(f"Аккаунт {self.account_name}: Найдено {len(TASKS)} заданий")
        return True

    def execute_tasks(self):

        if not self.check_tasks():
            return

        # Создаем копию списка заданий и перемешиваем
        tasks = TASKS.copy()
        random.shuffle(tasks)

        for task in tasks:
            try:
                logger.info(
                    f"Аккаунт {self.account_name}: Начало выполнения задания {task}"
                )

                # Создаем экземпляр соответствующего класса
                if task == "BeanDex":
                    module = BeanDex(
                        private_key=self.private_key,
                        proxy=self.proxy,
                        config=self.config,
                    )
                    swap_balance = module.swap(type="swap")
                    logger.info(
                        f"Аккаунт {self.account_name}: Свапы в задании {task}: {swap_balance}"
                    )
                elif task == "IzumiDex":
                    module = IzumiDex(
                        private_key=self.private_key,
                        proxy=self.proxy,
                        config=self.config,
                    )
                    swap_balance = module.swap(type="swap")
                    logger.info(
                        f"Аккаунт {self.account_name}: Свапы в задании {task}: {swap_balance}"
                    )
                elif task == "collect_bean":
                    module = BeanDex(
                        private_key=self.private_key,
                        proxy=self.proxy,
                        config=self.config,
                    )
                    collect_balance = module.swap(percentage_to_swap=99, type="collect")
                    logger.info(
                        f"Аккаунт {self.account_name}: Баланс MON в задании {task}: {collect_balance}"
                    )
                elif task == "collect_izumi":
                    module = IzumiDex(
                        private_key=self.private_key,
                        proxy=self.proxy,
                        config=self.config,
                    )
                    collect_balance = module.swap(percentage_to_swap=99, type="collect")
                    logger.info(
                        f"Аккаунт {self.account_name}: Баланс MON в задании {task}: {collect_balance}"
                    )
                else:
                    logger.error(f"Аккаунт {self.account_name}: Задание '{task}' не найдено. Проверьте general_settings.TASKS.")
                    continue
                logger.success(
                    f"Аккаунт {self.account_name}: Задание {task} успешно выполнено"
                )

                # Случайная задержка между заданиями
                if task != tasks[-1]:  # Если это не последнее задание
                    sleep_time = random.randint(
                        SLEEP_TIME_MODULES[0], SLEEP_TIME_MODULES[1]
                    )
                    logger.info(
                        f"Аккаунт {self.account_name}: Ожидание {sleep_time} секунд перед следующим заданием"
                    )
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(
                    f"Аккаунт {self.account_name}: Ошибка при выполнении задания {task}: {repr(e)}"
                )
                continue
