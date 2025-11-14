# bot_welcome/handlers/user.py
from aiogram import Router, types, F, Bot
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.config import settings
import json
import logging
import re
from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot_welcome.services.content_service import ContentService
from bot_3_qc.handlers.recruiter import format_application_message, create_recruiter_keyboard  # QC-функции
from bot_welcome.services.application_service import ApplicationService
from bot_welcome.models.db_models import CachedVacancy, Application

user_router = Router()


# --- FSM для Quick Apply ---
class QuickApply(StatesGroup):
    choosing_vacancy = State()
    waiting_fio = State()
    waiting_contact = State()
    waiting_email = State()
    waiting_level = State()
    waiting_skills = State()
    waiting_experience = State()
    waiting_resume = State()


# --- Вспомогательная функция для ручного экранирования Markdown V2 ---

SPECIAL_CHARS = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']


def escape_markdown_v2(text: Optional[str]) -> str:
    """Экранирует специальные символы MarkdownV2 для финального сообщения кандидату."""
    if not text:
        return "Н\\/Д"

    # 1. Сначала убираем символы, которые могут быть частью разметки, но являются вводом пользователя
    # (чтобы избежать конфликтов с внутренним синтаксисом)
    text = text.replace('*', '').replace('_', '').replace('`', '')

    # 2. Экранируем все остальные специальные символы V2
    for char in SPECIAL_CHARS:
        text = text.replace(char, f'\\{char}')

    return text.strip()


# --- Вспомогательные функции для DI ---
def get_content_service(session: AsyncSession) -> ContentService:
    return ContentService(session)


def get_application_service(session: AsyncSession) -> ApplicationService:
    return ApplicationService(session)


# --- Вспомогательные функции для клавиатуры ---

async def create_main_keyboard(vacancies: list) -> types.InlineKeyboardMarkup:
    # ... (код клавиатуры остается без изменений) ...
    builder = InlineKeyboardBuilder()
    vac_count = sum(1 for v in vacancies if v.is_active)

    builder.button(text=f"📋 Вакансии ({vac_count})", callback_data="show_vacancies")
    builder.button(text="🔗 Полезные ресурсы", callback_data="show_links")
    builder.button(text="❓ Справка", callback_data="show_help")

    builder.adjust(1)
    return builder.as_markup()


async def create_vacancy_selection_keyboard(vacancies: list) -> types.InlineKeyboardMarkup:
    # ... (код клавиатуры остается без изменений) ...
    builder = InlineKeyboardBuilder()
    for vacancy in vacancies:
        builder.button(text=vacancy.vacancy_title, callback_data=f"apply_{vacancy.post_id}")

    builder.button(text="↩️ В главное меню", callback_data="start_menu")
    builder.adjust(1)
    return builder.as_markup()


# --- Хендлеры команд и Callback'ов (Приветственный Гид) ---

async def send_welcome_message(message: Message, service: ContentService):
    """Отправляет полное приветственное сообщение (использует Markdown V2)."""
    welcome_text, _ = await service.get_welcome_data()
    vacancies = await service.get_latest_vacancies(limit=5)
    welcome_text_esc = escape_markdown_v2(welcome_text)

    vac_text_part_raw = service.format_vacancies_text(vacancies)

    vac_text_part_esc = escape_markdown_v2(vac_text_part_raw)

    # Используем Markdown V2 для welcome_text (предполагая, что он был очищен в админке или экранирован)
    final_text = f"{welcome_text_esc}\n\n{vac_text_part_esc}"

    keyboard = await create_main_keyboard(vacancies)

    await message.answer(
        final_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True
    )


