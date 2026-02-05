from __future__ import annotations

from aiogram import F, Router
import csv
from pathlib import Path
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import ADMIN_GROUP_ID, ADMIN_IDS, BTN, LOG_PATH
from app.db import database as db
from app.services.catalog import delivery_caption, format_price

router = Router()

def _extract_image_file_id(message: Message) -> str | None:
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        mime = message.document.mime_type or ""
        if mime.startswith("image/"):
            return message.document.file_id
    return None


async def _send_and_pin_admin_panel(message: Message) -> None:
    msg = await message.answer("Открыть панель:", reply_markup=admin_panel_inline_kb())
    if ADMIN_GROUP_ID and message.chat.id == ADMIN_GROUP_ID:
        try:
            await message.bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=msg.message_id,
                disable_notification=True,
            )
        except Exception:
            pass

async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
    if callback.data and str(callback.data).startswith("admin:menu:"):
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def _finalize_step_message(callback: CallbackQuery, text: str) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=None)
        return
    except Exception:
        pass
    await _clear_inline_keyboard(callback)

@router.message(F.chat.id == ADMIN_GROUP_ID, F.reply_to_message)
async def support_reply_from_admin(message: Message) -> None:
    if not await is_group_admin(message):
        return
    if message.text and message.text.startswith("/"):
        return

    user_id = await db.get_user_by_admin_reply(
        ADMIN_GROUP_ID, message.reply_to_message.message_id
    )
    if not user_id:
        return

    if message.text:
        await message.bot.send_message(user_id, message.text)
    elif message.photo:
        await message.bot.send_photo(
            user_id,
            photo=message.photo[-1].file_id,
            caption=message.caption or "",
        )
    elif message.document:
        await message.bot.send_document(
            user_id,
            document=message.document.file_id,
            caption=message.caption or "",
        )
    else:
        await message.answer("Можно отправлять только текст/фото/документ.")

    return


@router.callback_query(F.data.startswith("support:block:"))
async def support_block_user(callback: CallbackQuery) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Недоступно", show_alert=True)
        return

    user_id = await db.get_user_by_admin_reply(
        ADMIN_GROUP_ID, callback.message.message_id
    )
    if not user_id:
        await callback.answer("Не найдено обращение", show_alert=True)
        return

    await db.set_support_blocked(user_id, 1)
    await callback.bot.send_message(user_id, "Поддержка для вашего аккаунта закрыта.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Поддержка закрыта")


@router.callback_query(F.data == "support:close")
async def support_close_dialog(callback: CallbackQuery) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    if callback.message.chat.id != ADMIN_GROUP_ID:
        await callback.answer("Недоступно", show_alert=True)
        return

    user_id = await db.get_user_by_admin_reply(
        ADMIN_GROUP_ID, callback.message.message_id
    )
    if not user_id:
        await callback.answer("Не найдено обращение", show_alert=True)
        return

    await callback.bot.send_message(user_id, "Диалог поддержки закрыт админом.")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("✅ Диалог закрыт")


class AdminStates(StatesGroup):
    add_city_name = State()
    delete_city_pick = State()
    add_product_city = State()
    add_product_area = State()
    add_product_variant = State()
    add_product_class = State()
    add_product_photo = State()
    add_product_name = State()
    add_product_desc = State()
    add_product_price = State()
    add_product_stock = State()
    add_area_city = State()
    add_area_name = State()
    rename_city_pick = State()
    rename_city_name = State()
    rename_area_city = State()
    rename_area_pick = State()
    rename_area_name = State()
    rename_product_id = State()
    rename_product_name = State()
    rename_variant_pick = State()
    rename_variant_name = State()
    rename_class_variant = State()
    rename_class_pick = State()
    rename_class_name = State()
    delete_area_city = State()
    delete_area_pick = State()
    add_variant_name = State()
    add_class_variant = State()
    add_class_name = State()
    delete_variant_pick = State()
    delete_class_variant = State()
    delete_class_pick = State()
    user_history_id = State()
    variant_photo_pick = State()
    variant_photo_upload = State()
    product_owner_id = State()
    delete_product_id = State()
    payment_details_text = State()


def _get_user_id(message_or_callback) -> int | None:
    return message_or_callback.from_user.id if message_or_callback.from_user else None


async def is_group_admin(message_or_callback) -> bool:
    chat = (
        message_or_callback.chat
        if hasattr(message_or_callback, "chat")
        else message_or_callback.message.chat
    )
    if ADMIN_GROUP_ID == 0 or chat.id != ADMIN_GROUP_ID:
        return False
    user_id = _get_user_id(message_or_callback)
    if not user_id:
        return False
    if ADMIN_IDS and user_id in ADMIN_IDS:
        return True
    try:
        member = await message_or_callback.bot.get_chat_member(chat.id, user_id)
        return member.status in {"creator", "administrator"}
    except Exception:
        return False


async def is_admin(message_or_callback) -> bool:
    user_id = _get_user_id(message_or_callback)
    if user_id and user_id in ADMIN_IDS:
        return True
    chat = (
        message_or_callback.chat
        if hasattr(message_or_callback, "chat")
        else message_or_callback.message.chat
    )
    if ADMIN_GROUP_ID != 0 and chat.id == ADMIN_GROUP_ID:
        return await is_group_admin(message_or_callback)
    return False


def admin_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Каталог", callback_data="admin:section:catalog"
                ),
                InlineKeyboardButton(
                    text="Локации", callback_data="admin:section:locations"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Варианты/Классы",
                    callback_data="admin:section:variants",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Покупки/Отчеты",
                    callback_data="admin:section:reports",
                )
            ],
        ]
    )


def admin_catalog_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_ADD_PRODUCT, callback_data="admin:menu:add_product"
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_PRODUCTS_LIST,
                    callback_data="admin:menu:products_list",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_PRODUCT_DELETE,
                    callback_data="admin:menu:product_delete",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_RENAME_PRODUCT,
                    callback_data="admin:menu:rename_product",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_PRODUCT_OWNER,
                    callback_data="admin:menu:product_owner",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.BACK, callback_data="admin:menu:main"
                )
            ],
        ]
    )


