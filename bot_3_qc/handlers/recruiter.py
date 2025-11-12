# bot_3_qc/handlers/recruiter.py
from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot_welcome.services.application_service import ApplicationService
from bot_welcome.models.db_models import Application, ApplicationStatus
from core.config import settings
from typing import Optional

recruiter_router = Router()

# Фильтр для QC-чата
# Примечание: F.chat.id == int(settings.QC_CHAT_ID) предполагает, что QC_CHAT_ID - это строка, которую нужно преобразовать в int
recruiter_router.message.filter(F.chat.id == int(settings.QC_CHAT_ID))
recruiter_router.callback_query.filter(F.message.chat.id == int(settings.QC_CHAT_ID))


def get_application_service(session: AsyncSession) -> ApplicationService:
    return ApplicationService(session)


# --- Вспомогательная функция для экранирования Markdown V2 ---
def escape_input(text: Optional[str]) -> str:
    """Полное ручное экранирование для MarkdownV2."""
    if not text:
        return "Н/Д"

    # Экранируем ВСЕ специальные символы V2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')

    return text.strip()


# --- Вспомогательные функции для форматирования ---

def format_application_message(application: Application) -> str:
    """Форматирует сообщение о новом отклике для QC-чата (Использует Markdown V2)."""
    data = application.candidate_data
    contacts = data.get('contacts', {})
    info = data.get('professional_info', {})

    # Экранирование полей, вводимых пользователем
    full_name_esc = escape_input(data.get('full_name'))
    vacancy_title_esc = escape_input(application.vacancy_title)
    level_esc = escape_input(info.get('level'))
    skills_esc = escape_input(info.get('skills'))
    experience_esc = escape_input(info.get('experience'))
    resume_link_esc = escape_input(data.get('resume_link'))

    # Контакты
    email_esc = escape_input(contacts.get('email'))
    phone_esc = escape_input(contacts.get('phone'))
    tg_esc = escape_input(contacts.get('telegram_username'))

    message_text = (
        # ИСПРАВЛЕНИЕ: Экранируем ID: {application.id} скобками
        f"🚨 *НОВЫЙ ОТКЛИК\\!* ID: {application.id}\\n\\n"
        f"*💼 Вакансия:* {vacancy_title_esc}\n"
        f"*👤 Кандидат:* {full_name_esc}\n"
        f"*🎯 Уровень:* {level_esc}\n"
        f"*✨ Скиллы:* {skills_esc}\n\n"
        f"*📞 Контакты:*\n"
        f"  \\• Email: {email_esc}\n"
        f"  \\• Телефон: {phone_esc}\n"
        f"  \\• TG: {tg_esc}\n\n"
        f"*📝 Опыт:* {experience_esc}\n"
        f"*📎 Резюме:* {resume_link_esc}\n"
        f"*🔄 Статус:* {application.status.value}"
    )
    return message_text


def create_recruiter_keyboard(app_id: int) -> types.InlineKeyboardMarkup:
    """Создает клавиатуру действий для рекрутера."""
    builder = InlineKeyboardBuilder()

    builder.button(text="✅ Взять в работу", callback_data=f"app_take_{app_id}")
    builder.button(text="✉️ Пригласить", callback_data=f"app_status_INVITED_{app_id}")
    builder.button(text="❌ Отказ", callback_data=f"app_status_REJECTED_{app_id}")

    builder.adjust(1, 2)
    return builder.as_markup()


# --- Хендлеры действий ---

@recruiter_router.callback_query(F.data.startswith("app_take_"))
async def handle_take_application(callback: CallbackQuery, session: AsyncSession):
    """Рекрутер берет заявку в работу (status=IN_PROGRESS)."""
    await callback.answer("Принимаю заявку в работу...")

    app_id = int(callback.data.split("_")[-1])
    recruiter_tg_id = callback.from_user.id
    recruiter_username = callback.from_user.username or callback.from_user.full_name

    app_service = get_application_service(session)
    success = await app_service.update_application_status(
        application_id=app_id,
        new_status=ApplicationStatus.IN_PROGRESS,
        recruiter_tg_id=recruiter_tg_id
    )

    if success:
        # Обновляем сообщение, используя Markdown V2
        new_text = f"{callback.message.text}\n\n"
        # Экранируем имя пользователя, так как оно может содержать _, * и т.д.
        recruiter_info = escape_input(recruiter_username)
        new_text += f"*ВЗЯТО В РАБОТУ:* \\@{recruiter_info}"

        await callback.message.edit_text(
            new_text,
            reply_markup=create_recruiter_keyboard(app_id),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n⚠️ *ОШИБКА:* Не удалось обновить статус заявки {app_id}\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )


@recruiter_router.callback_query(F.data.startswith("app_status_"))
async def handle_final_status(callback: CallbackQuery, session: AsyncSession):
    """Обработка финальных статусов (INVITED, REJECTED)."""
    await callback.answer("Обновляю статус...")

    parts = callback.data.split("_")
    new_status_str = parts[2]
    app_id = int(parts[3])

    try:
        new_status = ApplicationStatus(new_status_str)
    except ValueError:
        await callback.answer("Неверный статус.", show_alert=True)
        return

    recruiter_tg_id = callback.from_user.id
    recruiter_username = callback.from_user.username or callback.from_user.full_name

    app_service = get_application_service(session)
    success = await app_service.update_application_status(
        application_id=app_id,
        new_status=new_status,
        recruiter_tg_id=recruiter_tg_id,
        reason=f"Обновлено рекрутером @{recruiter_username}"
    )

    if success:
        # Обновляем сообщение, удаляя кнопки
        status_emoji = "✅" if new_status == ApplicationStatus.INVITED else "❌"
        recruiter_info = escape_input(recruiter_username)

        new_text = f"{status_emoji} *СТАТУС: {new_status.value}* Обработано рекрутером \\@{recruiter_info}\n\n{callback.message.text}"

        await callback.message.edit_text(
            new_text,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n⚠️ *ОШИБКА:* Не удалось обновить статус заявки {app_id}\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
