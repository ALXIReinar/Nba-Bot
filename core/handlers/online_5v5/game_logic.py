"""
Игровая логика для PvP режима.
Адаптеры над синхронными функциями из rating_game.py.
"""
import copy
import logging
from typing import Any

from core.handlers.rating_game import (
    try_shoot,
    try_to_pass,
    get_pg_player,
    get_best_interior_def,
    get_best_perimetr_def,
    PassFirstState,
    PassSecondState,
    AttackFirstState
)
from core.handlers.rating_header import PlayerInfo, PlayerStats, Team, PlayersPair


logger = logging.getLogger(__name__)


def deserialize_team(team_data: dict) -> Team:
    """
    Десериализация команды из dict (из Redis) в объект Team.
    
    Args:
        team_data: Словарь с данными команды
    
    Returns:
        Team: Восстановленный объект команды
    """
    players = []
    for p_data in team_data["players"]:
        stats = PlayerStats(
            three_point=p_data["base_stats"]["three_point"],
            mid_point=p_data["base_stats"]["mid_point"],
            layup=p_data["base_stats"]["layup"],
            dunk=p_data["base_stats"]["dunk"],
            perimetr_def=p_data["base_stats"]["perimetr_def"],
            interior_def=p_data["base_stats"]["interior_def"],
            passplay=p_data["base_stats"]["passplay"],
            dribbling=p_data["base_stats"]["dribbling"],
            block=p_data["base_stats"]["block"],
            steal=p_data["base_stats"]["steal"],
            hands=p_data["base_stats"]["hands"],
            pass_perception=p_data["base_stats"]["pass_perception"]
        )
        
        player = PlayerInfo(
            card_id=p_data["card_id"],
            position=p_data["position"],
            category=p_data["category"],
            name=p_data["name"],
            stats=stats,
            team_name=p_data["team_name"],
            positions=p_data["positions"]
        )
        player.on_right_position = p_data["on_right_position"]
        players.append(player)
    
    return Team(players)


def serialize_team(team: Team) -> dict:
    """
    Сериализация команды в dict для хранения в Redis.
    
    Args:
        team: Объект команды
    
    Returns:
        dict: Сериализованная команда
    """
    return {
        "players": [
            {
                "card_id": p.card_id,
                "name": p.name,
                "category": p.category,
                "position": p.position,
                "positions": p.positions,
                "team_name": p.team_name,
                "on_right_position": p.on_right_position,
                "base_stats": {
                    "three_point": p.base_stats.three_point,
                    "mid_point": p.base_stats.mid_point,
                    "layup": p.base_stats.layup,
                    "dunk": p.base_stats.dunk,
                    "perimetr_def": p.base_stats.perimetr_def,
                    "interior_def": p.base_stats.interior_def,
                    "passplay": p.base_stats.passplay,
                    "dribbling": p.base_stats.dribbling,
                    "block": p.base_stats.block,
                    "hands": p.base_stats.hands,
                    "pass_perception": p.base_stats.pass_perception,
                    "steal": p.base_stats.steal
                }
            }
            for p in team.players if p is not None
        ]
    }


def apply_tactic_to_team(team: Team, tactic: str):
    """
    Применить тактику к команде.
    
    Args:
        team: Команда
        tactic: "defense" | "attack" | "balance"
    """
    team.set_tactic(tactic)