def admin_locations_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_ADD_CITY, callback_data="admin:menu:add_city"
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_ADD_AREA, callback_data="admin:menu:add_area"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_DELETE_CITY,
                    callback_data="admin:menu:delete_city",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_DELETE_AREA,
                    callback_data="admin:menu:delete_area",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_RENAME_CITY, callback_data="admin:menu:rename_city"
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_RENAME_AREA, callback_data="admin:menu:rename_area"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.BACK, callback_data="admin:menu:main"
                )
            ],
        ]
    )


def admin_variants_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_ADD_VARIANT,
                    callback_data="admin:menu:add_variant",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_ADD_CLASS,
                    callback_data="admin:menu:add_class",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_DELETE_VARIANT,
                    callback_data="admin:menu:delete_variant",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_DELETE_CLASS,
                    callback_data="admin:menu:delete_class",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_RENAME_VARIANT,
                    callback_data="admin:menu:rename_variant",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_RENAME_CLASS,
                    callback_data="admin:menu:rename_class",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_VARIANT_PHOTO,
                    callback_data="admin:menu:variant_photo",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN.BACK, callback_data="admin:menu:main"
                )
            ],
        ]
    )


def admin_reports_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_REQUESTS, callback_data="admin:menu:requests"
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_STATS, callback_data="admin:menu:stats"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_REPORTS, callback_data="admin:menu:reports"
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_LOGS, callback_data="admin:menu:logs"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_USER_HISTORY,
                    callback_data="admin:menu:user_history",
                ),
                InlineKeyboardButton(
                    text=BTN.ADMIN_REVIEWS, callback_data="admin:menu:reviews"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BTN.ADMIN_PAYMENT_DETAILS,
                    callback_data="admin:menu:payment_details",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN.BACK, callback_data="admin:menu:main"
                )
            ],
        ]
    )


def admin_panel_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN.ADMIN_PANEL, callback_data="admin:menu:home")]
        ]
    )


def cities_pick_kb(
    cities: list[dict], prefix: str = "admin:city:"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.button(text=city["name"], callback_data=f"{prefix}{city['id']}")
    builder.adjust(2)
    return builder.as_markup()


def areas_pick_kb(
    areas: list[dict], prefix: str = "admin:area:"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for area in areas:
        builder.button(text=area["name"], callback_data=f"{prefix}{area['id']}")
    builder.adjust(2)
    return builder.as_markup()


def variants_pick_kb(variants: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for variant in variants:
        name = variant["name"]
        builder.button(text=f"Товар {name}", callback_data=f"admin:variant:{name}")
    builder.adjust(2)
    return builder.as_markup()


def classes_pick_kb(variant: str, classes: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for class_row in classes:
        class_name = class_row["name"]
        builder.button(
            text=class_name, callback_data=f"admin:class:{variant}:{class_name}"
        )
    builder.adjust(2)
    return builder.as_markup()


def request_actions_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN.CONFIRM, callback_data=f"pay:confirm:{payment_id}"
                ),
                InlineKeyboardButton(
                    text=BTN.REJECT, callback_data=f"pay:reject:{payment_id}"
                ),
            ]
        ]
    )


