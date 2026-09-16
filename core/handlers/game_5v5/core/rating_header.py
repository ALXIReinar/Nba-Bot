
import random

from aiogram.fsm.state import StatesGroup, State

import copy

from core.data.postgres import PgSql
from core.utils.anything import categories, positions


class Match(StatesGroup):
    Main = State()
    Team = State()
    WatchingTeam = State()
    WatchingTactic = State()
    WatchingRating = State()
    WatchingRules = State()
    WatchingChannels = State()
    PickingCategory = State()
    ChoosingPlayer = State()
    ChoosingToPlay = State()
    StartedRanked = State()
    ChoosingTactic = State()
    PlayingMatch = State()
    WaitingForEndAction = State()

pos_debuff = 0.15


class PlayerStats:
    three_point : int
    mid_point : int
    layup : int
    dunk : int
    perimetr_def : int
    interior_def : int
    passplay : int
    dribbling : int
    block : int
    hands : int
    pass_perception : int
    steal : int

    def __init__(self, three_point : int, mid_point : int, layup : int, dunk : int, perimetr_def : int, interior_def : int, passplay : int, dribbling : int, block : int, steal : int, hands : int, pass_perception : int):
        self.three_point = three_point
        self.mid_point = mid_point
        self.layup = layup
        self.dunk = dunk
        self.perimetr_def = perimetr_def
        self.interior_def = interior_def
        self.passplay = passplay
        self.dribbling = dribbling
        self.block = block
        self.hands = hands
        self.pass_perception = pass_perception
        self.steal = steal

