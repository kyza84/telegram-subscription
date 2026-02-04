from __future__ import annotations

from aiogram import F, Router
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
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import ADMIN_GROUP_ID, ADMIN_IDS, BTN, CLASSES, VARIANTS
from app.db import database as db
from app.services.catalog import delivery_caption, format_price

router = Router()


class AdminStates(StatesGroup):
    add_product_city = State()
    add_product_area = State()
    add_product_variant = State()
    add_product_class = State()
    add_product_photo = State()
    add_product_name = State()
    add_product_desc = State()
    add_product_price = State()
    add_product_stock = State()
    rename_city_pick = State()
    rename_city_name = State()
    rename_product_id = State()
    rename_product_name = State()
    user_history_id = State()
    variant_photo_pick = State()
    variant_photo_upload = State()
    product_owner_id = State()


async def is_group_admin(message_or_callback) -> bool:
    chat = message_or_callback.chat if hasattr(message_or_callback, "chat") else message_or_callback.message.chat
    if ADMIN_GROUP_ID == 0 or chat.id != ADMIN_GROUP_ID:
        return False
    member = await message_or_callback.bot.get_chat_member(chat.id, message_or_callback.from_user.id)
    return member.status in {"creator", "administrator"}


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN.ADMIN_ADD_PRODUCT)],
            [KeyboardButton(text=BTN.ADMIN_RENAME_CITY), KeyboardButton(text=BTN.ADMIN_RENAME_PRODUCT)],
            [KeyboardButton(text=BTN.ADMIN_VARIANT_PHOTO), KeyboardButton(text=BTN.ADMIN_USER_HISTORY)],
            [KeyboardButton(text=BTN.ADMIN_REVIEWS)],
            [KeyboardButton(text=BTN.ADMIN_PRODUCT_OWNER)],
            [KeyboardButton(text=BTN.ADMIN_REQUESTS), KeyboardButton(text=BTN.ADMIN_STATS)],
        ],
        resize_keyboard=True,
    )