def set_positions_for_pvp(
    att_team: Team,
    def_team: Team,
    pass_state: str,
    def_debuff: float,
    save_pg: bool,
    pg_pair: PlayersPair | None = None
) -> tuple[PlayersPair, PlayersPair, PlayersPair]:
    """
    Установить позиции игроков для атаки (аналог set_positions из rating_game.py).
    
    Returns:
        tuple: (pg_pair, first_pair, second_pair)
    """
    # Сбрасываем статы
    def_team.reset_stats()
    att_team.reset_stats()
    
    # Применяем дебафф защиты
    if def_debuff != 0:
        def_team.apply_def_debuff(def_debuff)
    
    att_team_list = [p for p in att_team.players if p is not None]
    def_team_list = [p for p in def_team.players if p is not None]
    
    # Определяем PG (игрока с мячом)
    if save_pg and pg_pair:
        pg = pg_pair.attacker
        pg_opp = pg_pair.defender
        pg_pos = pg_pair.position
    else:
        pg = get_pg_player(att_team_list)
        pg_pos = pg.get_shooting_platform_position()
        pg_opp = (
            get_best_interior_def(def_team_list) 
            if pg_pos == 'interior' 
            else get_best_perimetr_def(def_team_list)
        )
    
    new_pg_pair = PlayersPair(pg, pg_opp, pg_pos)
    
    # Удаляем выбранных игроков из списков
    def_team_list = [p for p in def_team_list if p != pg_opp]
    att_team_list = [p for p in att_team_list if p != pg]
    
    # Выбираем двух игроков для паса
    import random
    first = random.choice(att_team_list)
    att_team_list.remove(first)
    second = random.choice(att_team_list)
    
    first_pos = first.get_shooting_platform_position()
    second_pos = second.get_shooting_platform_position()
    
    first_opp = (
        get_best_interior_def(def_team_list)
        if first_pos == 'interior'
        else get_best_perimetr_def(def_team_list)
    )
    def_team_list.remove(first_opp)
    
    second_opp = (
        get_best_interior_def(def_team_list)
        if second_pos == 'interior'
        else get_best_perimetr_def(def_team_list)
    )
    
    first_pair = PlayersPair(first, first_opp, first_pos)
    second_pair = PlayersPair(second, second_opp, second_pos)
    
    # Применяем эффекты паса
    pass_debuff_values = {
        PassSecondState.normal: 0.1,
        PassSecondState.good: 0.25,
        PassSecondState.perfect: 1
    }
    dribbling_buff_values = {PassFirstState.bad: 0.85}
    
    if pass_state == 'good':
        debuff = pass_debuff_values[PassSecondState.good]
        new_pg_pair.defender.apply_def_debuff(debuff)
    elif pass_state == 'normal':
        debuff = pass_debuff_values[PassSecondState.normal]
        new_pg_pair.defender.apply_def_debuff(debuff)
    elif pass_state == 'perfect':
        debuff = pass_debuff_values[PassSecondState.perfect]
        new_pg_pair.defender.apply_def_debuff(debuff)
    elif pass_state == 'bad':
        buff = dribbling_buff_values[PassFirstState.bad]
        new_pg_pair.attacker.current_stats.dribbling = max(
            0, 
            int(new_pg_pair.attacker.current_stats.dribbling * buff)
        )
    
    return new_pg_pair, first_pair, second_pair


def execute_attack_action(pg_pair: PlayersPair) -> tuple[str, str, str, int]:
    """
    Выполнить атаку (вызывает синхронную функцию try_shoot).
    
    Returns:
        tuple: (first_msg, action_msg, success_msg, score)
               score = -1 если мяч потерян
    """
    player = pg_pair.attacker
    defender = pg_pair.defender
    pos = pg_pair.position
    
    opp_def = (
        defender.get_interior_def() 
        if pos == 'interior' 
        else defender.get_perimetr_def()
    )
    
    dribbling = player.get_dribbling()
    hands = player.get_hands()
    steal = defender.get_steal()
    block = defender.get_block()
    
    # Определяем атаку (layup/dunk или 3pt/2pt)
    if pos == 'interior':
        layup = player.get_layup()
        dunk = player.get_dunk()
        if layup > dunk:
            attack_stat = layup
            attack_name = "лэй-ап"
            points = 2
        else:
            attack_stat = dunk
            attack_name = "данк"
            points = 2
    else:
        three_pt = player.get_three_point_shot()
        mid_pt = player.get_mid_point_shot()
        if three_pt > mid_pt:
            attack_stat = three_pt
            attack_name = "3-очковый"
            points = 3
        else:
            attack_stat = mid_pt
            attack_name = "2-очковый"
            points = 2
    
    # Вызываем синхронную функцию
    result = try_shoot(dribbling, opp_def, hands, steal, attack_stat, block)
    
    # Формируем сообщения
    first_msg = f"{player.name} идёт в атаку!\n"
    
    if result == AttackFirstState.lost:
        return first_msg, "", "Мяч потерян! ❌", -1
    
    # Определяем тип броска
    if result in [AttackFirstState.trough_block_success, AttackFirstState.trough_block_fail]:
        action_msg = f"Бросок через блок ({attack_name})!\n"
    elif result in [AttackFirstState.hard_throw_success, AttackFirstState.hard_throw_fail]:
        action_msg = f"Сложный бросок ({attack_name})!\n"
    else:
        action_msg = f"Свободный бросок ({attack_name})!\n"
    
    # Результат
    if result in [
        AttackFirstState.trough_block_success,
        AttackFirstState.hard_throw_success,
        AttackFirstState.free_throw_success
    ]:
        success_msg = f"Попадание! +{points} 🎯"
        return first_msg, action_msg, success_msg, points
    else:
        success_msg = "Промах! ❌"
        return first_msg, action_msg, success_msg, 0


