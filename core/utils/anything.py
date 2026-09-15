from collections import namedtuple
from dataclasses import dataclass


admin_commands = {
    '/flush_shop_cache', # Очистка кэша тарифных планов магазина
    '/reset_req_limit', # сброс счётчика запросов на пользователя
}

class RedisKeys:
    @staticmethod
    def important_key(tg_id: str | int) -> str:
        return f'important_key:tg_id={tg_id}:v1'
    
    # PvP матчи
    @staticmethod
    def pvp_match(match_id: str) -> str:
        """Ключ матча: pvp_match:match_id={uuid}"""
        return f'pvp_match:match_id={match_id}'
    
    @staticmethod
    def user_in_match(user_id: int) -> str:
        """Ключ для быстрого поиска матча пользователя"""
        return f'user_in_match:{user_id}'
    
    @staticmethod
    def match_request(from_user_id: int, to_user_id: int) -> str:
        """Ключ запроса на игру"""
        return f'match_request:{from_user_id}:{to_user_id}'


@dataclass
class SubServiceUris:
    # users division
    add_tg_user: str = '/api/v1/tg-bot/users/add'
    get_user_profile: str = '/api/v1/tg-bot/users/get'

    # user_subs division
    get_user_subs_all: str = '/api/v1/tg-bot/users/subs/all'

    # sub_plans division
    get_sub_plans_all: str = '/api/v1/tg-bot/sub_plans/all'
    get_payment_link: str = '/api/v1/robokassa/get_pay_link'


def truncate_text(text, max_length=25):
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    else:
        return text

category_template = namedtuple("category", ["id", "eng_name", "emoji", "single_msg", "craft_from", "need_to_craft",])

bronze_category = category_template(0, 'bronze', '🥉', '🥉Бронза', 'bronze', 1)
silver_category = category_template(1, 'silver', '🥈', '🥈Серебро', 'bronze', 10)
gold_category = category_template(2, 'gold', '🥇', '🥇Золото', 'silver', 10)
diamond_category = category_template(3, 'diamond', '💎', '💎Алмаз', 'gold', 10)
legend_category = category_template(4, 'legend', '🎖', '🎖Легенда', 'gold', 15)

categories = {
    'bronze': bronze_category,
    'silver': silver_category,
    'gold': gold_category,
    'legend': legend_category,
    'diamond': diamond_category,
}