from dataclasses import dataclass


admin_commands = {
    '/flush_shop_cache', # Очистка кэша тарифных планов магазина
    '/reset_req_limit', # сброс счётчика запросов на пользователя
}

class RedisKeys:
    @staticmethod
    def important_key(tg_id: str | int) -> str:
        return f'important_key:tg_id={tg_id}:v1'


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