@router.message(Command("admin"))
async def admin_entry(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await message.answer("Админ-панель:", reply_markup=ReplyKeyboardRemove())
    await _send_and_pin_admin_panel(message)
    await message.answer("Выберите раздел:", reply_markup=admin_main_menu_kb())


@router.message(F.text == BTN.ADMIN_PANEL)
async def admin_panel_button(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await message.answer("Админ-панель:", reply_markup=ReplyKeyboardRemove())
    await _send_and_pin_admin_panel(message)
    await message.answer("Выберите раздел:", reply_markup=admin_main_menu_kb())


@router.callback_query(F.data == "admin:menu:home")
async def admin_menu_home(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await callback.message.answer("Админ-панель:", reply_markup=ReplyKeyboardRemove())
    await _send_and_pin_admin_panel(callback.message)
    await callback.message.answer("Выберите раздел:", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:menu:main")
async def admin_menu_main(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Выберите раздел:", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:section:catalog")
async def admin_section_catalog(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Каталог:", reply_markup=admin_catalog_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:section:locations")
async def admin_section_locations(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Локации:", reply_markup=admin_locations_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:section:variants")
async def admin_section_variants(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Варианты и классификации:", reply_markup=admin_variants_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:section:reports")
async def admin_section_reports(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Покупки и отчеты:", reply_markup=admin_reports_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "admin:menu:add_product")
async def admin_menu_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.add_product_city)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Выберите город:", reply_markup=cities_pick_kb(cities))
    await callback.answer()


@router.callback_query(F.data == "admin:menu:add_city")
async def admin_menu_add_city(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.add_city_name)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Введите название нового города:")
    await callback.answer()

@router.callback_query(F.data == "admin:menu:add_area")
async def admin_menu_add_area(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.add_area_city)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите город для добавления местности:",
        reply_markup=cities_pick_kb(cities, prefix="admin:addareacity:"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:delete_city")
async def admin_menu_delete_city(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.delete_city_pick)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите город для удаления:",
        reply_markup=cities_pick_kb(cities, prefix="admin:citydel:"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:delete_area")
async def admin_menu_delete_area(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.delete_area_city)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите город для удаления местности:",
        reply_markup=cities_pick_kb(cities, prefix="admin:delareacity:"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:rename_city")
async def admin_menu_rename_city(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.rename_city_pick)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Выберите город:", reply_markup=cities_pick_kb(cities))
    await callback.answer()


@router.callback_query(F.data == "admin:menu:rename_product")
async def admin_menu_rename_product(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.rename_product_id)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Введите ID товара:")
    await callback.answer()

@router.callback_query(F.data == "admin:menu:rename_area")
async def admin_menu_rename_area(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.rename_area_city)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите город для поиска местности:",
        reply_markup=cities_pick_kb(cities, prefix="admin:areacity:"),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:rename_variant")
async def admin_menu_rename_variant(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.rename_variant_pick)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите вариант для переименования:",
        reply_markup=variants_pick_kb(variants),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:rename_class")
async def admin_menu_rename_class(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.rename_class_variant)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите вариант для переименования классификации:",
        reply_markup=variants_pick_kb(variants),
    )
    await callback.answer()

@router.callback_query(F.data == "admin:menu:add_variant")
async def admin_menu_add_variant(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.add_variant_name)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Введите название нового варианта:")
    await callback.answer()


@router.callback_query(F.data == "admin:menu:add_class")
async def admin_menu_add_class(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.add_class_variant)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите вариант для новой классификации:",
        reply_markup=variants_pick_kb(variants),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:delete_variant")
async def admin_menu_delete_variant(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.delete_variant_pick)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите вариант для удаления:",
        reply_markup=variants_pick_kb(variants),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:delete_class")
async def admin_menu_delete_class(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.delete_class_variant)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Выберите вариант для удаления классификации:",
        reply_markup=variants_pick_kb(variants),
    )
    await callback.answer()

@router.callback_query(F.data == "admin:menu:variant_photo")
async def admin_menu_variant_photo(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.variant_photo_pick)
    await _clear_inline_keyboard(callback)
    variants = await db.get_variants()
    await callback.message.answer(
        "Выберите вариант:", reply_markup=variants_pick_kb(variants)
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:user_history")
async def admin_menu_user_history(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.user_history_id)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Введите Telegram ID пользователя:")
    await callback.answer()


@router.callback_query(F.data == "admin:menu:reviews")
async def admin_menu_reviews(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    rows = await db.get_recent_reviews(30)
    if not rows:
        await callback.message.answer("Отзывов пока нет.")
        await callback.answer()
        return
    await _clear_inline_keyboard(callback)
    lines = []
    for row in rows:
        lines.append(
            f"#{row['id']} | user {row['user_id']} | order {row['order_id']} | {row['created_at']}\n{row['text']}"
        )
    await callback.message.answer("Последние отзывы:\n\n" + "\n\n".join(lines))
    await callback.answer()


@router.callback_query(F.data == "admin:menu:product_owner")
async def admin_menu_product_owner(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.product_owner_id)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Введите ID товара:")
    await callback.answer()


@router.callback_query(F.data == "admin:menu:products_list")
async def admin_menu_products_list(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    products = await db.list_products(100)
    if not products:
        await callback.message.answer("Ассортимент пуст.")
        await callback.answer()
        return
    await _clear_inline_keyboard(callback)
    lines = []
    for p in products:
        stock = int(p["stock"] or 0)
        status = "в наличии" if stock > 0 else "нет в наличии"
        sold = f", купил: {p['sold_to_user_id']}" if p["sold_to_user_id"] else ""
        lines.append(f"#{p['id']} | {p['title']} | {format_price(int(p['price']))} | {status}{sold}")
    text = "Ассортимент (последние 100):\n" + "\n".join(lines)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:menu:product_delete")
async def admin_menu_product_delete(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.delete_product_id)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Введите ID товара для удаления:")
    await callback.answer()


@router.callback_query(F.data == "admin:menu:logs")
async def admin_menu_logs(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    try:
        await callback.bot.send_document(
            callback.message.chat.id,
            document=FSInputFile(str(LOG_PATH)),
            caption="Логи бота",
        )
    except Exception:
        await callback.message.answer("Логи недоступны или файл пуст.")
    await callback.answer()


@router.callback_query(F.data == "admin:menu:requests")
async def admin_menu_requests(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    payments = await db.list_pending_payments()
    if not payments:
        await callback.message.answer("Нет заявок на подтверждение.")
        await callback.answer()
        return
    await _clear_inline_keyboard(callback)
    await callback.message.answer(f"Ожидают подтверждения: {len(payments)}")
    for payment in payments:
        text = (
            f"Заявка #{payment['id']}\n"
            f"Пользователь: {payment['user_id']}\n"
            f"Сумма: {format_price(payment['total'])}\n"
            f"Создана: {payment['created_at']}"
        )
        await callback.message.answer_photo(
            payment["photo_file_id"],
            caption=text,
            reply_markup=request_actions_kb(int(payment["id"])),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:stats")
async def admin_menu_stats(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await _clear_inline_keyboard(callback)
    stats = await db.get_stats()
    text = (
        "Статистика:\n"
        f"Всего заказов: {stats['orders_total']}\n"
        f"Оплачено: {stats['orders_paid']}\n"
        f"В ожидании проверки: {stats['orders_pending']}\n"
        f"Отклонено: {stats['orders_rejected']}\n"
        f"Заявок в ожидании: {stats['payments_pending']}"
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin:menu:payment_details")
async def admin_menu_payment_details(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminStates.payment_details_text)
    await _clear_inline_keyboard(callback)
    await callback.message.answer(
        "Отправьте новые реквизиты одним сообщением. "
        "Это сообщение будет показываться пользователям в разделе оплаты."
    )
    await callback.answer()


@router.callback_query(F.data == "admin:menu:reports")
async def admin_menu_reports(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    rows = await db.get_payments_report()
    if not rows:
        await callback.message.answer("Нет данных для отчета.")
        await callback.answer()
        return
    report_path = Path("data") / "payments_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "payment_id",
                "order_id",
                "user_id",
                "username",
                "first_name",
                "total",
                "payment_status",
                "order_status",
                "payment_created_at",
                "payment_processed_at",
                "order_created_at",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["payment_id"],
                    row["order_id"],
                    row["user_id"],
                    row["username"] or "",
                    row["first_name"] or "",
                    row["total"],
                    row["payment_status"],
                    row["order_status"],
                    row["payment_created_at"],
                    row["payment_processed_at"] or "",
                    row["order_created_at"],
                ]
            )
    try:
        await callback.bot.send_document(
            callback.message.chat.id,
            document=FSInputFile(str(report_path)),
            caption="Отчет по оплатам (CSV)",
        )
    except Exception:
        await callback.message.answer("Не удалось отправить отчет.")
    await callback.answer()


@router.message(F.text == BTN.ADMIN_ADD_PRODUCT)
async def admin_add_product_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.add_product_city)
    await message.answer("Выберите город:", reply_markup=cities_pick_kb(cities))


@router.message(F.text == BTN.ADMIN_ADD_CITY)
async def admin_add_city_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.add_city_name)
    await message.answer("Введите название нового города:")

@router.message(F.text == BTN.ADMIN_ADD_AREA)
async def admin_add_area_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.add_area_city)
    await message.answer(
        "Выберите город для добавления местности:",
        reply_markup=cities_pick_kb(cities, prefix="admin:addareacity:"),
    )


@router.message(F.text == BTN.ADMIN_DELETE_CITY)
async def admin_delete_city_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.delete_city_pick)
    await message.answer(
        "Выберите город для удаления:",
        reply_markup=cities_pick_kb(cities, prefix="admin:citydel:"),
    )


@router.message(F.text == BTN.ADMIN_DELETE_AREA)
async def admin_delete_area_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.delete_area_city)
    await message.answer(
        "Выберите город для удаления местности:",
        reply_markup=cities_pick_kb(cities, prefix="admin:delareacity:"),
    )


@router.message(F.text == BTN.ADMIN_RENAME_CITY)
async def admin_rename_city_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.rename_city_pick)
    await message.answer("Выберите город:", reply_markup=cities_pick_kb(cities))


@router.message(F.text == BTN.ADMIN_RENAME_PRODUCT)
async def admin_rename_product_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.rename_product_id)
    await message.answer("Введите ID товара:")

@router.message(F.text == BTN.ADMIN_RENAME_AREA)
async def admin_rename_area_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.rename_area_city)
    await message.answer(
        "Выберите город для поиска местности:",
        reply_markup=cities_pick_kb(cities, prefix="admin:areacity:"),
    )


@router.message(F.text == BTN.ADMIN_RENAME_VARIANT)
async def admin_rename_variant_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.rename_variant_pick)
    await message.answer(
        "Выберите вариант для переименования:",
        reply_markup=variants_pick_kb(variants),
    )


@router.message(F.text == BTN.ADMIN_RENAME_CLASS)
async def admin_rename_class_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.rename_class_variant)
    await message.answer(
        "Выберите вариант для переименования классификации:",
        reply_markup=variants_pick_kb(variants),
    )

@router.message(F.text == BTN.ADMIN_ADD_VARIANT)
async def admin_add_variant_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.add_variant_name)
    await message.answer("Введите название нового варианта:")


@router.message(F.text == BTN.ADMIN_ADD_CLASS)
async def admin_add_class_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.add_class_variant)
    await message.answer(
        "Выберите вариант для новой классификации:",
        reply_markup=variants_pick_kb(variants),
    )


