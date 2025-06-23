import sys
from loguru import logger

# Удаляем стандартный обработчик
logger.remove()

# Добавляем новый обработчик с кастомным форматом
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Опционально: добавляем запись в файл
logger.add(
    "logs/app.log",
    rotation="500 MB",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO"
)
