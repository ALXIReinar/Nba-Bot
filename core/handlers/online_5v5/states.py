"""
FSM States для онлайн-режима 5 на 5.
Состояния используются только для UI навигации отдельного пользователя.
Данные матча хранятся в Redis.
"""
from aiogram.fsm.state import State, StatesGroup


class OnlineMatch(StatesGroup):
    """Состояния для онлайн-матча PvP"""
    
    # Ожидание ответа на приглашение (для отправителя)
    WaitingInviteResponse = State()
    
    # Выбор тактики перед началом игры
    ChoosingTactic = State()
    
    # Просмотр "монетки" (3 эмодзи 🏀)
    WatchingCoinToss = State()
    
    # Игрок делает ход (атакует)
    PlayingTurn = State()
    
    # Игрок ждёт хода соперника (защищается)
    WaitingOpponent = State()
