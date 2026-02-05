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

from app.config import ADMIN_GROUP_ID, BTN, PAYMENT_DETAILS, SUPPORT_TEXT
from app.db import database as db
from app.services.catalog import build_cart_text, format_price

router = Router()


class UserStates(StatesGroup):
    waiting_payment_photo = State()
    waiting_review = State()
    waiting_support_message = State()


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN.CATALOG), KeyboardButton(text=BTN.CART)],
            [KeyboardButton(text=BTN.PAYMENT), KeyboardButton(text=BTN.SUPPORT)],
        ],
        resize_keyboard=True,
    )


def cities_kb(cities: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for city in cities:
        builder.button(text=city["name"], callback_data=f"city:{city['id']}")
    builder.adjust(2)
    return builder.as_markup()


def areas_kb(areas: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for area in areas:
        builder.button(text=area["name"], callback_data=f"area:{area['id']}")
    builder.button(text=BTN.BACK, callback_data="back:cities")
    builder.adjust(2)
    return builder.as_markup()


def variants_kb(variants: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for variant in variants:
        name = variant["name"]
        builder.button(text=f"Товар {name}", callback_data=f"variant:{name}")
    builder.button(text=BTN.BACK, callback_data="back:areas")
    builder.adjust(2)
    return builder.as_markup()

def classes_kb(variant: str, classes: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for class_row in classes:
        class_name = class_row["name"]
        builder.button(
            text=class_name, callback_data=f"class:{variant}:{class_name}"
        )
    builder.button(text=BTN.BACK, callback_data="back:variants")
    builder.adjust(2)
    return builder.as_markup()


def products_select_kb(products: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        title = product["title"]
        price = format_price(int(product["price"]))
        stock = int(product["stock"] or 0)
        if stock > 0:
            builder.button(
                text=f"{title} — {price}", callback_data=f"add:{product['id']}"
            )
        else:
            builder.button(
                text=f"{title} — нет в наличии",
                callback_data=f"out:{product['id']}",
            )
    builder.adjust(1)
    return builder.as_markup()


def cart_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN.CLEAR_CART, callback_data="cart:clear"),
                InlineKeyboardButton(text=BTN.CHECKOUT, callback_data="cart:checkout"),
            ]
        ]
    )


def payment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN.I_PAID, callback_data="pay:submit")]
        ]
    )


def support_back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN.BACK)]],
        resize_keyboard=True,
    )


def support_locked_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN.CATALOG), KeyboardButton(text=BTN.PAYMENT)]],
        resize_keyboard=True,
    )


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await db.upsert_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    username_value = message.from_user.username or "unknown"
    username = f"@{username_value}"
    await message.answer(
        f"Привет, {message.from_user.first_name} ({username}) [id:{message.from_user.id}], добро пожаловать!",
        reply_markup=main_menu_kb(),
    )

    cities = await db.get_cities()
    await message.answer("Выберите город:", reply_markup=cities_kb(cities))


@router.message(F.text == BTN.CATALOG)
async def show_catalog(message: Message) -> None:
    cities = await db.get_cities()
    await message.answer("Выберите город:", reply_markup=cities_kb(cities))


@router.callback_query(F.data.startswith("city:"))
async def pick_city(callback: CallbackQuery) -> None:
    city_id = int(callback.data.split(":", 1)[1])
    await db.set_user_city(callback.from_user.id, city_id)
    areas = await db.get_areas_by_city(city_id)
    await callback.message.answer("Выберите местность:", reply_markup=areas_kb(areas))
    await callback.answer()


@router.callback_query(F.data.startswith("area:"))
async def pick_area(callback: CallbackQuery) -> None:
    area_id = int(callback.data.split(":", 1)[1])
    await db.set_user_area(callback.from_user.id, area_id)
    photos = await db.get_variant_photos()
    variants = await db.get_variants()
    for variant in variants:
        name = variant["name"]
        photo_id = photos.get(name)
        if photo_id:
            await callback.message.answer_photo(
                photo_id,
                caption=f"Раздел Товар {name}",
            )
    await callback.message.answer(
        "Выберите вариант:", reply_markup=variants_kb(variants)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("variant:"))
