import asyncio
import os

from aiogram.types import InputMediaPhoto, FSInputFile, InputMediaAnimation

from core.config_dir.config import env, bot


class ImageCache:
    def __init__(self):
        self.file_ids = {}  # {card_id: file_id}

    async def edit_photo(self, chat_id, message_id, filepath, caption=None, reply_markup=None, has_spoiler=False):
        filepath = str(filepath)
        if filepath in self.file_ids:
            media = InputMediaPhoto(
                media=self.file_ids[filepath],
                caption=caption,
                parse_mode='html',
                has_spoiler=has_spoiler
            )
            await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
        else:
            path_photo = os.path.abspath(filepath)
            with open(path_photo, "rb") as file:
                media = InputMediaPhoto(
                    media=FSInputFile(path_photo),
                    caption=caption,
                    parse_mode='html',
                    has_spoiler=has_spoiler
                )
                message = await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id,
                                                       reply_markup=reply_markup)
                self.file_ids[filepath] = message.photo[-1].file_id

    async def edit_video(self, chat_id, message_id, filepath, caption=None, reply_markup=None, has_spoiler=False,
                         width=686, height=853):
        filepath = str(filepath)
        if filepath in self.file_ids:
            media = InputMediaAnimation(
                media=self.file_ids[filepath],
                caption=caption,
                parse_mode='html',
                has_spoiler=has_spoiler,
            )
            await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
        else:
            path_photo = env.cards_path / f"default.png"
            # path_photo = os.path.abspath(filepath)
            with open(path_photo, "rb") as file:
                media = InputMediaAnimation(
                    media=FSInputFile(path_photo),
                    caption=caption,
                    parse_mode='html',
                    has_spoiler=has_spoiler,
                    width=width,
                    height=height,
                )
                message = await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id,
                                                       reply_markup=reply_markup)
                try:
                    self.file_ids[filepath] = message.video.file_id
                except:
                    self.file_ids[filepath] = message.animation.file_id

    async def edit_card_media(self, chat_id, message_id, card_filename, caption=None, reply_markup=None,
                              has_spoiler=False):
        card_filename = str(card_filename)
        if card_filename in self.file_ids:
            media = InputMediaPhoto(
                media=self.file_ids[card_filename],
                caption=caption,
                parse_mode='html',
                has_spoiler=has_spoiler
            )
            try:
                await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id,
                                             reply_markup=reply_markup)
            except Exception as e:
                pass
                # logger.error(f"Error editing card media: {e}")

        else:
            path_photo = os.path.join(env.cards_path, f"default.png")
            # path_photo = os.path.join(env.cards_path, f"{card_filename}.PNG")
            with open(path_photo, "rb") as file:
                media = InputMediaPhoto(
                    media=FSInputFile(path_photo),
                    caption=caption,
                    parse_mode='html',
                    has_spoiler=has_spoiler
                )
                try:
                    message = await bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id,
                                                           reply_markup=reply_markup)
                    self.file_ids[card_filename] = message.photo[-1].file_id
                except Exception as e:
                    pass
                    # logger.error(f"Error editing card media: {e}")

    async def send_video(self, chat_id, filepath, caption, reply_markup=None, has_spoiler=False, width=686, height=853):
        filepath = str(filepath)
        if filepath in self.file_ids:
            await bot.send_animation(chat_id, self.file_ids[filepath], height=height, caption=caption, width=width,
                                     has_spoiler=has_spoiler, reply_markup=reply_markup)
        else:
            path_photo = env.cards_path / f"default.mp4"
            # path_photo = os.path.abspath(filepath)
            with open(path_photo, "rb") as file:
                message = await bot.send_animation(chat_id, FSInputFile(path_photo), height=height, width=width,
                                                   caption=caption, has_spoiler=has_spoiler, reply_markup=reply_markup)
                try:
                    self.file_ids[filepath] = message.video.file_id
                except:
                    self.file_ids[filepath] = message.animation.file_id

    async def send_card(self, chat_id, card_filename, text=None, reply_markup=None, has_spoiler=False):
        card_filename = 'default'
        # card_filename = str(card_filename)
        for attempt in range(3):
            try:
                if card_filename in self.file_ids:
                    # Используем сохраненный file_id
                    await bot.send_photo(chat_id, self.file_ids[card_filename], caption=text, reply_markup=reply_markup,
                                         parse_mode='html', has_spoiler=has_spoiler)
                else:
                    # Первая отправка - загружаем с диска
                    path_photo = os.path.join(env.cards_path, f"{card_filename}.png")
                    # path_photo = os.path.join(env.cards_path, f"{card_filename}.PNG")
                    with open(path_photo, "rb") as file:
                        message = await bot.send_photo(chat_id, FSInputFile(path_photo), caption=text,
                                                       reply_markup=reply_markup, parse_mode='html',
                                                       has_spoiler=has_spoiler)
                        self.file_ids[card_filename] = message.photo[-1].file_id
                return

            except Exception:
                # logger.warning(
                #     f"Ошибка отправки сообщения пользователю {chat_id} "
                #     f"(попытка {attempt + 1}/3): {e}"
                # )

                if attempt < 2:
                    await asyncio.sleep(1 + attempt)

        # logger.error(
        #     f"Не удалось отправить сообщение пользователю {chat_id} "
        #     f"после 3 попыток"
        # )


# Инициализация
image_cache = ImageCache()