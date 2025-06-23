# ---------------GENERAL SETTINGS---------------


SOFTWARE_MODE = 1  # 0 - последовательный запуск / 1 - параллельный запуск
ACCOUNT_IN_STERAM = 0  # Количество аккаунтов в потоке при SOFTWARE_MODE = 1
ACCOUNT_TO_WORK = 1  # 0 / 3 / 3, 20, 31 / [3, 20]
TELEGRAM_NOTIFICATIONS = False

# SLEPPING SETTINGS
SLEEP_MODE = False  # Включает сон после каждого модуля и аккаунта
SLEEP_TIME_MODULES = [5, 10]  # (минимум, максимум) секунд | Время сна между модулями.
SLEEP_TIME_ACCOUNTS = (60, 120) # (минимум, максимум) секунд | Время сна между аккаунтами.


PAUSE_BETWEEN_SWAPS = (7, 15)  # (минимум, максимум) секунд | Время сна между свапами
PERCENTAGE_TO_SWAP = (2, 4)  # Процент баланса для свапа
NUMBER_OF_SWAPS = (1, 3)  # Количество свапов
# RETRY SETTINGS
MAXIMUM_RETRY = 20  # Количество повторений при ошибках
SLEEP_TIME_RETRY = (5, 10)  # (минимум, максимум) секунд | Время сна после очередного повторения


# DATA SETTINGS
EXCEL_PASSWORD = False  # Password for Excel file, leave empty if no password
EXCEL_PAGE_NAME = "Monad"
EXCEL_FILE_PATH = "./data/account_data.xlsx"
# Путь к файлу с аккаунтами для второго модуля

# TELEGRAM SETTINGS
API_TOKEN = ""  # Вставьте сюда токен вашего бота
ADMIN_ID =   # Ваш Telegram user_id для ограничения доступа

TASKS = ["IzumiDex"]
########################### TASKS ###########################
# IzumiDex
# BeanDex
# collect_izumi
# collect_bean

