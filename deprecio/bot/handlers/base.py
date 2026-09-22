"""Base command handlers for /start, /help, and educational guides."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from deprecio.bot.keyboards import get_back_keyboard, get_main_menu_keyboard

router = Router(name="base_router")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    text = (
        "👋 **Добро пожаловать в Deprecio!**\n\n"
        "Я аналитический бот по вторичному рынку смартфонов.\n"
        "Помогаю покупать технику выгодно и не терять деньги при перепродаже:\n\n"
        "• 📉 **Остаточная стоимость (RV%):** сколько телефон потерял от стартовой цены\n"
        "• 🟢 **Зона Sweet Spot:** когда наступает идеальный момент для покупки\n"
        "• ⚖️ **Анализ версий:** разница цен между CN, Ростест/EAC и Global\n"
        "• 💡 **Аналоги:** подбор лучших альтернатив в том же бюджете\n\n"
        "Нажмите кнопку ниже или просто напишите название модели (например, *Xiaomi 14* или *iPhone 15*):"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Как это работает?")
async def handle_help(message: Message) -> None:
    text = (
        "ℹ️ **Как устроен анализ цен в Deprecio:**\n\n"
        "1. **Фильтрация спама и дефектов:**\n"
        "Мы анализируем базу объявлений со вторичного рынка (Авито), отсекая лоты с дефектами "
        "(*битые экраны, заблокированные устройства, 'на запчасти'*).\n\n"
        "2. **Статистика IQR:**\n"
        "Алгоритм межквартильного размаха исключает фиктивные цены ('1 рубль' или оверпрайс).\n\n"
        "3. **Sweet Spot:**\n"
        "Определяет момент, когда начальный обвал цены завершен (обычно 6–12 месяцев после релиза), "
        "и смартфон дает максимум возможностей за свои деньги."
    )
    await message.answer(text, reply_markup=get_back_keyboard(), parse_mode="Markdown")


@router.message(F.text == "⚖️ Версии CN vs EAC")
async def handle_editions_info(message: Message) -> None:
    text = (
        "⚖️ **Региональные версии смартфонов:**\n\n"
        "• 🇨🇳 **Китайская версия (CN):**\n"
        "Выходит раньше всех и стоит дешевле. На вторичке в РФ обычно на **15–25% дешевле** Ростеста. "
        "Минусы: китайская прошивка, часто нет важного диапазона LTE Band 20, китайская вилка.\n\n"
        "• 🇷🇺 **Ростест / EAC:**\n"
        "Официальная поставка для РФ. Самая высокая ликвидность и сохранение остаточной стоимости на вторичке. "
        "Полная гарантия и полный комплект всех частот связи.\n\n"
        "• 🌐 **Global / EU:**\n"
        "Золотая середина: европейская вилка, все бенды, глобальная прошивка, цена между CN и EAC."
    )
    await message.answer(text, reply_markup=get_back_keyboard(), parse_mode="Markdown")


@router.callback_query(F.data == "menu:main")
async def handle_back_to_menu(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard(),
    )
    await callback.answer()