@router.message(F.text == BTN.ADMIN_DELETE_VARIANT)
async def admin_delete_variant_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.delete_variant_pick)
    await message.answer(
        "Выберите вариант для удаления:",
        reply_markup=variants_pick_kb(variants),
    )


@router.message(F.text == BTN.ADMIN_DELETE_CLASS)
async def admin_delete_class_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    variants = await db.get_variants()
    await state.set_state(AdminStates.delete_class_variant)
    await message.answer(
        "Выберите вариант для удаления классификации:",
        reply_markup=variants_pick_kb(variants),
    )

@router.message(F.text == BTN.ADMIN_USER_HISTORY)
async def admin_user_history_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.user_history_id)
    await message.answer("Введите Telegram ID пользователя:")


@router.message(F.text == BTN.ADMIN_REVIEWS)
async def admin_show_reviews(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    rows = await db.get_recent_reviews(30)
    if not rows:
        await message.answer("Отзывов пока нет.")
        return
    lines = []
    for row in rows:
        lines.append(
            f"#{row['id']} | user {row['user_id']} | order {row['order_id']} | {row['created_at']}\n{row['text']}"
        )
    await message.answer("Последние отзывы:\n\n" + "\n\n".join(lines))


@router.message(F.text == BTN.ADMIN_VARIANT_PHOTO)
async def admin_variant_photo_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.variant_photo_pick)
    variants = await db.get_variants()
    await message.answer("Выберите вариант:", reply_markup=variants_pick_kb(variants))


@router.message(F.text == BTN.ADMIN_PRODUCTS_LIST)
async def admin_products_list(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    products = await db.list_products(100)
    if not products:
        await message.answer("Ассортимент пуст.")
        return
    lines = []
    for p in products:
        stock = int(p["stock"] or 0)
        status = "в наличии" if stock > 0 else "нет в наличии"
        sold = f", купил: {p['sold_to_user_id']}" if p["sold_to_user_id"] else ""
        lines.append(f"#{p['id']} | {p['title']} | {format_price(int(p['price']))} | {status}{sold}")
    text = "Ассортимент (последние 100):\n" + "\n".join(lines)
    await message.answer(text)


@router.message(F.text == BTN.ADMIN_PRODUCT_DELETE)
async def admin_product_delete_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.delete_product_id)
    await message.answer("Введите ID товара для удаления:")


@router.message(F.text == BTN.ADMIN_LOGS)
async def admin_send_logs(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    try:
        await message.bot.send_document(
            message.chat.id,
            document=FSInputFile(str(LOG_PATH)),
            caption="Логи бота",
        )
    except Exception:
        await message.answer("Логи недоступны или файл пуст.")


@router.message(F.text == BTN.ADMIN_PRODUCT_OWNER)
async def admin_product_owner_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.product_owner_id)
    await message.answer("Введите ID товара:")


