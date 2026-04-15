from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать / Главное меню")],
            [KeyboardButton(text="🎁 Пробный период"), KeyboardButton(text="🌍 Выбрать сервер")],
            [KeyboardButton(text="💳 Купить подписку"), KeyboardButton(text="📦 Моя подписка")],
            [KeyboardButton(text="🛠 Поддержка"), KeyboardButton(text="📨 Мои обращения")],
            [KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )
