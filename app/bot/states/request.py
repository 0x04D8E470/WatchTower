from aiogram.fsm.state import StatesGroup, State

class RequestStates(StatesGroup):
    waiting_for_method = State()
    waiting_for_url = State()
    waiting_for_headers = State()
    waiting_for_body = State()
    waiting_for_confirmation = State()
    waiting_for_template_name = State()