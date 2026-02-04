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
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0") or 0)

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

VARIANTS = ["A", "B"]
CLASSES = {
    "A": ["A-1", "A-2", "A-3", "A-4"],
    "B": ["B-1", "B-2", "B-3", "B-4"],
}

AREAS = ["Местность 1", "Местность 2", "Местность 3", "Местность 4"]


@dataclass(frozen=True)
class Buttons:
    CATALOG: str = "Каталог"
    CART: str = "Корзина"
    PAYMENT: str = "Оплата"
    SUPPORT: str = "Поддержка"

    CLEAR_CART: str = "Очистить"
    CHECKOUT: str = "Оформить"
    I_PAID: str = "Я оплатил"

    ADMIN_ADD_PRODUCT: str = "Добавить товар"
    ADMIN_ADD_CITY: str = "Добавить город"
    ADMIN_DELETE_CITY: str = "Удалить город"
    ADMIN_RENAME_CITY: str = "Переименовать город"
    ADMIN_RENAME_PRODUCT: str = "Переименовать товар"
    ADMIN_VARIANT_PHOTO: str = "Фото варианта"
    ADMIN_USER_HISTORY: str = "История покупок"
    ADMIN_REVIEWS: str = "Отзывы"
    ADMIN_PRODUCT_OWNER: str = "Кто купил товар"
    ADMIN_PRODUCTS_LIST: str = "Ассортимент"
    ADMIN_PRODUCT_DELETE: str = "Удалить товар"
    ADMIN_LOGS: str = "Логи"
    ADMIN_REQUESTS: str = "Заявки"
    ADMIN_STATS: str = "Статистика"

    CONFIRM: str = "✅ Подтвердить"
    REJECT: str = "❌ Отклонить"

    BACK: str = "Назад"


BTN = Buttons()