@router.message(F.text == BTN.ADMIN_REQUESTS)
async def admin_show_requests(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    payments = await db.list_pending_payments()
    if not payments:
        await message.answer("Нет заявок на подтверждение.")
        return
    await message.answer(f"Ожидают подтверждения: {len(payments)}")
    for payment in payments:
        text = (
            f"Заявка #{payment['id']}\n"
            f"Пользователь: {payment['user_id']}\n"
            f"Сумма: {format_price(payment['total'])}\n"
            f"Создана: {payment['created_at']}"
        )
        await message.answer_photo(
            payment["photo_file_id"],
            caption=text,
            reply_markup=request_actions_kb(int(payment["id"])),
        )


@router.message(F.text == BTN.ADMIN_STATS)
async def admin_stats(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    stats = await db.get_stats()
    text = (
        "Статистика:\n"
        f"Всего заказов: {stats['orders_total']}\n"
        f"Оплачено: {stats['orders_paid']}\n"
        f"В ожидании проверки: {stats['orders_pending']}\n"
        f"Отклонено: {stats['orders_rejected']}\n"
        f"Заявок в ожидании: {stats['payments_pending']}"
    )
    await message.answer(text)


@router.message(F.text == BTN.ADMIN_PAYMENT_DETAILS)
async def admin_payment_details_start(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.payment_details_text)
    await message.answer(
        "Отправьте новые реквизиты одним сообщением. "
        "Это сообщение будет показываться пользователям в разделе оплаты."
    )


@router.message(F.text == BTN.ADMIN_REPORTS)
async def admin_reports(message: Message) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        return
    rows = await db.get_payments_report()
    if not rows:
        await message.answer("Нет данных для отчета.")
        return
    report_path = Path("data") / "payments_report.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "payment_id",
                "order_id",
                "user_id",
                "username",
                "first_name",
                "total",
                "payment_status",
                "order_status",
                "payment_created_at",
                "payment_processed_at",
                "order_created_at",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["payment_id"],
                    row["order_id"],
                    row["user_id"],
                    row["username"] or "",
                    row["first_name"] or "",
                    row["total"],
                    row["payment_status"],
                    row["order_status"],
                    row["payment_created_at"],
                    row["payment_processed_at"] or "",
                    row["order_created_at"],
                ]
            )
    try:
        await message.bot.send_document(
            message.chat.id,
            document=FSInputFile(str(report_path)),
            caption="Отчет по оплатам (CSV)",
        )
    except Exception:
        await message.answer("Не удалось отправить отчет.")


@router.callback_query(AdminStates.add_product_city, F.data.startswith("admin:city:"))
async def admin_add_product_city(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)
    city_row = await db.get_city(city_id)

    areas = await db.get_areas_by_city(city_id)
    await state.set_state(AdminStates.add_product_area)
    if city_row:
        await _finalize_step_message(
            callback, f"Город выбран: {city_row['name']}"
        )
    else:
        await _clear_inline_keyboard(callback)
    if not areas:
        cities = await db.get_cities()
        await callback.message.answer(
            "Для этого города нет местностей. Выберите другой город:",
            reply_markup=cities_pick_kb(cities),
        )
        await callback.answer()
        return
    await callback.message.answer("Выберите местность:", reply_markup=areas_pick_kb(areas))
    await callback.answer()


@router.callback_query(AdminStates.delete_city_pick, F.data.startswith("admin:citydel:"))
async def admin_delete_city_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    city_id = int(callback.data.split(":", 2)[2])
    await db.delete_city(city_id)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Город удалён.")
    await state.clear()
    await callback.answer()


@router.callback_query(
    AdminStates.delete_area_city, F.data.startswith("admin:delareacity:")
)
async def admin_delete_area_city_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)
    areas = await db.get_areas_by_city(city_id)
    await state.set_state(AdminStates.delete_area_pick)
    await _finalize_step_message(callback, "Город выбран.")
    if not areas:
        await callback.message.answer("В этом городе нет местностей.")
        await state.clear()
        await callback.answer()
        return
    await callback.message.answer(
        "Выберите местность для удаления:",
        reply_markup=areas_pick_kb(areas, prefix="admin:delarea:"),
    )
    await callback.answer()

@router.callback_query(
    AdminStates.add_area_city, F.data.startswith("admin:addareacity:")
)
async def admin_add_area_city_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)
    await state.set_state(AdminStates.add_area_name)
    await _finalize_step_message(callback, "Город выбран.")
    await callback.message.answer("Введите название новой местности:")
    await callback.answer()


@router.message(AdminStates.add_area_name)
async def admin_add_area_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    city_id = int(data["city_id"])
    existing = [a["name"].lower() for a in await db.get_areas_by_city(city_id)]
    if new_name.lower() in existing:
        await message.answer("Местность с таким названием уже существует.")
        return
    area_id = await db.add_area(city_id, new_name)
    await message.answer(f"Местность добавлена (ID {area_id}).")
    await state.clear()


@router.callback_query(
    AdminStates.delete_area_pick, F.data.startswith("admin:delarea:")
)
async def admin_delete_area_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    area_id = int(callback.data.split(":", 2)[2])
    count = await db.count_products_by_area(area_id)
    if count > 0:
        await callback.message.answer(
            "Нельзя удалить местность: есть товары. Сначала удалите/скройте товары."
        )
        await state.clear()
        await callback.answer()
        return
    await db.delete_area(area_id)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Местность удалена.")
    await state.clear()
    await callback.answer()