async def pick_variant(callback: CallbackQuery) -> None:
    variant = callback.data.split(":", 1)[1]
    classes = await db.get_classes(variant)
    await callback.message.answer(
        "Выберите классификацию:", reply_markup=classes_kb(variant, classes)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("class:"))
async def pick_class(callback: CallbackQuery) -> None:
    _, variant, class_name = callback.data.split(":", 2)
    user = await db.get_user(callback.from_user.id)
    if not user or not user["last_city_id"] or not user["last_area_id"]:
        cities = await db.get_cities()
        await callback.message.answer("Сначала выберите город.")
        await callback.message.answer("Выберите город:", reply_markup=cities_kb(cities))
        await callback.answer()
        return

    products = await db.get_products_filtered(
        city_id=int(user["last_city_id"]),
        area_id=int(user["last_area_id"]),
        variant=variant,
        class_name=class_name,
    )

    if not products:
        await callback.message.answer("Товары не найдены для выбранной категории.")
        await callback.answer()
        return

    await callback.message.answer(
        f"Товары для {variant} / {class_name}:",
        reply_markup=products_select_kb(products),
    )
    await callback.answer()


@router.callback_query(F.data == "back:cities")
async def back_to_cities(callback: CallbackQuery) -> None:
    cities = await db.get_cities()
    await callback.message.answer("Выберите город:", reply_markup=cities_kb(cities))
    await callback.answer()


