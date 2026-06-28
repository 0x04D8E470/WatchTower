from aiogram.fsm.state import StatesGroup, State

class MonitorStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_interval = State()
    waiting_for_expected_status = State()