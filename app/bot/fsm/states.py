from aiogram.fsm.state import State, StatesGroup


class TrialFlow(StatesGroup):
    choosing_server = State()


class PurchaseFlow(StatesGroup):
    choosing_server = State()
    choosing_plan = State()
    choosing_provider = State()


class SupportFlow(StatesGroup):
    waiting_text = State()


class AdminSupportFlow(StatesGroup):
    waiting_reply = State()
