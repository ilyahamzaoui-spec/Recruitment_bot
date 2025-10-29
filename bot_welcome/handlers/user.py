# bot_welcome/handlers/user.py
from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot_welcome.services.content_service import ContentService

user_router = Router()


def get_service(session: AsyncSession) -> ContentService:
    """Хелпер для DI ContentService."""
    return ContentService(session)


# --- Вспомогательные функции для клавиатуры ---

async def create_main_keyboard(vacancies: list) -> types.InlineKeyboardMarkup:
    """Создает основную навигационную клавиатуру."""
    builder = InlineKeyboardBuilder()
    vac_count = sum(1 for v in vacancies if v.is_active)

    builder.button(text=f"📋 Вакансии ({vac_count})", callback_data="show_vacancies")
    builder.button(text="🔗 Полезные ресурсы", callback_data="show_links")
    builder.button(text="❓ Справка", callback_data="show_help")

    builder.adjust(1)
    return builder.as_markup()


# --- Хендлеры команд и Callback'ов ---

async def send_welcome_message(message: Message, service: ContentService):
    """Отправляет полное приветственное сообщение."""
    welcome_text, _ = await service.get_welcome_data()
    vacancies = await service.get_latest_vacancies(limit=5)

    vac_text_part = service.format_vacancies_text(vacancies)
    final_text = f"{welcome_text}\n\n---\n\n{vac_text_part}"

    keyboard = await create_main_keyboard(vacancies)

    await message.answer(
        final_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


@user_router.message(F.text.in_(['/start', '/help']))
async def handle_start_and_help(message: Message, session: AsyncSession):
    """Обработка /start и /help."""
    service = get_service(session)
    await send_welcome_message(message, service)


@user_router.callback_query(F.data == "show_vacancies")
async def handle_show_vacancies(callback: CallbackQuery, session: AsyncSession):
    """Показывает актуальные вакансии."""
    await callback.answer("Загружаю вакансии...")
    service = get_service(session)
    vacancies = await service.get_latest_vacancies(limit=10)  # Можно показать больше

    text = service.format_vacancies_text(vacancies)

    builder = InlineKeyboardBuilder()
    # Добавляем кнопку "Вернуться в меню"
    builder.button(text="↩️ В главное меню", callback_data="start_menu")

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


@user_router.callback_query(F.data == "show_links")
async def handle_show_links(callback: CallbackQuery, session: AsyncSession):
    """Показывает полезные ссылки."""
    await callback.answer()
    service = get_service(session)
    _, links = await service.get_welcome_data()

    text = "**🔗 Полезные ресурсы:**\n"
    builder = InlineKeyboardBuilder()

    for item in links:
        builder.button(text=item['title'], url=item['url'])

    builder.button(text="↩️ В главное меню", callback_data="start_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )


@user_router.callback_query(F.data == "start_menu")
async def handle_back_to_menu(callback: CallbackQuery, session: AsyncSession):
    """Возвращает в главное меню."""
    await callback.answer()
    service = get_service(session)
    await send_welcome_message(callback.message, service)


# --- Обработка вступления в канал (Отправка в ЛС) ---
@user_router.message(F.new_chat_members)
async def handle_new_member_in_chat(message: Message, session: AsyncSession):
    """Отправляет приветственное сообщение в ЛС новому участнику (если бот имеет доступ)."""
    service = get_service(session)
    for member in message.new_chat_members:
        if member.is_bot: continue  # Игнорируем других ботов

        try:
            # Отправляем краткое приветствие и призыв нажать /start
            await message.bot.send_message(
                chat_id=member.id,
                text="👋 **Добро пожаловать в канал!**\n\nНажмите /start, чтобы увидеть актуальные вакансии и полезные ссылки.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            # Например, если пользователь заблокировал бота
            print(f"Не удалось отправить приветствие пользователю {member.id}: {e}")