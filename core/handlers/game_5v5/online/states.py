from aiogram.fsm.state import State, StatesGroup


class OnlineMatch(StatesGroup):

    # Ожидание ответа на приглашение (для отправителя)
    WaitingInviteResponse = State()
    
    # Выбор тактики перед началом игры
    ChoosingTactic = State()
    
    # Просмотр "монетки" (3 стикера 🏀)
    WatchingCoinToss = State()
    
    # Игрок делает ход (атакует)
    PlayingTurn = State()
    
    # Игрок ждёт хода соперника (защищается)
    WaitingOpponent = State()