@user_router.message(F.text.in_(['/start', '/help']))
async def handle_start_and_help(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка /start и /help."""
    await state.clear()  # Сбрасываем FSM при старте
    service = get_content_service(session)
    await send_welcome_message(message, service)


@user_router.callback_query(F.data == "show_vacancies")
async def handle_show_vacancies(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("Загружаю вакансии...")
    service = get_content_service(session)
    vacancies = await service.get_latest_vacancies(limit=10)

    text = service.format_vacancies_text(vacancies)

    builder = InlineKeyboardBuilder()
    if vacancies:
        builder.button(text="✈️ Откликнуться на вакансию", callback_data="init_apply")

    builder.button(text="↩️ В главное меню", callback_data="start_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN,  # Оставляем Markdown V1 здесь для совместимости с format_vacancies_text
        disable_web_page_preview=True
    )


@user_router.callback_query(F.data == "show_links")
async def handle_show_links(callback: CallbackQuery, session: AsyncSession):
    """Показывает полезные ссылки."""
    await callback.answer()
    service = get_content_service(session)
    _, links = await service.get_welcome_data()

    # ВАЖНО: Текст должен быть MarkdownV2, чтобы избежать ошибок
    text = "*🔗 Полезные ресурсы:*\n"
    builder = InlineKeyboardBuilder()

    for item in links:
        # Экранируем title в кнопке
        builder.button(text=escape_markdown_v2(item['title']), url=item['url'])

    builder.button(text="↩️ В главное меню", callback_data="start_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


@user_router.callback_query(F.data == "start_menu")
async def handle_back_to_menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Возвращает в главное меню."""
    await state.clear()
    await callback.answer()
    service = get_content_service(session)
    await send_welcome_message(callback.message, service)


@user_router.message(F.new_chat_members)
async def handle_new_member_in_chat(message: Message, session: AsyncSession):
    """Отправляет приветственное сообщение в ЛС новому участнику (использует Markdown V2)."""
    service = get_content_service(session)
    for member in message.new_chat_members:
        if member.is_bot: continue

        try:
            await message.bot.send_message(
                chat_id=member.id,
                text="👋 *Добро пожаловать в канал*\\n\\nНажмите /start, чтобы увидеть актуальные вакансии и полезные ссылки\\.",
                parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
            )
        except Exception as e:
            logging.error(f"Не удалось отправить приветствие пользователю {member.id}: {e}")


# --- Хендлеры Quick Apply ---

@user_router.callback_query(F.data == "init_apply")
async def init_apply_process(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало процесса отклика: выбор способа."""
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 Заполнить на сайте", url="https://ваша.форма.на.сайте")
    builder.button(text="✈️ Откликнуться в Telegram", callback_data="start_telegram_apply")
    builder.button(text="↩️ Отмена", callback_data="start_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "*📝 Выберите способ отклика:*",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


@user_router.callback_query(F.data == "start_telegram_apply")
async def start_telegram_apply(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Переход к выбору вакансии."""
    await callback.answer()
    content_service = get_content_service(session)
    vacancies = await content_service.get_latest_vacancies(limit=10)

    if not vacancies:
        await callback.message.edit_text(
            "К сожалению, на данный момент нет активных вакансий для отклика\\. Попробуйте позже\\.",
            parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
        )
        await state.clear()
        return

    keyboard = await create_vacancy_selection_keyboard(vacancies)

    await state.set_state(QuickApply.choosing_vacancy)
    await state.update_data(vacancies_cache={v.post_id: v.vacancy_title for v in vacancies})

    await callback.message.edit_text(
        "*💼 Шаг 1/7:* Выберите вакансию, на которую хотите откликнуться:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


@user_router.callback_query(QuickApply.choosing_vacancy, F.data.startswith("apply_"))
async def process_vacancy_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор вакансии -> Запрос ФИО."""
    await callback.answer()
    vacancy_post_id = int(callback.data.split("_")[1])
    data = await state.get_data()

    vacancy_title = data['vacancies_cache'].get(vacancy_post_id, "Неизвестная вакансия")

    # 1. Создаем запись отклика в БД для сохранения FSM-контекста
    app_service = get_application_service(session)
    application = await app_service.create_new_application(
        candidate_tg_id=callback.from_user.id,
        vacancy_id=vacancy_post_id,
        vacancy_title=vacancy_title,
        temp_data=data  # Сохраняем текущий контекст
    )

    # 2. Сохраняем ID отклика и название вакансии в FSM
    await state.update_data(
        application_id=application.id,
        vacancy_id=vacancy_post_id,
        vacancy_title=vacancy_title
    )

    # 3. Переход к следующему состоянию
    await state.set_state(QuickApply.waiting_fio)
    await callback.message.edit_text(
        f"✅ Вы выбрали: *{escape_markdown_v2(vacancy_title)}*\\n\\n"
        f"*👤 Шаг 2/7:* Введите Ваши *полные ФИО*:",
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


@user_router.message(QuickApply.waiting_fio)
async def process_fio(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ФИО -> Запрос контакта."""
    fio = message.text.strip()
    if len(fio) < 5 or len(fio.split()) < 2:
        await message.answer("Пожалуйста, введите корректные полные ФИО \\(минимум Имя и Фамилия\\)\\.",
                             parse_mode=ParseMode.MARKDOWN_V2)  # <--- ИСПРАВЛЕНИЕ
        return

    await state.update_data(full_name=fio)

    # Обновление временных данных в БД
    data = await state.get_data()
    app_service = get_application_service(session)
    await app_service.update_temp_data(data['application_id'], data)

    # Клавиатура для быстрого ввода номера
    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Поделиться контактом", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await state.set_state(QuickApply.waiting_contact)
    await message.answer(
        "*📞 Шаг 3/7:* Отправьте Ваш *номер телефона* или нажмите кнопку 'Поделиться контактом':",
        reply_markup=reply_keyboard,
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


@user_router.message(QuickApply.waiting_contact)
@user_router.message(QuickApply.waiting_contact, F.content_type == types.ContentType.CONTACT)
async def process_contact(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка контакта -> Запрос Email."""
    phone = message.contact.phone_number if message.contact else message.text.strip()

    if not phone:
        await message.answer("Пожалуйста, отправьте корректный номер телефона\\.",
                             parse_mode=ParseMode.MARKDOWN_V2)  # <--- ИСПРАВЛЕНИЕ
        return

    await state.update_data(phone=phone)

    # Обновление временных данных в БД
    data = await state.get_data()
    app_service = get_application_service(session)
    await app_service.update_temp_data(data['application_id'], data)

    await state.set_state(QuickApply.waiting_email)
    await message.answer(
        "*📧 Шаг 4/7:* Введите Ваш *рабочий Email* для связи с рекрутером:",
        reply_markup=types.ReplyKeyboardRemove(),
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


# Валидация Email (простой regex)
EMAIL_REGEX = r"[^@]+@[^@]+\.[^@]+"


@user_router.message(QuickApply.waiting_email)
async def process_email(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка Email -> Запрос уровня позиции."""
    email = message.text.strip()

    if not re.fullmatch(EMAIL_REGEX, email):
        await message.answer("❌ Неверный формат Email\\. Пожалуйста, введите корректный адрес\\.",
                             parse_mode=ParseMode.MARKDOWN_V2)  # <--- ИСПРАВЛЕНИЕ
        return

    await state.update_data(email=email,
                            telegram_username=f"@{message.from_user.username}" if message.from_user.username else "Нет")

    # Обновление временных данных в БД
    data = await state.get_data()
    app_service = get_application_service(session)
    await app_service.update_temp_data(data['application_id'], data)

    # Клавиатура выбора уровня
    builder = InlineKeyboardBuilder()
    levels = ["Intern", "Junior", "Middle", "Senior", "Lead"]
    for level in levels:
        builder.button(text=level, callback_data=f"level_{level}")
    builder.adjust(2)

    await state.set_state(QuickApply.waiting_level)
    await message.answer(
        "*🎯 Шаг 5/7:* Выберите Ваш *уровень* позиции:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN_V2  # <--- ИСПРАВЛЕНИЕ
    )


@user_router.callback_query(QuickApply.waiting_level, F.data.startswith("level_"))
async def process_level(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка уровня -> Запрос скиллов."""
    await callback.answer()
    level = callback.data.split("_")[1]
    await state.update_data(level=level)

    # Обновление временных данных в БД
    data = await state.get_data()
    app_service = get_application_service(session)
    await app_service.update_temp_data(data['application_id'], data)

    await state.set_state(QuickApply.waiting_skills)
    await callback.message.edit_text(
        f"✨ Шаг 6/7: Перечислите ключевые технологии/скиллы через запятую \\(например: Java\\, Spring Boot\\, PostgreSQL\\, Docker\\):",
        reply_markup=None,
        parse_mode=ParseMode.MARKDOWN_V2
    )


@user_router.message(QuickApply.waiting_skills)
async def process_skills(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка скиллов -> Запрос опыта."""
    skills = message.text.strip()

    if len(skills) < 10:
        await message.answer("Пожалуйста, опишите Ваши ключевые навыки более подробно\\.",
                             parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(skills=skills)

    # Обновление временных данных в БД
    data = await state.get_data()
    app_service = get_application_service(session)
    await app_service.update_temp_data(data['application_id'], data)

    await state.set_state(QuickApply.waiting_experience)
    await message.answer(
        "📝 Финальный Шаг \\(7/7\\): Опишите кратко Ваш опыт работы и достижения \\(2\\-3 предложения\\):",
        parse_mode=ParseMode.MARKDOWN_V2
    )


@user_router.message(QuickApply.waiting_experience)
async def process_experience(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка опыта -> Запрос резюме (финал)."""
    experience = message.text.strip()

    if len(experience) < 20:
        await message.answer("Пожалуйста, опишите опыт более подробно \\(минимум 20 символов\\)\\.",
                             parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(experience=experience)

    # Обновление временных данных в БД
    data = await state.get_data()
    app_service = get_application_service(session)
    await app_service.update_temp_data(data['application_id'], data)

    # Клавиатура для пропуска резюме
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭️ Пропустить", callback_data="skip_resume")
    builder.adjust(1)

    await state.set_state(QuickApply.waiting_resume)
    await message.answer(
        "📎 *Завершение:* Пришлите Ваше *резюме* \\(PDF/DOCX\\) *файлом* или *ссылкой* на него, или нажмите 'Пропустить':",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.MARKDOWN_V2
    )


# --- ФИНАЛИЗАЦИЯ ОТКЛИКА ---

# Обработка файла/ссылки или кнопки "Пропустить"
@user_router.message(QuickApply.waiting_resume,
                     F.content_type.in_({types.ContentType.DOCUMENT, types.ContentType.TEXT}))
@user_router.callback_query(QuickApply.waiting_resume, F.data == "skip_resume")
async def finalize_apply(update: types.Union[Message, CallbackQuery], state: FSMContext, session: AsyncSession):
    is_message = isinstance(update, Message)

    # 1. Получение данных резюме
    if is_message:
        if update.document and update.document.file_name.lower().endswith(('.pdf', '.doc', '.docx')):
            # Резюме в виде файла. Мы не загружаем его, а сохраняем file_id или ссылку
            resume_data = {"type": "file_id", "value": update.document.file_id}
            resume_link = f"File ID: {update.document.file_id}"
        elif update.text and (update.text.lower().startswith('http') or update.text.lower().startswith('www')):
            # Резюме в виде ссылки
            resume_data = {"type": "link", "value": update.text.strip()}
            resume_link = update.text.strip()
        else:
            await update.answer("❌ Пожалуйста, отправьте файл PDF/DOCX, действующую ссылку или нажмите 'Пропустить'\\.",
                                parse_mode=ParseMode.MARKDOWN_V2)
            return
    else:  # Кнопка "Пропустить"
        await update.answer()
        resume_data = {"type": "skip", "value": "Skipped"}
        resume_link = "Не предоставлено."

    # 2. Сбор всех данных
    state_data = await state.get_data()

    final_data = {
        "full_name": state_data.get('full_name'),
        "contacts": {
            "phone": state_data.get('phone'),
            "email": state_data.get('email'),
            "telegram_username": state_data.get('telegram_username'),
            "tg_id": update.from_user.id
        },
        "professional_info": {
            "level": state_data.get('level'),
            "skills": state_data.get('skills'),
            "experience": state_data.get('experience'),
        },
        "resume_link": resume_link  # Отправляем ссылку/ID во внешнюю систему
    }

    application_id = state_data['application_id']
    vacancy_post_id = state_data['vacancy_id']
    vacancy_title = state_data['vacancy_title']

    # 3. Финализация и отправка в API
    app_service = get_application_service(session)
    success, result_message = await app_service.finalize_and_send_application(application_id, final_data)

    # 4. Коммуникация с кандидатом (ФИНАЛЬНЫЙ ОТВЕТ)
    if success:
        # Пытаемся получить рекрутера по направлению (берем первое слово из skills)
        vacancy_result = await session.execute(
            select(CachedVacancy).filter_by(post_id=vacancy_post_id)
        )
        vacancy = vacancy_result.scalar_one_or_none()
        if vacancy and vacancy.direction:
            direction = vacancy.direction.lower()
        else:
            logging.error(f"Vacancy ID {vacancy_post_id} not found in cache. Defaulting direction.")
            direction = 'default'
        recruiter = await app_service.get_recruiter_by_direction(direction)

        recruiter_contact = recruiter.recruiter_username if recruiter and recruiter.recruiter_username else "default_recruiter"

        final_response = (
            f"🎉 *Ваш отклик успешно принят*\n"
            f"*🎯 Вакансия:* {escape_markdown_v2(vacancy_title)}\n"
            f"*📞 Для быстрой связи напишите Вашему рекрутеру:*\n"
            f"👉 @{escape_markdown_v2(recruiter_contact)}\n"
            f"Укажите, что Вы по поводу вакансии \\[*{escape_markdown_v2(vacancy_title)}*\\]\\."
        )

        # --- БЛОК ОТПРАВКИ УВЕДОМЛЕНИЯ В QC-ЧАТ ---
        # 1. Загружаем объект Application для полного доступа к данным
        application = await session.get(Application, application_id)

        # 2. Форматируем и отправляем сообщение
        if application:
            recruiter_bot_instance = Bot(token=settings.RECRUITER_BOT_TOKEN)

            qc_message = format_application_message(application)
            qc_keyboard = create_recruiter_keyboard(application_id)

            try:
                await recruiter_bot_instance.send_message(
                    chat_id=settings.QC_CHAT_ID,
                    text=qc_message,
                    reply_markup=qc_keyboard,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                await recruiter_bot_instance.session.close()  # Закрыть сессию
            except Exception as e:
                logging.error(f"Failed to send QC notification for app {application_id}: {e}")
        # ---------------------------------------------

    else:
        # Если API не сработало, показываем пользователю ошибку (или мягкое сообщение)
        logging.error(f"API send failed for app {application_id}: {result_message}")
        final_response = (
            "⚠️ *Ошибка отправки\\.*\\n\\n"
            "Ваш отклик сохранен, но произошел сбой при передаче данных в рекрутинговую систему\\.\\n"
            "Мы свяжемся с Вами по почте или телефону\\. Приносим извинения\\."
        )

    await update.bot.send_message(
        chat_id=update.from_user.id,
        text=final_response,
        parse_mode=ParseMode.MARKDOWN_V2
    )

    await state.clear()
