from aiogram.types import BotCommand, BotCommandScopeDefault  # noqa: I001
from aiogram import Bot


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command='/start', description='Запуск бота'),
    ]

    await bot.set_my_commands(commands, BotCommandScopeDefault())