@router.callback_query(AdminStates.add_product_area, F.data.startswith("admin:area:"))
async def admin_add_product_area(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    area_id = int(callback.data.split(":", 2)[2])
    await state.update_data(area_id=area_id)
    area_row = await db.get_area(area_id)

    await state.set_state(AdminStates.add_product_variant)
    if area_row:
        await _finalize_step_message(
            callback, f"Местность выбрана: {area_row['name']}"
        )
    else:
        await _clear_inline_keyboard(callback)
    variants = await db.get_variants()
    await callback.message.answer(
        "Выберите вариант:", reply_markup=variants_pick_kb(variants)
    )
    await callback.answer()


@router.callback_query(AdminStates.add_product_variant, F.data.startswith("admin:variant:"))
async def admin_add_product_variant(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)

    await state.set_state(AdminStates.add_product_class)
    await _finalize_step_message(callback, f"Вариант выбран: {variant}")
    classes = await db.get_classes(variant)
    await callback.message.answer(
        "Выберите классификацию:", reply_markup=classes_pick_kb(variant, classes)
    )
    await callback.answer()


@router.callback_query(AdminStates.add_product_class, F.data.startswith("admin:class:"))
async def admin_add_product_class(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    _, _, variant, class_name = callback.data.split(":", 3)
    await state.update_data(class_name=class_name, variant=variant)

    await state.set_state(AdminStates.add_product_photo)
    await _finalize_step_message(callback, f"Классификация выбрана: {class_name}")
    await callback.message.answer("Отправьте фото товара:")
    await callback.answer()


@router.callback_query(
    AdminStates.delete_variant_pick, F.data.startswith("admin:variant:")
)
async def admin_delete_variant_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variant = callback.data.split(":", 2)[2]
    count = await db.count_products_by_variant(variant)
    if count > 0:
        await callback.message.answer(
            "Нельзя удалить вариант: есть товары. Сначала удалите/скройте товары."
        )
        await state.clear()
        await callback.answer()
        return
    await db.delete_variant(variant)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Вариант удалён.")
    await state.clear()
    await callback.answer()

@router.message(AdminStates.add_variant_name)
async def admin_add_variant_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    variants = [row["name"] for row in await db.get_variants()]
    if new_name in variants:
        await message.answer("Вариант с таким названием уже существует.")
        return
    try:
        await db.add_variant(new_name)
    except Exception:
        await message.answer("Не удалось добавить вариант.")
        return
    await message.answer("Вариант добавлен.")
    await state.clear()


@router.callback_query(
    AdminStates.add_class_variant, F.data.startswith("admin:variant:")
)
async def admin_add_class_variant_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)
    await state.set_state(AdminStates.add_class_name)
    await _finalize_step_message(callback, f"Вариант выбран: {variant}")
    await callback.message.answer("Введите название новой классификации:")
    await callback.answer()


@router.message(AdminStates.add_class_name)
async def admin_add_class_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    variant = data.get("variant", "")
    existing = [row["name"] for row in await db.get_classes(variant)]
    if new_name in existing:
        await message.answer("Классификация с таким названием уже существует.")
        return
    try:
        await db.add_class(variant, new_name)
    except Exception:
        await message.answer("Не удалось добавить классификацию.")
        return
    await message.answer("Классификация добавлена.")
    await state.clear()


@router.callback_query(
    AdminStates.delete_class_variant, F.data.startswith("admin:variant:")
)
async def admin_delete_class_variant_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)
    classes = await db.get_classes(variant)
    await state.set_state(AdminStates.delete_class_pick)
    await _finalize_step_message(callback, f"Вариант выбран: {variant}")
    if not classes:
        await callback.message.answer("Для этого варианта нет классификаций.")
        await state.clear()
        await callback.answer()
        return
    await callback.message.answer(
        "Выберите классификацию для удаления:",
        reply_markup=classes_pick_kb(variant, classes),
    )
    await callback.answer()


@router.callback_query(
    AdminStates.delete_class_pick, F.data.startswith("admin:class:")
)
async def admin_delete_class_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    _, _, variant, class_name = callback.data.split(":", 3)
    count = await db.count_products_by_class(variant, class_name)
    if count > 0:
        await callback.message.answer(
            "Нельзя удалить классификацию: есть товары. Сначала удалите/скройте товары."
        )
        await state.clear()
        await callback.answer()
        return
    await db.delete_class(variant, class_name)
    await _clear_inline_keyboard(callback)
    await callback.message.answer("Классификация удалена.")
    await state.clear()
    await callback.answer()


