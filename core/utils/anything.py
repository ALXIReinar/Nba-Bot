from collections import namedtuple
from dataclasses import dataclass


class RedisKeys:
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


def truncate_text(text, max_length=25):
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    else:
        return text

"Редкости карточек"
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

"Роли карточек"
positions = ["C", "PG", "PF", "SG", "SF"]


"Онлайн пвп"
@dataclass
class GamePvpCalls:
    pvp_menu: str = 'pvp_menu'
    pvp_1: str = 'pvp_1'
    pvp_2: str = 'pvp_2'
    pvp_3: str = 'pvp_3'
    pvp_run: str = 'pvp_run'

    pvp_tactic_attack: str = 'pvp_tactic_attack'
    pvp_tactic_defense: str = 'pvp_tactic_defense'
    pvp_tactic_balance: str = 'pvp_tactic_balance'

    tactic_map = {
        pvp_tactic_defense: "defense",
        pvp_tactic_attack: "attack",
        pvp_tactic_balance: "balance"
    }

GAME_CALLBACKS = {
    GamePvpCalls.pvp_1, GamePvpCalls.pvp_2, GamePvpCalls.pvp_3,
    GamePvpCalls.pvp_run,

    GamePvpCalls.pvp_tactic_defense,
    GamePvpCalls.pvp_tactic_attack,
    GamePvpCalls.pvp_tactic_balance,

    GamePvpCalls.pvp_menu,
    "NONE",
    "none",
}

@dataclass
class InvitePvpCalls:
    pvp_accept_: str = 'pvp_accept_'
    pvp_decline_: str = 'pvp_decline_'

GAME_CALLBACK_PREFIXES = {
    InvitePvpCalls.pvp_accept_,
    InvitePvpCalls.pvp_decline_,
}


"Косметические мапы для пвп"
platform_position_emoji = {
    'interior': '🎨',
    'perimetr': '🎯'
}
pick_tactic_message = {
    'defense': "Оборонительную🛡",
    'attack': "Атакующую⚔️",
    'balance': "Сбалансированную⚖️"
}
tactic_message = {
    'defense': "Оборонительная🛡",
    'attack': "Атакующая⚔️",
    'balance': "Сбалансированная⚖️"
}
