from __future__ import annotations

from typing import Iterable


def format_price(price: int) -> str:
    return f"{price} руб."


def product_caption(product: dict) -> str:
    try:
        stock = product["stock"]
    except Exception:
        stock = None
    stock_text = "" if stock is None else f"\nОстаток: {stock}"
    return (
        f"{product['title']}\n\n"
        f"{product['description']}\n\n"
        f"Цена: {format_price(int(product['price']))}{stock_text}"
    )


def delivery_caption(product: dict, quantity: int) -> str:
    qty_text = f"\nКоличество: {quantity}" if quantity > 1 else ""
    return (
        f"{product['title']}\n\n"
        f"{product['description']}\n\n"
        f"Цена: {format_price(int(product['price']))}{qty_text}"
    )


def build_cart_text(items: Iterable[dict]) -> tuple[str, int]:
    items = list(items)
    if not items:
        return "Корзина пуста.", 0

    lines: list[str] = []
    total = 0
    for item in items:
        line_total = int(item["price"]) * int(item["quantity"])
        total += line_total
        lines.append(
            f"{item['title']} x{item['quantity']} — {format_price(line_total)}"
        )

    text = "Ваши товары:\n" + "\n".join(lines) + f"\n\nИтого: {format_price(total)}"
    return text, total