@router.message(AdminStates.add_product_photo, F.photo | F.document)
async def admin_add_product_photo(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    file_id = _extract_image_file_id(message)
    if not file_id:
        await message.answer("Нужно отправить изображение (фото или файл-картинку).")
        return
    await state.update_data(photo_file_id=file_id)
    await state.set_state(AdminStates.add_product_name)
    await message.answer("Введите название товара:")


@router.message(AdminStates.add_product_photo)
async def admin_add_product_photo_required(message: Message) -> None:
    await message.answer("Нужно отправить фото товара.")


@router.message(AdminStates.add_product_name)
async def admin_add_product_name(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(title=name)
    await state.set_state(AdminStates.add_product_desc)
    await message.answer("Введите описание товара:")


@router.message(AdminStates.add_product_desc)
async def admin_add_product_desc(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым.")
        return
    await state.update_data(description=description)
    await state.set_state(AdminStates.add_product_price)
    await message.answer("Введите цену (целое число):")


@router.message(AdminStates.add_product_price)
async def admin_add_product_price(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    raw_price = message.text.strip().replace(" ", "")
    if not raw_price.isdigit():
        await message.answer("Цена должна быть целым числом.")
        return
    price = int(raw_price)
    if price <= 0:
        await message.answer("Цена должна быть больше нуля.")
        return

    await state.update_data(price=price)
    await state.set_state(AdminStates.add_product_stock)
    await message.answer("Введите остаток: только '1' или '-' (товар штучный):")


@router.message(AdminStates.add_product_stock)
async def admin_add_product_stock(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return

    raw_stock = message.text.strip().lower()
    stock: int | None
    if raw_stock in {"-", "нет", "no"}:
        stock = 1
    elif raw_stock.isdigit():
        stock = int(raw_stock)
        if stock != 1:
            await message.answer("Для штучных товаров допускается только 1.")
            return
    else:
        await message.answer("Введите '1' или '-' для пропуска.")
        return

    data = await state.get_data()

    product_id = await db.add_product(
        city_id=int(data["city_id"]),
        area_id=int(data["area_id"]),
        variant=data["variant"],
        class_name=data["class_name"],
        title=data["title"],
        description=data["description"],
        price=int(data["price"]),
        photo_file_id=data["photo_file_id"],
        stock=stock,
    )

    await message.answer(f"Товар добавлен (#{product_id}).")
    city_row = await db.get_city(int(data["city_id"]))
    area_row = await db.get_area(int(data["area_id"]))
    city_name = city_row["name"] if city_row else "-"
    area_name = area_row["name"] if area_row else "-"

    preview_text = (
        "Предпросмотр товара:\n"
        f"Город: {city_name}\n"
        f"Местность: {area_name}\n"
        f"Вариант: {data['variant']}\n"
        f"Класс: {data['class_name']}\n"
        f"Название: {data['title']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {format_price(int(data['price']))}"
    )
    await message.answer_photo(
        photo=data["photo_file_id"],
        caption=preview_text,
    )
    await state.clear()


@router.callback_query(F.data.startswith("pay:confirm:"))
async def confirm_payment(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    payment_id = int(callback.data.split(":", 2)[2])
    payment = await db.get_payment(payment_id)
    if not payment or payment["status"] != "pending":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    await db.set_payment_status(payment_id, "confirmed")
    await db.set_order_status(int(payment["order_id"]), "paid")
    await db.increment_purchases(int(payment["user_id"]))

    user_id = int(payment["user_id"])
    await callback.bot.send_message(user_id, "Оплата подтверждена.")

    items = await db.get_order_items(int(payment["order_id"]))
    for item in items:
        caption = delivery_caption(item, int(item["quantity"]))
        await callback.bot.send_photo(
            user_id,
            photo=item["photo_file_id"],
            caption=caption,
        )

    await callback.bot.send_message(user_id, "ВАШ ДОСТУП: ...")
    await callback.bot.send_message(
        user_id,
        "Хотите оставить отзыв или написать в поддержку?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Оставить отзыв",
                        callback_data=f"review:{int(payment['order_id'])}",
                    ),
                    InlineKeyboardButton(
                        text="Написать в поддержку",
                        callback_data="support:after",
                    ),
                ]
            ]
        ),
    )

    if ADMIN_GROUP_ID:
        buyer = await db.get_user(user_id)
        username = f"@{buyer['username']}" if buyer and buyer["username"] else "-"
        first_name = buyer["first_name"] if buyer and buyer["first_name"] else "-"
        items_lines = []
        for item in items:
            items_lines.append(
                f"- {item['title']} x{item['quantity']} ({format_price(int(item['price']))})"
            )
        sold_text = (
            "Продажа подтверждена:\n"
            f"Заказ #{payment['order_id']}\n"
            f"Покупатель ID: {user_id}\n"
            f"Username: {username}\n"
            f"First name: {first_name}\n"
            f"Сумма: {format_price(int(payment['total']))}\n"
            "Товары:\n"
            + "\n".join(items_lines)
        )
        await callback.bot.send_message(ADMIN_GROUP_ID, sold_text)

    try:
        await callback.message.edit_caption(
            (callback.message.caption or "") + f"\n\nСтатус: подтверждено\nПокупатель ID: {user_id}",
            reply_markup=None,
        )
    except Exception:
        pass

    await callback.answer("Подтверждено")


@router.callback_query(F.data.startswith("pay:reject:"))
async def reject_payment(callback: CallbackQuery) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    payment_id = int(callback.data.split(":", 2)[2])
    payment = await db.get_payment(payment_id)
    if not payment or payment["status"] != "pending":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    await db.set_payment_status(payment_id, "rejected")
    await db.set_order_status(int(payment["order_id"]), "rejected")
    await db.restore_order_products(int(payment["order_id"]))

    await callback.bot.send_message(
        int(payment["user_id"]),
        "Оплата отклонена. Если это ошибка, свяжитесь с поддержкой.",
    )

    try:
        await callback.message.edit_caption(
            (callback.message.caption or "") + "\n\nСтатус: отклонено",
            reply_markup=None,
        )
    except Exception:
        pass

    await callback.answer("Отклонено")


@router.callback_query(AdminStates.rename_city_pick, F.data.startswith("admin:city:"))
async def admin_rename_city_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)
    await state.set_state(AdminStates.rename_city_name)
    await _finalize_step_message(callback, "Город выбран для переименования.")
    await callback.message.answer("Введите новое название города:")
    await callback.answer()

@router.callback_query(
    AdminStates.rename_area_city, F.data.startswith("admin:areacity:")
)
async def admin_rename_area_city_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)
    areas = await db.get_areas_by_city(city_id)
    await state.set_state(AdminStates.rename_area_pick)
    await _finalize_step_message(callback, "Город выбран.")
    if not areas:
        await callback.message.answer("В этом городе нет местностей.")
        await state.clear()
        await callback.answer()
        return
    await callback.message.answer(
        "Выберите местность:",
        reply_markup=areas_pick_kb(areas, prefix="admin:arearename:"),
    )
    await callback.answer()


@router.callback_query(
    AdminStates.rename_area_pick, F.data.startswith("admin:arearename:")
)
async def admin_rename_area_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    area_id = int(callback.data.split(":", 2)[2])
    await state.update_data(area_id=area_id)
    await state.set_state(AdminStates.rename_area_name)
    await _finalize_step_message(callback, "Местность выбрана для переименования.")
    await callback.message.answer("Введите новое название местности:")
    await callback.answer()


@router.message(AdminStates.rename_area_name)
async def admin_rename_area_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    await db.rename_area(int(data["area_id"]), new_name)
    await message.answer("Местность переименована.")
    await state.clear()


@router.callback_query(AdminStates.rename_variant_pick, F.data.startswith("admin:variant:"))
async def admin_rename_variant_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    old_name = callback.data.split(":", 2)[2]
    await state.update_data(old_variant=old_name)
    await state.set_state(AdminStates.rename_variant_name)
    await _finalize_step_message(callback, f"Вариант выбран: {old_name}")
    await callback.message.answer("Введите новое название варианта:")
    await callback.answer()