class PlayerInfo(object):
    card_id : int
    name : str
    category : str
    base_stats : PlayerStats
    current_stats : PlayerStats
    team_name : str
    positions : str
    on_right_position = False
    position : int

    def __init__(self, card_id: int, position : int, category : str, name : str, stats : PlayerStats, team_name : str, positions : str):
        self.card_id = card_id
        self.category = category
        self.name = categories[self.category].emoji + name
        self.base_stats = stats
        self.current_stats = copy.copy(stats)
        self.team_name = team_name
        self.positions = positions
        self.position = position

    def get_base_stats(self) -> PlayerStats:
        return self.base_stats

    def get_current_stats(self) -> PlayerStats:
        return self.current_stats
    
    def get_defence(self, pos) -> PlayerStats:
        if pos == 'interior':
            return self.get_interior_def()
        elif pos == 'perimetr':
            return self.get_perimetr_def()
        else:
            return 0
    
    def get_interior_def(self) -> int:
        return self.current_stats.interior_def
    
    def get_perimetr_def(self) -> int:
        return self.current_stats.perimetr_def

    def get_three_point_shot(self) -> int:
        return self.current_stats.three_point
    
    def get_mid_point_shot(self) -> int:
        return self.current_stats.mid_point
    
    def get_layup(self) -> int:
        return self.current_stats.layup
    
    def get_dunk(self) -> int:
        return self.current_stats.dunk

    def get_passplay(self) -> int:
        return self.current_stats.passplay
    
    def get_dribbling(self) -> int:
        return self.current_stats.dribbling
    
    def get_block(self) -> int:
        return self.current_stats.block
    
    def get_steal(self) -> int:
        return self.current_stats.steal
    
    def get_hands(self) -> int:
        return self.current_stats.hands
    
    def get_pass_perception(self) -> int:
        return self.current_stats.pass_perception
    
    def reset_buffs(self):
        self.current_stats = copy.copy(self.base_stats)

    def apply_current_stats_as_base(self):
        self.base_stats = copy.copy(self.current_stats)

    def apply_def_debuff(self, debuff):
        debuff = 1 - debuff
        self.current_stats.interior_def = max(0, int(self.current_stats.interior_def * debuff))
        self.current_stats.perimetr_def = max(0, int(self.current_stats.perimetr_def * debuff))
        self.current_stats.block = max(0, int(self.current_stats.block * debuff))
        self.current_stats.steal = max(0, int(self.current_stats.steal * debuff))
        self.current_stats.pass_perception = max(0, int(self.current_stats.pass_perception * debuff))

    
    def apply_pos_debuff(self):
        debuff = 1 - pos_debuff
        self.current_stats.three_point = int(self.current_stats.three_point * debuff)
        self.current_stats.mid_point = int(self.current_stats.mid_point * debuff)
        self.current_stats.layup = int(self.current_stats.layup * debuff)
        self.current_stats.dunk = int(self.current_stats.dunk * debuff)
        self.current_stats.interior_def = int(self.current_stats.interior_def * debuff)
        self.current_stats.perimetr_def = int(self.current_stats.perimetr_def * debuff)
        self.current_stats.dribbling = int(self.current_stats.dribbling * debuff)
        self.current_stats.passplay = int(self.current_stats.passplay * debuff)
        self.current_stats.block = int(self.current_stats.block * debuff)
        self.current_stats.steal = int(self.current_stats.steal * debuff)
        self.current_stats.pass_perception = int(self.current_stats.pass_perception * debuff)
        self.current_stats.hands = int(self.current_stats.hands * debuff)

    def set_tactic(self, tactic : str = None):
        if(tactic == 'defense'):
            self.current_stats.interior_def = min(100, int(self.current_stats.interior_def * 1.12))
            self.current_stats.perimetr_def = min(100, int(self.current_stats.perimetr_def * 1.12))
        elif(tactic == 'attack'):
            self.current_stats.dribbling = min(100, int(self.current_stats.dribbling * 1.12))
        elif(tactic == 'balance'):
            self.current_stats.dribbling = min(100, int(self.current_stats.dribbling * 1.06))
            self.current_stats.interior_def = min(100, int(self.current_stats.interior_def * 1.06))
            self.current_stats.perimetr_def = min(100, int(self.current_stats.perimetr_def * 1.06))

    def get_shooting_platform_position(self) -> str:
        perimetr = self.get_mid_point_shot() + self.get_three_point_shot()
        interior = self.get_dunk() + self.get_layup()
        all = interior + perimetr
        if(perimetr > interior):
            diff = perimetr - interior
            diff *= diff
            perimetr += diff
            all += diff

        if(interior > perimetr):
            diff = interior - perimetr
            diff *= diff
            interior += diff
            all += diff
        
            
        rand = random.random()
        return 'interior' if rand < interior / all else 'perimetr'
    
    def to_text(self, tactic : str) -> str:
        text = f'Игрок {self.name}\nПозиция {self.positions}\nКлуб {self.team_name}\n'
        on_pos_text = " - 15%⛳️" if not self.on_right_position else ""
        text += "\n⏫ = "
        if(tactic == 'defense'):
            text += "[🛡+12%] 🛡"
        elif(tactic == 'attack'):
            text += "[⛹️‍♂️+12%] ⚔️"
        elif(tactic == 'balance'):
            text += "[🛡⛹️‍♂️+6%] ⚖️"
        
        text += on_pos_text

        text += '<code>'

        text += f"\nOS: "

        # three_point
        text += f"3️⃣ {self.base_stats.three_point}"
        if(self.current_stats.three_point != self.base_stats.three_point):
            text += f"{self.current_stats.three_point - self.base_stats.three_point:<+3d} "
        else:
            text += "    "

        # mid_point
        text += f"2️⃣ {self.base_stats.mid_point}"
        if(self.current_stats.mid_point != self.base_stats.mid_point):
            text += f"{self.current_stats.mid_point - self.base_stats.mid_point:<+3d} "

        text += f"\nIS: "

        # layup
        text += f"⤴️ {self.base_stats.layup}"
        if(self.current_stats.layup != self.base_stats.layup):
            text += f"{self.current_stats.layup - self.base_stats.layup:<+3d} "
        else:
            text += "    "
        
        # dunk
        text += f"⤵️ {self.base_stats.dunk}"
        if(self.current_stats.dunk != self.base_stats.dunk):
            text += f"{self.current_stats.dunk - self.base_stats.dunk:<+3d} "

        text += f"\nPm: "
        
        # dribbling
        text += f"⛹️‍♂️ {self.base_stats.dribbling}"
        if(self.current_stats.dribbling != self.base_stats.dribbling):
            text += f"{self.current_stats.dribbling - self.base_stats.dribbling:<+3d} "
        else:
            text += "    "

        # passplay
        text += f"🤝 {self.base_stats.passplay}"
        if(self.current_stats.passplay != self.base_stats.passplay):
            text += f"{self.current_stats.passplay - self.base_stats.passplay:<+3d} "

        text += f"\nDf: "
        
        # perimetr
        text += f"🎯 {self.base_stats.perimetr_def}"
        if(self.current_stats.perimetr_def != self.base_stats.perimetr_def):
            text += f"{self.current_stats.perimetr_def - self.base_stats.perimetr_def:<+3d} "
        else:
            text += "    "

        # interior
        text += f"🎨 {self.base_stats.interior_def}"
        if(self.current_stats.interior_def != self.base_stats.interior_def):
            text += f"{self.current_stats.interior_def - self.base_stats.interior_def:<+3d} "

        text += f"\nEx: "
        text += f"🚫 {self.base_stats.block}    🪬 {self.base_stats.pass_perception}\n"
        text += f"    👐 {self.base_stats.hands}    🥷 {self.base_stats.steal}\n"

        text += '</code>'

        return text
    