def serialize_player_pair(pair: PlayersPair) -> dict:
    """
    Сериализация пары игроков для хранения в Redis.
    
    Args:
        pair: Пара атакующий-защищающийся
    
    Returns:
        dict: Сериализованная пара
    """
    return {
        "attacker": {
            "card_id": pair.attacker.card_id,
            "name": pair.attacker.name,
            "position": pair.attacker.position
        },
        "defender": {
            "card_id": pair.defender.card_id,
            "name": pair.defender.name,
            "position": pair.defender.position
        },
        "position": pair.position
    }


def deserialize_player_pair(pair_data: dict) -> PlayersPair:
    """
    Десериализация пары игроков из dict.
    ВНИМАНИЕ: Возвращает упрощённую версию без полных статов!
    Используется только для отображения имён и позиций.
    
    Args:
        pair_data: Словарь с данными пары
    
    Returns:
        PlayersPair: Восстановленная пара (упрощённая)
    """
    # Создаём временные объекты PlayerInfo без полных данных
    # Это нужно только для отображения имён в сообщениях
    attacker_info = type('PlayerInfo', (), {
        'card_id': pair_data["attacker"]["card_id"],
        'name': pair_data["attacker"]["name"],
        'position': pair_data["attacker"]["position"]
    })()
    
    defender_info = type('PlayerInfo', (), {
        'card_id': pair_data["defender"]["card_id"],
        'name': pair_data["defender"]["name"],
        'position': pair_data["defender"]["position"]
    })()
    
    return type('PlayersPair', (), {
        'attacker': attacker_info,
        'defender': defender_info,
        'position': pair_data["position"]
    })()


def execute_pass_action(
    pg_pair: PlayersPair,
    pass_pair: PlayersPair
) -> tuple[str, str, bool, str]:
    """
    Выполнить пас (вызывает синхронную функцию try_to_pass).
    
    Returns:
        tuple: (first_msg, success_msg, success, pass_state)
               success = True если пас удался
               pass_state = "good" | "normal" | "perfect" | "bad" | "lost"
    """
    first_state, second_state = try_to_pass(pg_pair, pass_pair)
    
    player = pg_pair.attacker
    target = pass_pair.attacker
    
    first_msg = f"{player.name} пасует к {target.name}\n"
    
    if first_state == PassFirstState.lost:
        return first_msg, "Мяч перехвачен! ❌", False, "lost"
    elif first_state == PassFirstState.bad:
        return first_msg, "Плохой пас! Дриблинг снижен на 15%", True, "bad"
    
    # Хороший пас
    if second_state == PassSecondState.normal:
        return first_msg, "Пас удался! Защита противника снижена на 10%", True, "normal"
    elif second_state == PassSecondState.good:
        return first_msg, "Отличный пас! Защита противника снижена на 25%", True, "good"
    else:  # perfect
        return first_msg, "Идеальный пас! Защита противника уничтожена!", True, "perfect"