@router.message(AdminStates.rename_variant_name)
async def admin_rename_variant_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    old_name = data.get("old_variant", "")
    variants = [row["name"] for row in await db.get_variants()]
    if new_name in variants:
        await message.answer("Вариант с таким названием уже существует.")
        return
    if old_name not in variants:
        await message.answer("Вариант больше не существует.")
        await state.clear()
        return
    await db.rename_variant(old_name, new_name)
    await message.answer("Вариант переименован.")
    await state.clear()


@router.callback_query(AdminStates.rename_class_variant, F.data.startswith("admin:variant:"))
async def admin_rename_class_variant_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)
    classes = await db.get_classes(variant)
    await state.set_state(AdminStates.rename_class_pick)
    await _finalize_step_message(callback, f"Вариант выбран: {variant}")
    if not classes:
        await callback.message.answer("Для этого варианта нет классификаций.")
        await state.clear()
        await callback.answer()
        return
    await callback.message.answer(
        "Выберите классификацию:",
        reply_markup=classes_pick_kb(variant, classes),
    )
    await callback.answer()


@router.callback_query(AdminStates.rename_class_pick, F.data.startswith("admin:class:"))
async def admin_rename_class_pick(
    callback: CallbackQuery, state: FSMContext
) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    _, _, variant, class_name = callback.data.split(":", 3)
    await state.update_data(variant=variant, old_class=class_name)
    await state.set_state(AdminStates.rename_class_name)
    await _finalize_step_message(callback, f"Классификация выбрана: {class_name}")
    await callback.message.answer("Введите новое название классификации:")
    await callback.answer()


@router.message(AdminStates.rename_class_name)
async def admin_rename_class_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    variant = data.get("variant", "")
    old_class = data.get("old_class", "")
    classes = [row["name"] for row in await db.get_classes(variant)]
    if new_name in classes:
        await message.answer("Классификация с таким названием уже существует.")
        return
    if old_class not in classes:
        await message.answer("Классификация больше не существует.")
        await state.clear()
        return
    await db.rename_class(variant, old_class, new_name)
    await message.answer("Классификация переименована.")
    await state.clear()

@router.message(AdminStates.rename_city_name)
async def admin_rename_city_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    await db.rename_city(int(data["city_id"]), new_name)
    await message.answer("Город переименован.")
    await state.clear()


@router.message(AdminStates.add_city_name)
async def admin_add_city_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым.")
        return
    existing = [c["name"].lower() for c in await db.get_cities()]
    if new_name.lower() in existing:
        await message.answer("Город с таким названием уже существует.")
        return
    city_id = await db.add_city(new_name)
    await message.answer(f"Город добавлен (ID {city_id}).")
    await state.clear()


@router.message(AdminStates.rename_product_id)
async def admin_rename_product_pick(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        return
    await state.update_data(product_id=int(message.text.strip()))
    await state.set_state(AdminStates.rename_product_name)
    await message.answer("Введите новое название товара:")


@router.message(AdminStates.rename_product_name)
async def admin_rename_product_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    await db.rename_product(int(data["product_id"]), new_title)
    await message.answer("Товар переименован.")
    await state.clear()


@router.message(AdminStates.user_history_id)
async def admin_user_history_show(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        return
    user_id = int(message.text.strip())
    rows = await db.get_user_purchase_history(user_id)
    if not rows:
        await message.answer("Покупок не найдено.")
        await state.clear()
        return
    lines = []
    current_order = None
    for row in rows:
        order_id = int(row["order_id"])
        if current_order != order_id:
            lines.append(
                f"\nЗаказ #{order_id} от {row['created_at']} (сумма {format_price(int(row['total']))})"
            )
            current_order = order_id
        lines.append(f"- {row['title']} x{row['quantity']}")
    await message.answer("История покупок:" + "\n".join(lines))
    await state.clear()


@router.message(AdminStates.payment_details_text)
async def admin_payment_details_save(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    text = message.text.strip()
    if not text:
        await message.answer("Реквизиты не могут быть пустыми.")
        return
    await db.set_setting("payment_details", text)
    await message.answer("Реквизиты обновлены.")
    await state.clear()


@router.message(AdminStates.delete_product_id)
async def admin_product_delete_finish(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        return
    product_id = int(message.text.strip())
    await db.delete_product(product_id)
    await message.answer(f"Товар #{product_id} скрыт из ассортимента.")
    await state.clear()


@router.callback_query(AdminStates.variant_photo_pick, F.data.startswith("admin:variant:"))
async def admin_variant_photo_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)
    await state.set_state(AdminStates.variant_photo_upload)
    await _finalize_step_message(callback, f"Вариант выбран: {variant}")
    await callback.message.answer("Отправьте фото для выбранного варианта:")
    await callback.answer()


@router.message(AdminStates.variant_photo_upload, F.photo | F.document)
async def admin_variant_photo_upload(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    data = await state.get_data()
    file_id = _extract_image_file_id(message)
    if not file_id:
        await message.answer("Нужно отправить изображение (фото или файл-картинку).")
        return
    await db.set_variant_photo(data["variant"], file_id)
    await message.answer("Фото варианта сохранено.")
    await state.clear()


@router.message(AdminStates.product_owner_id)
async def admin_product_owner_show(message: Message, state: FSMContext) -> None:
    if not await is_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        return
    product_id = int(message.text.strip())
    row = await db.get_product_owner(product_id)
    if not row:
        await message.answer("Товар не найден.")
        await state.clear()
        return
    if row["sold_to_user_id"] is None:
        await message.answer(f"Товар #{product_id} ещё не куплен.")
        await state.clear()
        return
    username = f"@{row['username']}" if row["username"] else "-"
    first_name = row["first_name"] or "-"
    await message.answer(
        "Покупатель товара:\n"
        f"Товар: {row['title']} (ID {product_id})\n"
        f"User ID: {row['sold_to_user_id']}\n"
        f"Username: {username}\n"
        f"First name: {first_name}\n"
        f"Order ID: {row['sold_order_id']}\n"
        f"Дата покупки: {row['sold_at']}"
    )
    await state.clear()


 