class Team:
    players : list[PlayerInfo]

    def __init__(self, players : list[PlayerInfo]):
        self.players = players

    @staticmethod
    async def get_team_from_user_id(user_id, db: PgSql):
        # team_ids = await db.conn.fetchrow(f"SELECT {positions[0]}, {positions[1]}, {positions[2]}, {positions[3]}, {positions[4]} FROM user_team WHERE user_id={user_id};")
        team_ids = await db.conn.fetchrow(f"SELECT {', '.join(positions)} FROM user_team WHERE user_id = $1", user_id)

        team_players = []
        for i in range(len(positions)):
            # if(team_ids[i] == None):
            if(team_ids[positions[i].lower()] == None):
                team_players.append(None)
                continue
            player = await get_player_by_card_id(team_ids[i], i, db)
            if(positions[i] in player.positions):
                player.on_right_position = True
            else:
                player.apply_pos_debuff()
            team_players.append(player)

        return Team(team_players)

    def set_tactic(self, tactic : str):
        for player in self.players:
            if player is not None:
                player.set_tactic(tactic)

    def set_current_stats_as_base(self):
        for player in self.players:
            if player is not None:
                player.apply_current_stats_as_base()

    def apply_def_debuff(self, debuff):
        for player in self.players:
            if player is not None:
                player.apply_def_debuff(debuff)

    def reset_stats(self):
        for player in self.players:
            if player is not None:
                player.reset_buffs()

    
class PlayersPair(object):
    attacker : PlayerInfo
    defender : PlayerInfo
    position : str

    def __init__(self, attacker: PlayerInfo, defender : PlayerInfo, position : str):
        self.attacker = attacker
        self.defender = defender
        self.position = position


async def get_max_rating(user_id: int, db: PgSql) -> int:
    return await db.conn.fetchval(f"SELECT max_rating FROM user_rating WHERE user_id = $1", user_id)

async def get_rating(user_id, db: PgSql) -> int:
    """
    Не используется в rating_header, rating_team, rating_game - файлах
    """
    # if db.joker:
    #     return random.randint(-2000, 2000)
    # else:
    #     cursor = db.connection.cursor()
    #     cursor.execute(f"SELECT rating FROM user_rating WHERE user_id={user_id};")
    #     rating = cursor.fetchone()[0]
    #     cursor.close()
    #     return rating
    return await db.conn.fetchval(f"SELECT rating FROM user_rating WHERE user_id = $1", user_id)

def update_team_info(team : list[PlayerInfo]):
    clubs = {}
    for i in range(len(team)):
        if team[i] is None:
            continue
        player : PlayerInfo = team[i]
        clubs[player.team_name] = clubs.setdefault(player.team_name, 0) + 1
        if(positions[i] in player.positions):
            player.on_right_position = True
        player.position = i

    for i in range(len(team)):
        if team[i] is None:
            continue
        team_name = team[i].team_name
        if(clubs[team_name] > 1):
            team[i].teamup_lvl = clubs[team_name] - 1
    return team

def apply_tactic(team : list[PlayerInfo], tactic : str):
    for player in team:
        if(player is not None):
            player.apply_tactic(tactic)

def apply_def_debuff(team : list[PlayerInfo], debuff):
    for player in team:
        if(player is not None):
            player.base_interior_def * debuff
            player.base_perimetr_def * debuff

async def get_team_ids(user_id, db: PgSql) -> list[int]:
    # cursor.execute(f"SELECT {positions[0]}, {positions[1]}, {positions[2]}, {positions[3]}, {positions[4]} FROM user_team WHERE user_id={user_id};")
    return (await db.conn.fetchrow(f"SELECT {', '.join(positions)} FROM user_team WHERE user_id = $1", user_id)).values()

async def get_player_by_card_id(card_id, pos : int, db: PgSql) -> PlayerInfo:
    player_cols = ["category", "name", "club", "position"]
    stats_cols = ["threepoint_shot", "mid_range_shot", "layup", "dunk", "perimetr_defense", "interior_defense", "passplay", "dribbling", "block", "steal", "hands", "pass_perception"]
    result = await db.conn.fetchrow(f"SELECT {', '.join(player_cols)}, {', '.join(stats_cols)} FROM cards WHERE card_id = $1", card_id)

    # base_stats : PlayerStats = PlayerStats(result[4], result[5], result[6], result[7], result[8], result[9], result[10], result[11], result[12], result[13], result[14], result[15])
    base_stats : PlayerStats = PlayerStats(*tuple(result[col] for col in stats_cols))
    # player = PlayerInfo(card_id, pos, result[0], result[1], base_stats, result[2], result[3])
    player = PlayerInfo(card_id, pos, result[player_cols[0]], result[player_cols[1]], base_stats, result[player_cols[2]], result[player_cols[3]])
    return player

async def get_user_defense_tactic(user_id, db: PgSql):
    return await db.conn.fetchval(f"SELECT defense_tactic FROM user_rating WHERE user_id = $1", user_id)

async def get_team(user_id, db: PgSql) -> list[PlayerInfo]:
    team_ids = (await db.conn.fetchrow(f"SELECT {', '.join(positions)} FROM user_team WHERE user_id = $1", user_id)).values()
    team_players = []
    for i in range(len(positions)):
        if(team_ids[i] == None):
            team_players.append(None)
            continue
        player = await get_player_by_card_id(team_ids[i], i, db)
        if(positions[i] in player.positions):
            player.on_right_position = True
        else:
            player.apply_pos_debuff()
        team_players.append(player)

    return team_players