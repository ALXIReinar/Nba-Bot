from asyncpg import Connection

from core.data.sql_queries.cards_sql import CardsQueries
from core.data.sql_queries.user_teams_sql import UserTeamsQueries
from core.data.sql_queries.users import UsersQueries


class PgSql:
    def __init__(self, conn: Connection):
        self.conn = conn

        self.users = UsersQueries(conn)
        self.cards = CardsQueries(conn)
        self.user_teams = UserTeamsQueries(conn)
