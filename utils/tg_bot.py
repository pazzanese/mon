import sys
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from general_settings import API_TOKEN, ADMIN_ID

# Добавляю путь к корню проекта для корректного импорта process
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from process import Process
from utils.tools import check_balances

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Создаём клавиатуру с кнопками
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="run"), KeyboardButton(text="balance")],
        [KeyboardButton(text="stop")],
    ],
    resize_keyboard=True,
)

async def send_menu(message: types.Message):
    menu = (
        "МЕНЮ БОТА\n\n"
        "/run — Запустить главный процесс\n"
        "/balance — Проверить балансы\n"
        "/stop — Остановить бота\n"
    )
    await message.answer(menu, reply_markup=main_keyboard)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    await send_menu(message)

@dp.message(Command("run"))
async def cmd_run(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    await message.answer("Запуск главного процесса...", reply_markup=main_keyboard)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: Process().start(exit_on_finish=False))
    await message.answer("Главный процесс завершён.", reply_markup=main_keyboard)

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    await message.answer("Проверка балансов...", reply_markup=main_keyboard)
    # Собираем вывод функции проверки баланса
    from contextlib import redirect_stdout
    import io
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            await check_balances()
        result = buf.getvalue()
        if not result.strip():
            result = "Баланс успешно проверен."
        await message.answer(f"Результат проверки баланса:\n<pre>{result}</pre>", parse_mode="HTML", reply_markup=main_keyboard)
    except Exception as e:
        await message.answer(f"Ошибка при проверке баланса: {e}", reply_markup=main_keyboard)

stop_event = asyncio.Event()

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    await message.answer("Бот завершает работу...", reply_markup=main_keyboard)
    stop_event.set()

async def main():
    polling = asyncio.create_task(dp.start_polling(bot))
    await stop_event.wait()
    polling.cancel()
    await bot.session.close()
    print("Бот остановлен.")

if __name__ == "__main__":
    asyncio.run(main()) 