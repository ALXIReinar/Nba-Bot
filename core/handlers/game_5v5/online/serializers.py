from core.handlers.game_5v5.core.rating_header import Team, PlayerStats, PlayerInfo, PlayersPair


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


def serialize_player_pair(pair) -> dict:
    """Сериализация PlayersPair для Redis"""

    def serialize_player(p: PlayerInfo) -> dict:
        return {
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
            },
            "current_stats": {
                "three_point": p.current_stats.three_point,
                "mid_point": p.current_stats.mid_point,
                "layup": p.current_stats.layup,
                "dunk": p.current_stats.dunk,
                "perimetr_def": p.current_stats.perimetr_def,
                "interior_def": p.current_stats.interior_def,
                "passplay": p.current_stats.passplay,
                "dribbling": p.current_stats.dribbling,
                "block": p.current_stats.block,
                "hands": p.current_stats.hands,
                "pass_perception": p.current_stats.pass_perception,
                "steal": p.current_stats.steal
            }
        }

    return {
        "attacker": serialize_player(pair.attacker),
        "defender": serialize_player(pair.defender),
        "position": pair.position
    }


def deserialize_player_pair(pair_data: dict):
    """Десериализация PlayersPair из Redis"""

    def deserialize_player(p_data: dict) -> PlayerInfo:
        base_stats = PlayerStats(
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
            stats=base_stats,
            team_name=p_data["team_name"],
            positions=p_data["positions"]
        )
        player.on_right_position = p_data["on_right_position"]

        # Восстанавливаем current_stats
        player.current_stats = PlayerStats(
            three_point=p_data["current_stats"]["three_point"],
            mid_point=p_data["current_stats"]["mid_point"],
            layup=p_data["current_stats"]["layup"],
            dunk=p_data["current_stats"]["dunk"],
            perimetr_def=p_data["current_stats"]["perimetr_def"],
            interior_def=p_data["current_stats"]["interior_def"],
            passplay=p_data["current_stats"]["passplay"],
            dribbling=p_data["current_stats"]["dribbling"],
            block=p_data["current_stats"]["block"],
            steal=p_data["current_stats"]["steal"],
            hands=p_data["current_stats"]["hands"],
            pass_perception=p_data["current_stats"]["pass_perception"]
        )

        return player

    attacker = deserialize_player(pair_data["attacker"])
    defender = deserialize_player(pair_data["defender"])

    return PlayersPair(attacker, defender, pair_data["position"])
