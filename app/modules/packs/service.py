from app.modules.base_service import BaseService
from app.db.postgres import PgSql, Connection
import json

class PacksService(BaseService):
    """
    Сервис паков
    """
    def __init__(self, db: PgSql):
        self.db = db

    async def get_pack_count(self, pack_name: str, user_id: int, conn: Connection | None = None):
        """
        Взять количество паков, блокирующая
        """    
        async with self._connection(conn) as connection:
            answer: dict = await connection.fetchval(f"SELECT packs FROM user_packs WHERE user_id = $1 FOR UPDATE;", user_id)

        count = answer.get(pack_name, 0)
                
        return count

    async def add_packs(self, pack_name : str, count : int, user_id: int, conn: Connection | None = None):
        """
        Добавить пак юзеру
        """    
        async with self._connection(conn) as connection:
            answer: dict = await connection.fetchval(f"SELECT packs FROM user_packs WHERE user_id = $1;", user_id)
            answer[pack_name] = answer.get(pack_name, 0) + count

            await connection.execute(f"UPDATE user_packs SET packs = '{json.dumps(answer)}' WHERE user_id = {user_id};")