def cities_pick_kb(cities: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.button(text=city["name"], callback_data=f"admin:city:{city['id']}")
    builder.adjust(2)
    return builder.as_markup()


def areas_pick_kb(areas: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for area in areas:
        builder.button(text=area["name"], callback_data=f"admin:area:{area['id']}")
    builder.adjust(2)
    return builder.as_markup()


def variants_pick_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for variant in VARIANTS:
        builder.button(text=f"Товар {variant}", callback_data=f"admin:variant:{variant}")
    builder.adjust(2)
    return builder.as_markup()


def classes_pick_kb(variant: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for class_name in CLASSES.get(variant, []):
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
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.message(F.text == BTN.ADMIN_ADD_PRODUCT)
async def admin_add_product_start(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.add_product_city)
    await message.answer("Выберите город:", reply_markup=cities_pick_kb(cities))


@router.callback_query(AdminStates.add_product_city, F.data.startswith("admin:city:"))
async def admin_add_product_city(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)

    areas = await db.get_areas_by_city(city_id)
    await state.set_state(AdminStates.add_product_area)
    await callback.message.answer("Выберите местность:", reply_markup=areas_pick_kb(areas))
    await callback.answer()


@router.callback_query(AdminStates.add_product_area, F.data.startswith("admin:area:"))
async def admin_add_product_area(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    area_id = int(callback.data.split(":", 2)[2])
    await state.update_data(area_id=area_id)

    await state.set_state(AdminStates.add_product_variant)
    await callback.message.answer("Выберите вариант:", reply_markup=variants_pick_kb())
    await callback.answer()


@router.callback_query(AdminStates.add_product_variant, F.data.startswith("admin:variant:"))
async def admin_add_product_variant(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)

    await state.set_state(AdminStates.add_product_class)
    await callback.message.answer(
        "Выберите классификацию:", reply_markup=classes_pick_kb(variant)
    )
    await callback.answer()


@router.callback_query(AdminStates.add_product_class, F.data.startswith("admin:class:"))
async def admin_add_product_class(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    _, _, variant, class_name = callback.data.split(":", 3)
    await state.update_data(class_name=class_name, variant=variant)

    await state.set_state(AdminStates.add_product_photo)
    await callback.message.answer("Отправьте фото товара:")
    await callback.answer()


@router.message(AdminStates.add_product_photo, F.photo)
async def admin_add_product_photo(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(AdminStates.add_product_name)
    await message.answer("Введите название товара:")


@router.message(AdminStates.add_product_photo)
async def admin_add_product_photo_required(message: Message) -> None:
    await message.answer("Нужно отправить фото товара.")


@router.message(AdminStates.add_product_name)
async def admin_add_product_name(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
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
    if not await is_group_admin(message):
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
    if not await is_group_admin(message):
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
    if not await is_group_admin(message):
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
    await state.clear()


@router.message(F.text == BTN.ADMIN_REQUESTS)
async def admin_show_requests(message: Message) -> None:
    if not await is_group_admin(message):
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
    if not await is_group_admin(message):
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


@router.callback_query(F.data.startswith("pay:confirm:"))
async def confirm_payment(callback: CallbackQuery) -> None:
    if not await is_group_admin(callback):
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
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    payment_id = int(callback.data.split(":", 2)[2])
    payment = await db.get_payment(payment_id)
    if not payment or payment["status"] != "pending":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return

    await db.set_payment_status(payment_id, "rejected")
    await db.set_order_status(int(payment["order_id"]), "rejected")

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


@router.message(F.text == BTN.ADMIN_RENAME_CITY)
async def admin_rename_city_start(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    cities = await db.get_cities()
    await state.set_state(AdminStates.rename_city_pick)
    await message.answer("Выберите город:", reply_markup=cities_pick_kb(cities))


@router.callback_query(AdminStates.rename_city_pick, F.data.startswith("admin:city:"))
async def admin_rename_city_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    city_id = int(callback.data.split(":", 2)[2])
    await state.update_data(city_id=city_id)
    await state.set_state(AdminStates.rename_city_name)
    await callback.message.answer("Введите новое название города:")
    await callback.answer()


@router.message(AdminStates.rename_city_name)
async def admin_rename_city_finish(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
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


@router.message(F.text == BTN.ADMIN_RENAME_PRODUCT)
async def admin_rename_product_start(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.rename_product_id)
    await message.answer("Введите ID товара:")


@router.message(AdminStates.rename_product_id)
async def admin_rename_product_pick(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
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
    if not await is_group_admin(message):
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


@router.message(F.text == BTN.ADMIN_USER_HISTORY)
async def admin_user_history_start(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.user_history_id)
    await message.answer("Введите Telegram ID пользователя:")


@router.message(AdminStates.user_history_id)
async def admin_user_history_show(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
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


@router.message(F.text == BTN.ADMIN_REVIEWS)
async def admin_show_reviews(message: Message) -> None:
    if not await is_group_admin(message):
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
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.variant_photo_pick)
    await message.answer("Выберите вариант:", reply_markup=variants_pick_kb())


@router.callback_query(AdminStates.variant_photo_pick, F.data.startswith("admin:variant:"))
async def admin_variant_photo_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await is_group_admin(callback):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    variant = callback.data.split(":", 2)[2]
    await state.update_data(variant=variant)
    await state.set_state(AdminStates.variant_photo_upload)
    await callback.message.answer("Отправьте фото для выбранного варианта:")
    await callback.answer()


@router.message(AdminStates.variant_photo_upload, F.photo)
async def admin_variant_photo_upload(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        await state.clear()
        return
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    await db.set_variant_photo(data["variant"], photo_id)
    await message.answer("Фото варианта сохранено.")
    await state.clear()


@router.message(F.text == BTN.ADMIN_PRODUCT_OWNER)
async def admin_product_owner_start(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AdminStates.product_owner_id)
    await message.answer("Введите ID товара:")


@router.message(AdminStates.product_owner_id)
async def admin_product_owner_show(message: Message, state: FSMContext) -> None:
    if not await is_group_admin(message):
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


@router.message(F.chat.id == ADMIN_GROUP_ID)
async def support_reply_from_admin(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in ADMIN_IDS:
        return
    if message.text and message.text.startswith("/"):
        return

    if not message.reply_to_message:
        await message.answer("Нужно отвечать реплаем на сообщение обращения.")
        return

    user_id = await db.get_user_by_admin_reply(
        ADMIN_GROUP_ID, message.reply_to_message.message_id
    )
    if not user_id:
        await message.answer("Нужно отвечать реплаем на сообщение обращения.")
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

    await message.answer("✅ Отправлено пользователю")


