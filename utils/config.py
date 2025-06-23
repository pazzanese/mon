class Config:
    def __init__(self):
        # Базовые настройки
        self.retry_count = 3
        self.timeout = 30
        self.max_attempts = 5

        # Настройки для работы с сетью
        self.network_settings = {
            "gas_limit": 300000,
            "gas_price": 1,
            "max_priority_fee": 1,
        }

        # Настройки для транзакций
        self.transaction_settings = {
            "min_amount": 0.001,
            "max_amount": 0.1,
            "slippage": 1,  # 1%
        }

        # Настройки для логирования
        self.logging_settings = {
            "level": "INFO",
            "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        }
