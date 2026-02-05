from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def load_env(path: Path | str = BASE_DIR / ".env") -> None:
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def _parse_admin_ids(value: str) -> list[int]:
    ids: list[int] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ids.append(int(raw))
        except ValueError:
            continue
    return ids


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
try:
    ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0") or 0)
except ValueError:
    ADMIN_GROUP_ID = 0

DB_PATH = BASE_DIR / "data" / "shop.db"
LOG_PATH = BASE_DIR / "logs" / "bot.log"

PAYMENT_DETAILS = (
    "Реквизиты для оплаты:\n"
    "Банк: Пример Банк\n"
    "Номер карты: 0000 0000 0000 0000\n"
    "Получатель: ИП Пример\n"
    "Назначение: Оплата заказа\n"
)

SUPPORT_TEXT = "Поддержка: напишите @your_support или support@example.com"

DEFAULT_CITIES = ["Киев", "Львов"]

DEFAULT_VARIANTS = ["Электроника", "Аксессуары"]
DEFAULT_CLASSES = {
    "Электроника": ["Смартфоны", "Наушники", "Гаджеты"],
    "Аксессуары": ["Кабели", "Зарядки", "Чехлы"],
}

AREAS = ["Центр", "Север", "Юг", "Запад"]

TEST_PRODUCTS = [
    {
        "city": "Киев",
        "area": "Центр",
        "variant": "Электроника",
        "class": "Смартфоны",
        "title": "Smart X1 128GB",
        "description": "Экран 6.5\", NFC, быстрый заряд.",
        "price": 9999,
        "photo_url": "https://placehold.co/600x400/png?text=Smart+X1",
        "stock": 1,
    },
    {
        "city": "Киев",
        "area": "Север",
        "variant": "Электроника",
        "class": "Смартфоны",
        "title": "Smart Lite 64GB",
        "description": "Легкий корпус, батарея на 2 дня.",
        "price": 6999,
        "photo_url": "https://placehold.co/600x400/png?text=Smart+Lite",
        "stock": 1,
    },
    {
        "city": "Киев",
        "area": "Юг",
        "variant": "Электроника",
        "class": "Наушники",
        "title": "AirBeat Pro",
        "description": "Шумоподавление, до 24 часов работы.",
        "price": 2599,
        "photo_url": "https://placehold.co/600x400/png?text=AirBeat+Pro",
        "stock": 1,
    },
    {
        "city": "Львов",
        "area": "Центр",
        "variant": "Электроника",
        "class": "Гаджеты",
        "title": "Watch Fit 2",
        "description": "Умные уведомления и спорт-режимы.",
        "price": 3499,
        "photo_url": "https://placehold.co/600x400/png?text=Watch+Fit+2",
        "stock": 1,
    },
    {
        "city": "Львов",
        "area": "Север",
        "variant": "Аксессуары",
        "class": "Кабели",
        "title": "USB-C кабель 1.5 м",
        "description": "Нейлоновая оплетка, усиленные коннекторы.",
        "price": 299,
        "photo_url": "https://placehold.co/600x400/png?text=USB-C+Cable",
        "stock": 1,
    },
    {
        "city": "Львов",
        "area": "Юг",
        "variant": "Аксессуары",
        "class": "Зарядки",
        "title": "Зарядка 30W",
        "description": "Быстрая зарядка для смартфонов и планшетов.",
        "price": 699,
        "photo_url": "https://placehold.co/600x400/png?text=Charger+30W",
        "stock": 1,
    },
    {
        "city": "Киев",
        "area": "Запад",
        "variant": "Аксессуары",
        "class": "Чехлы",
        "title": "Чехол Slim для Smart X1",
        "description": "Матовый, защита камеры и краев.",
        "price": 399,
        "photo_url": "https://placehold.co/600x400/png?text=Slim+Case",
        "stock": 1,
    },
    {
        "city": "Львов",
        "area": "Запад",
        "variant": "Электроника",
        "class": "Наушники",
        "title": "SoundDots Mini",
        "description": "Компактные, зарядка от кейса.",
        "price": 1299,
        "photo_url": "https://placehold.co/600x400/png?text=SoundDots",
        "stock": 1,
    },
]


@dataclass(frozen=True)
class Buttons:
    CATALOG: str = "Каталог товаров"
    CART: str = "Корзина"
    PAYMENT: str = "Оплата и реквизиты"
    SUPPORT: str = "Поддержка"

    CLEAR_CART: str = "Очистить корзину"
    CHECKOUT: str = "Оформить заказ"
    I_PAID: str = "Я оплатил"

    ADMIN_ADD_PRODUCT: str = "Добавить товар"
    ADMIN_ADD_CITY: str = "Добавить город"
    ADMIN_ADD_AREA: str = "Добавить местность"
    ADMIN_DELETE_CITY: str = "Удалить город"
    ADMIN_DELETE_AREA: str = "Удалить местность"
    ADMIN_RENAME_CITY: str = "Переименовать город"
    ADMIN_RENAME_AREA: str = "Переименовать местность"
    ADMIN_RENAME_PRODUCT: str = "Переименовать товар"
    ADMIN_RENAME_VARIANT: str = "Переименовать вариант"
    ADMIN_RENAME_CLASS: str = "Переименовать классификацию"
    ADMIN_ADD_VARIANT: str = "Добавить вариант"
    ADMIN_ADD_CLASS: str = "Добавить классификацию"
    ADMIN_DELETE_VARIANT: str = "Удалить вариант"
    ADMIN_DELETE_CLASS: str = "Удалить классификацию"
    ADMIN_VARIANT_PHOTO: str = "Фото варианта"
    ADMIN_USER_HISTORY: str = "История покупок"
    ADMIN_REVIEWS: str = "Отзывы"
    ADMIN_PRODUCT_OWNER: str = "Кто купил товар"
    ADMIN_PRODUCTS_LIST: str = "Текущий ассортимент"
    ADMIN_PRODUCT_DELETE: str = "Удалить товар"
    ADMIN_LOGS: str = "Логи бота"
    ADMIN_PAYMENT_DETAILS: str = "Реквизиты оплаты"
    ADMIN_REPORTS: str = "Отчет по оплатам"
    ADMIN_REQUESTS: str = "Заявки на оплату"
    ADMIN_STATS: str = "Статистика продаж"
    ADMIN_PANEL: str = "Админ-панель"

    CONFIRM: str = "✅ Подтвердить"
    REJECT: str = "❌ Отклонить"

    BACK: str = "Назад"


BTN = Buttons()