@router.callback_query(F.data == "back:areas")
async def back_to_areas(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user or not user["last_city_id"]:
        cities = await db.get_cities()
        await callback.message.answer("Выберите город:", reply_markup=cities_kb(cities))
        await callback.answer()
        return
    areas = await db.get_areas_by_city(int(user["last_city_id"]))
    await callback.message.answer("Выберите местность:", reply_markup=areas_kb(areas))
    await callback.answer()


@router.callback_query(F.data == "back:variants")
async def back_to_variants(callback: CallbackQuery) -> None:
    photos = await db.get_variant_photos()
    variants = await db.get_variants()
    for variant in variants:
        name = variant["name"]
        photo_id = photos.get(name)
        if photo_id:
            await callback.message.answer_photo(
                photo_id,
                caption=f"Раздел Товар {name}",
            )
    await callback.message.answer(
        "Выберите вариант:", reply_markup=variants_kb(variants)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:"))
async def add_product_to_cart(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    ok = await db.add_to_cart(callback.from_user.id, product_id)
    if not ok:
        await callback.answer("Товар закончился", show_alert=True)
        return
    await callback.answer("Добавлено в корзину")


@router.callback_query(F.data.startswith("out:"))
async def product_out_of_stock(callback: CallbackQuery) -> None:
    await callback.answer("Товара нет в наличии", show_alert=True)


@router.message(F.text == BTN.CART)
async def show_cart(message: Message) -> None:
    items = await db.get_cart_items(message.from_user.id)
    text, total = build_cart_text(items)
    if not items:
        await message.answer(text)
        return
    await message.answer(text, reply_markup=cart_actions_kb())


@router.callback_query(F.data == "cart:clear")
async def clear_cart(callback: CallbackQuery) -> None:
    await db.clear_cart(callback.from_user.id)
    await callback.message.answer("Корзина очищена.")
    await callback.answer()


@router.callback_query(F.data == "cart:checkout")
async def checkout_from_cart(callback: CallbackQuery) -> None:
    items = await db.get_cart_items(callback.from_user.id)
    if not items:
        await callback.message.answer("Корзина пуста.")
        await callback.answer()
        return
    payment_details = await db.get_setting("payment_details") or PAYMENT_DETAILS
    await callback.message.answer(payment_details, reply_markup=payment_kb())
    await callback.answer()


@router.message(F.text == BTN.PAYMENT)
async def show_payment(message: Message) -> None:
    payment_details = await db.get_setting("payment_details") or PAYMENT_DETAILS
    await message.answer(payment_details, reply_markup=payment_kb())


@router.callback_query(F.data == "pay:submit")
async def request_payment_photo(callback: CallbackQuery, state: FSMContext) -> None:
    items = await db.get_cart_items(callback.from_user.id)
    if not items:
        await callback.message.answer("Корзина пуста. Сначала добавьте товары.")
        await callback.answer()
        return
    await state.set_state(UserStates.waiting_payment_photo)
    await callback.message.answer("Отправьте фото или скрин оплаты.")
    await callback.answer()


@router.message(UserStates.waiting_payment_photo, F.photo)
async def receive_payment_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    result = await db.create_order_from_cart(
        user_id=message.from_user.id,
        payment_photo_id=photo_id,
    )
    if not result:
        await message.answer("Корзина пуста.")
        await state.clear()
        return
    if isinstance(result, dict) and result.get("error") == "out_of_stock":
        await message.answer("Часть товаров закончилась. Обновите корзину.")
        await state.clear()
        return

    payment_id = result["payment_id"]
    total = result["total"]

    await message.answer(
        "Заявка создана и отправлена администратору. Ожидайте подтверждения."
    )

    admin_text = (
        f"Новая заявка #{payment_id}\n"
        f"Пользователь: {message.from_user.id}\n"
        f"Сумма: {format_price(total)}"
    )
    admin_kb = InlineKeyboardMarkup(
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

    if ADMIN_GROUP_ID:
        try:
            await message.bot.send_photo(
                ADMIN_GROUP_ID,
                photo=photo_id,
                caption=admin_text,
                reply_markup=admin_kb,
            )
        except Exception:
            pass

    await state.clear()


@router.message(UserStates.waiting_payment_photo)
async def payment_photo_required(message: Message) -> None:
    await message.answer("Нужно отправить фото или скрин оплаты.")


@router.message(F.text == BTN.SUPPORT)
async def support(message: Message, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    purchases = int(user["purchases_count"]) if user else 0
    blocked = int(user["support_blocked"]) if user else 0
    if blocked:
        await message.answer(
            "Поддержка для вашего аккаунта закрыта.",
            reply_markup=main_menu_kb(),
        )
        return
    if purchases <= 0:
        await message.answer(
            "Поддержка доступна после первой покупки/оплаты.",
            reply_markup=support_locked_kb(),
        )
        return
    await state.set_state(UserStates.waiting_support_message)
    await message.answer(
        "Напишите сообщение поддержке (можно приложить фото/документ).",
        reply_markup=support_back_kb(),
    )


@router.callback_query(F.data == "support:after")
async def support_after_payment(callback: CallbackQuery, state: FSMContext) -> None:
    user = await db.get_user(callback.from_user.id)
    purchases = int(user["purchases_count"]) if user else 0
    blocked = int(user["support_blocked"]) if user else 0
    if blocked:
        await callback.message.answer(
            "Поддержка для вашего аккаунта закрыта.",
            reply_markup=main_menu_kb(),
        )
        await callback.answer()
        return
    if purchases <= 0:
        await callback.message.answer(
            "Поддержка доступна после первой покупки/оплаты.",
            reply_markup=support_locked_kb(),
        )
        await callback.answer()
        return
    await state.set_state(UserStates.waiting_support_message)
    await callback.message.answer(
        "Напишите сообщение поддержке (можно приложить фото/документ).",
        reply_markup=support_back_kb(),
    )
    await callback.answer()


@router.message(UserStates.waiting_support_message, F.text == BTN.BACK)
async def support_back(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


@router.message(
    UserStates.waiting_support_message, F.text | F.photo | F.document
)
async def support_message(message: Message, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    purchases = int(user["purchases_count"]) if user else 0
    blocked = int(user["support_blocked"]) if user else 0
    if blocked:
        await state.clear()
        await message.answer(
            "Поддержка для вашего аккаунта закрыта.",
            reply_markup=main_menu_kb(),
        )
        return
    if purchases <= 0:
        await state.clear()
        await message.answer(
            "Поддержка доступна после первой покупки/оплаты.",
            reply_markup=support_locked_kb(),
        )
        return

    if not ADMIN_GROUP_ID:
        await state.clear()
        await message.answer(
            "Поддержка временно недоступна. Попробуйте позже.",
            reply_markup=main_menu_kb(),
        )
        return

    username = user["username"] if user else None
    first_name = user["first_name"] if user else None
    last_city_id = user["last_city_id"] if user else None
    last_area_id = user["last_area_id"] if user else None

    city_name = "-"
    area_name = "-"
    if last_city_id:
        city = await db.get_city(int(last_city_id))
        if city:
            city_name = city["name"]
    if last_area_id:
        area = await db.get_area(int(last_area_id))
        if area:
            area_name = area["name"]

    text = message.text or message.caption or ""
    info_lines = [
        "Обращение в поддержку",
        f"User ID: {message.from_user.id}",
        f"Username: @{username}" if username else "Username: -",
        f"First name: {first_name}" if first_name else "First name: -",
        f"Покупок: {purchases}",
        f"Город: {city_name}",
        f"Местность: {area_name}",
        f"Сообщение: {text}" if text else "Сообщение: (без текста)",
        "Ответьте реплаем на это сообщение — ответ уйдет пользователю в личку.",
    ]
    info = "\n".join(info_lines)

    sent_ids: list[int] = []

    try:
        if message.photo:
            media_msg = await message.bot.send_photo(
                ADMIN_GROUP_ID,
                photo=message.photo[-1].file_id,
                caption="Фото от пользователя",
            )
            sent_ids.append(media_msg.message_id)
        if message.document:
            media_msg = await message.bot.send_document(
                ADMIN_GROUP_ID,
                document=message.document.file_id,
                caption="Документ от пользователя",
            )
            sent_ids.append(media_msg.message_id)

        info_msg = await message.bot.send_message(
            ADMIN_GROUP_ID,
            info,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Закрыть чат",
                            callback_data="support:close",
                        ),
                        InlineKeyboardButton(
                            text="Закрыть навсегда",
                            callback_data=f"support:block:{message.from_user.id}",
                        ),
                    ]
                ]
            ),
        )
        sent_ids.append(info_msg.message_id)
    except Exception:
        await message.answer(
            "Не удалось отправить сообщение в поддержку. "
            "Проверьте, что бот добавлен в админ-группу и имеет права администратора.",
            reply_markup=main_menu_kb(),
        )
        return

    for mid in sent_ids:
        await db.save_support_thread(
            user_tg_id=message.from_user.id,
            admin_group_id=ADMIN_GROUP_ID,
            admin_message_id=mid,
        )

    await message.answer("Принято. Мы ответим здесь.", reply_markup=main_menu_kb())


@router.message(UserStates.waiting_support_message)
async def support_message_invalid(message: Message) -> None:
    await message.answer(
        "Отправьте текст, фото или документ для поддержки.",
        reply_markup=support_back_kb(),
    )


@router.callback_query(F.data.startswith("review:"))
async def start_review(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = int(callback.data.split(":", 1)[1])
    await state.update_data(order_id=order_id)
    await state.set_state(UserStates.waiting_review)
    await callback.message.answer("Напишите ваш отзыв одним сообщением:")
    await callback.answer()


@router.message(UserStates.waiting_review)
async def save_review(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = int(data.get("order_id", 0))
    text = message.text.strip()
    if not text:
        await message.answer("Отзыв не может быть пустым.")
        return
    await db.add_review(message.from_user.id, order_id, text)
    await message.answer("Спасибо! Отзыв сохранён.")
    await state.clear()
