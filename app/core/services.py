from app.db.postgres import PgSql
# from app.modules.tasks.service import TasksService
from app.modules.pull_cards.service import PullCardsService
# from app.modules.cards.service import CardsService
# from app.modules.collection.service import CollectionService
from app.modules.users.service import UsersService
# from app.modules.workshop.service import WorkshopService
# from app.modules.trades.service import TradesService
# from app.modules.throw_ball.service import ThrowBallService
from app.modules.packs.service import PacksService


class Services:
    def __init__(self, db: PgSql):
        # self.tasks = TasksService(db)
        # self.cards = CardsService(db)
        # self.workshop = WorkshopService(db)
        # self.trades = TradesService(db)
        # self.throw_ball = ThrowBallService(db)
        self.packs = PacksService(db)

        # self.collection = CollectionService(db, self.trades, self.tasks, self.cards)
        self.pull_cards = PullCardsService(db)
        # self.users = UsersService(db, self.tasks, self.pull_cards, self.trades) # оригинал
        self.users = UsersService(db, self.pull_cards)


    async def init(self):
        await self.cards.init()