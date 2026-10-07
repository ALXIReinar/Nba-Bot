from aiogram.fsm.context import FSMContext
from redis.asyncio import Redis

from app.core.config import env, bot
from app.core.services import Services
from app.db.postgres import PgSql
import app.old_core.keyboards as keyboards

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, BotCommand, BotCommandScopeDefault

from aiogram.types import Message, CallbackQuery

from aiogram import F

router = Router()

async def on_startup():
    # log_event('Бот запущен', level='WARNING')
    await bot.send_message(env.admin_tg_id, 'Бот запущен!')

async def set_commands():
    commands = [
        BotCommand(command='/start', description='Запуск бота'),
        BotCommand(command='/complete_task', description='Переключить таску в reward_ready. Принимает "task_id"'),
        BotCommand(command='/complete_task_set', description='Сделать достпуными для получения награды по набору заданий. Принимает "task_set_id"'),
        BotCommand(command='/set_task_set_in_progress', description='Перевести в in_progress задачи по набору и сам набор заданий. Принимает "task_set_id"'),
        BotCommand(command='/add_progress', description='Добавить прогресс. Принимает "challenge_id progress"'),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())


@router.callback_query(F.data.lower() == 'none')
async def nothing(callback: CallbackQuery):
    await callback.answer()

@router.message(CommandStart())
async def cmd_start(
    message: Message,
    db: PgSql,
    services: Services
):
    user_id = message.from_user.id
    username = message.from_user.username

    if not await db.users.exists(user_id):
        referrer = None

        if message.text and " " in message.text:
            raw_referrer = message.text.split(maxsplit=1)[1]

            try:
                if(int(raw_referrer) != user_id):
                    referrer = int(raw_referrer)

            except ValueError:
                pass

        await services.users.add_user(
            user_id=user_id,
            username=username,
            referrer=referrer,
        )

    start_message = """Привет, STEPbro!

Теперь ты часть заряженного коммьюнити. Шаг за шагом ты будешь собирать свою коллекцию, а мы поможем тебе с этим.

@STEEEPCHANNEL - канал
@STEEEPHOUSE - коммьюнити
@STEEEPBRO - поддержка"""

    await message.answer(
        start_message,
        reply_markup=keyboards.main_keyboard,
    )
    await bot.delete_my_commands()
    await set_commands()

@router.message(F.text.startswith('🧍Профиль'))
async def cmd_help(message: Message, db: PgSql):
    await message.answer("Заглушка, чтобы отобразить клаву с кнопкой 'Задания'", reply_markup=keyboards.profile_keyboard)

