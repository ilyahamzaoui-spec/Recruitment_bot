# bot_welcome/handlers/admin.py
from aiogram.filters import Filter
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot_welcome.services.content_service import ContentService
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
import json

admin_router = Router()


# FSM-состояния для админ-панели
class AdminStates(StatesGroup):
    waiting_for_welcome_text = State()
    waiting_for_links_json = State()
    waiting_for_new_vacancy_data = State()
    waiting_for_toggle_vacancy_id = State()


def get_service(session: AsyncSession) -> ContentService:
    return ContentService(session)


class IsAdmin(Filter):
    """Проверяет, является ли отправитель сообщения администратором."""

    # Этот метод вызывается Aiogram при обработке сообщения
    async def __call__(self, message: Message) -> bool:
        # Проверяем, находится ли ID пользователя в списке ADMIN_IDS
        return message.from_user.id in settings.ADMIN_IDS


@admin_router.message(F.text == "/admin", IsAdmin())
async def cmd_admin(message: Message):
    """Главное меню админ-панели."""
    text = "**⚙️ Панель Администратора Бот №1:**\n"
    text += "/update_welcome - Обновить текст приветствия и ссылки\n"
    text += "/add_vacancy - Добавить новую вакансию в кэш\n"
    text += "/toggle_vacancy - Изменить статус активности вакансии (по ID поста)"

    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


# --- 1. Обновление приветственного контента ---

@admin_router.message(F.text == "/update_welcome", IsAdmin())
async def cmd_update_welcome(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_welcome_text)
    await message.answer(
        "Введите **новый текст приветствия** (поддерживается Markdown):",
        parse_mode=ParseMode.MARKDOWN
    )


@admin_router.message(AdminStates.waiting_for_welcome_text, IsAdmin())
async def process_new_welcome_text(message: Message, state: FSMContext):
    await state.update_data(new_welcome_text=message.html_text)  # Сохраняем как HTML/Markdown
    await state.set_state(AdminStates.waiting_for_links_json)
    await message.answer(
        "Отлично. Теперь введите **полезные ссылки** в формате **JSON**:\n"
        'Пример: `[{"title": "GitHub", "url": "http://..."}]`',
        parse_mode=ParseMode.MARKDOWN
    )


@admin_router.message(AdminStates.waiting_for_links_json, IsAdmin())
async def process_new_links_json(message: Message, state: FSMContext, session: AsyncSession):
    try:
        links_data = json.loads(message.text)
        if not isinstance(links_data, list):
            raise ValueError("JSON должен быть списком.")

        data = await state.get_data()
        new_text = data['new_welcome_text']

        service = get_service(session)
        await service.update_welcome_content(new_text, links_data)

        await message.answer("✅ **Приветственный контент успешно обновлен!**")
        await state.clear()
    except json.JSONDecodeError:
        await message.answer("❌ **Ошибка:** Неверный формат JSON. Попробуйте снова.")
    except ValueError as e:
        await message.answer(f"❌ **Ошибка:** {e}")
    except Exception as e:
        await message.answer(f"❌ **Ошибка БД:** {e}")
        await state.clear()


# --- 2. Добавление вакансии в кэш ---

@admin_router.message(F.text == "/add_vacancy", IsAdmin())
async def cmd_add_vacancy(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_new_vacancy_data)
    await message.answer(
        "Введите данные новой вакансии в формате:\n"
        "**Название вакансии**\n"
        "**Ссылка на пост**\n"
        "**ID поста (только цифры)**\n"
        "*(Каждый параметр в новой строке)*"
    )


@admin_router.message(AdminStates.waiting_for_new_vacancy_data, IsAdmin())
async def process_new_vacancy_data(message: Message, state: FSMContext, session: AsyncSession):
    try:
        lines = message.text.strip().split('\n')
        if len(lines) != 3:
            raise ValueError("Необходимо 3 строки: Название, Ссылка, ID поста.")

        title = lines[0].strip()
        link = lines[1].strip()
        post_id = int(lines[2].strip())

        service = get_service(session)
        if await service.add_vacancy_to_cache(title, link, post_id):
            await message.answer(f"✅ **Вакансия '{title}' успешно добавлена в кэш!**")
        else:
            await message.answer(f"⚠️ **Вакансия с ID {post_id} уже существует!**")

        await state.clear()

    except ValueError as e:
        await message.answer(f"❌ **Ошибка:** {e}")
    except Exception as e:
        await message.answer(f"❌ **Ошибка БД:** {e}")
        await state.clear()


# --- 3. Изменение статуса активности ---

@admin_router.message(F.text == "/toggle_vacancy", IsAdmin())
async def cmd_toggle_vacancy(message: Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_toggle_vacancy_id)
    await message.answer(
        "Введите **ID поста** и **новый статус** через пробел (0 - неактивна, 1 - активна):\n"
        "Пример: `12345 0`"
    )


@admin_router.message(AdminStates.waiting_for_toggle_vacancy_id, IsAdmin())
async def process_toggle_vacancy(message: Message, state: FSMContext, session: AsyncSession):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Необходимы ID поста и статус (0/1).")

        post_id = int(parts[0])
        status = int(parts[1])

        if status not in [0, 1]:
            raise ValueError("Статус должен быть 0 (неактивна) или 1 (активна).")

        is_active = bool(status)

        service = get_service(session)
        if await service.toggle_vacancy_active(post_id, is_active):
            status_text = "Активна" if is_active else "Неактивна"
            await message.answer(f"✅ **Статус вакансии с ID {post_id} обновлен:** {status_text}.")
        else:
            await message.answer(f"⚠️ **Ошибка:** Вакансия с ID {post_id} не найдена.")

        await state.clear()

    except ValueError as e:
        await message.answer(f"❌ **Ошибка:** {e}")
    except Exception as e:
        await message.answer(f"❌ **Ошибка БД:** {e}")
        await state.clear()