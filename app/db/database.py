from __future__ import annotations

from typing import Any

import aiosqlite

from app.config import AREAS, DB_PATH


async def _table_exists(db: aiosqlite.Connection, table: str) -> bool:
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    )
    row = await cur.fetchone()
    await cur.close()
    return row is not None


async def _table_has_column(
    db: aiosqlite.Connection, table: str, column: str
) -> bool:
    cur = await db.execute(f"PRAGMA table_info({table})")
    rows = await cur.fetchall()
    await cur.close()
    return any(str(row[1]) == column for row in rows)


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")

        if await _table_exists(db, "products") and not await _table_has_column(
            db, "products", "variant"
        ):
            await db.execute("ALTER TABLE products RENAME TO products_old")

        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                purchases_count INTEGER NOT NULL DEFAULT 0,
                last_city_id INTEGER,
                last_area_id INTEGER,
                support_blocked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS areas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE (city_id, name),
                FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                area_id INTEGER NOT NULL,
                variant TEXT NOT NULL,
                class TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price INTEGER NOT NULL,
                photo_file_id TEXT NOT NULL,
                stock INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE,
                FOREIGN KEY (area_id) REFERENCES areas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                UNIQUE (user_id, product_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL,
                photo_file_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS variant_photos (
                variant TEXT PRIMARY KEY,
                photo_file_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS support_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                admin_group_id INTEGER NOT NULL,
                admin_message_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_group_id, admin_message_id)
            );
            """
        )

        if await _table_exists(db, "products"):
            if not await _table_has_column(db, "products", "sold_to_user_id"):
                await db.execute(
                    "ALTER TABLE products ADD COLUMN sold_to_user_id INTEGER"
                )
            if not await _table_has_column(db, "products", "sold_order_id"):
                await db.execute(
                    "ALTER TABLE products ADD COLUMN sold_order_id INTEGER"
                )
            if not await _table_has_column(db, "products", "sold_at"):
                await db.execute("ALTER TABLE products ADD COLUMN sold_at TEXT")
        if await _table_exists(db, "users"):
            if not await _table_has_column(db, "users", "support_blocked"):
                await db.execute(
                    "ALTER TABLE users ADD COLUMN support_blocked INTEGER NOT NULL DEFAULT 0"
                )

        await _seed_cities_and_areas(db)
        await db.commit()


async def _seed_cities_and_areas(db: aiosqlite.Connection) -> None:
    cur = await db.execute("SELECT COUNT(*) FROM cities")
    count_row = await cur.fetchone()
    await cur.close()

    if count_row and int(count_row[0]) == 0:
        await db.executemany(
            "INSERT INTO cities (name) VALUES (?)",
            [("City 1",)],
        )

    cur = await db.execute("SELECT id FROM cities ORDER BY id")
    cities = await cur.fetchall()
    await cur.close()

    for city in cities:
        city_id = int(city[0])
        for area_name in AREAS:
            await db.execute(
                "INSERT OR IGNORE INTO areas (city_id, name) VALUES (?, ?)",
                (city_id, area_name),
            )

    # Optional cleanup of default City 2 if it exists and has no products
    cur = await db.execute("SELECT id FROM cities WHERE name = ?", ("City 2",))
    city2 = await cur.fetchone()
    await cur.close()
    if city2:
        city2_id = int(city2[0])
        cur = await db.execute(
            "SELECT COUNT(*) FROM products WHERE city_id = ?",
            (city2_id,),
        )
        cnt_row = await cur.fetchone()
        await cur.close()
        if cnt_row and int(cnt_row[0]) == 0:
            await db.execute("DELETE FROM cities WHERE id = ?", (city2_id,))


async def _fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        await cur.close()
        return rows


async def _fetch_one(query: str, params: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        row = await cur.fetchone()
        await cur.close()
        return row


async def _execute(query: str, params: tuple[Any, ...] = ()) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


async def upsert_user(tg_id: int, username: str | None, first_name: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (tg_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (tg_id, username, first_name),
        )
        await db.commit()


async def get_user(tg_id: int) -> aiosqlite.Row | None:
    return await _fetch_one(
        "SELECT tg_id, username, first_name, purchases_count, last_city_id, last_area_id, support_blocked FROM users WHERE tg_id = ?",
        (tg_id,),
    )


async def set_support_blocked(tg_id: int, blocked: int = 1) -> None:
    await _execute(
        "UPDATE users SET support_blocked = ? WHERE tg_id = ?",
        (blocked, tg_id),
    )


async def set_user_city(tg_id: int, city_id: int) -> None:
    await _execute(
        "UPDATE users SET last_city_id = ?, last_area_id = NULL WHERE tg_id = ?",
        (city_id, tg_id),
    )


async def set_user_area(tg_id: int, area_id: int) -> None:
    await _execute("UPDATE users SET last_area_id = ? WHERE tg_id = ?", (area_id, tg_id))


async def increment_purchases(tg_id: int) -> None:
    await _execute(
        "UPDATE users SET purchases_count = purchases_count + 1 WHERE tg_id = ?",
        (tg_id,),
    )


async def get_cities() -> list[aiosqlite.Row]:
    return await _fetch_all("SELECT id, name FROM cities ORDER BY name")


async def get_areas_by_city(city_id: int) -> list[aiosqlite.Row]:
    return await _fetch_all(
        "SELECT id, name FROM areas WHERE city_id = ? ORDER BY name",
        (city_id,),
    )


async def get_city(city_id: int) -> aiosqlite.Row | None:
    return await _fetch_one(
        "SELECT id, name FROM cities WHERE id = ?",
        (city_id,),
    )


async def get_area(area_id: int) -> aiosqlite.Row | None:
    return await _fetch_one(
        "SELECT id, city_id, name FROM areas WHERE id = ?",
        (area_id,),
    )


async def set_variant_photo(variant: str, photo_file_id: str) -> None:
    await _execute(
        """
        INSERT INTO variant_photos (variant, photo_file_id)
        VALUES (?, ?)
        ON CONFLICT(variant) DO UPDATE SET photo_file_id = excluded.photo_file_id
        """,
        (variant, photo_file_id),
    )


async def get_variant_photos() -> dict[str, str]:
    rows = await _fetch_all("SELECT variant, photo_file_id FROM variant_photos")
    return {str(row["variant"]): str(row["photo_file_id"]) for row in rows}


async def add_product(
    *,
    city_id: int,
    area_id: int,
    variant: str,
    class_name: str,
    title: str,
    description: str,
    price: int,
    photo_file_id: str,
    stock: int | None,
) -> int:
    stock_value: int
    if stock is None:
        stock_value = 1
    else:
        stock_value = 1 if stock >= 1 else 0
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO products (
                city_id, area_id, variant, class, title, description, price, photo_file_id, stock,
                sold_to_user_id, sold_order_id, sold_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
            """,
            (
                city_id,
                area_id,
                variant,
                class_name,
                title,
                description,
                price,
                photo_file_id,
                stock_value,
            ),
        )
        await db.commit()
        return int(cur.lastrowid)


async def get_products_filtered(
    *,
    city_id: int,
    area_id: int,
    variant: str,
    class_name: str,
) -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT id, title, description, price, photo_file_id, stock
        FROM products
        WHERE city_id = ? AND area_id = ? AND variant = ? AND class = ? AND is_active = 1
          AND COALESCE(stock, 0) >= 1
        ORDER BY id DESC
        """,
        (city_id, area_id, variant, class_name),
    )


async def get_product(product_id: int) -> aiosqlite.Row | None:
    return await _fetch_one(
        """
        SELECT id, title, description, price, photo_file_id, stock, sold_to_user_id, sold_order_id, sold_at
        FROM products
        WHERE id = ?
        """,
        (product_id,),
    )


async def get_product_owner(product_id: int) -> aiosqlite.Row | None:
    return await _fetch_one(
        """
        SELECT p.id, p.title, p.sold_to_user_id, p.sold_order_id, p.sold_at,
               u.username, u.first_name
        FROM products p
        LEFT JOIN users u ON u.tg_id = p.sold_to_user_id
        WHERE p.id = ?
        """,
        (product_id,),
    )


async def list_products(limit: int = 50) -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT id, title, price, stock, is_active, sold_to_user_id
        FROM products
        WHERE is_active = 1 AND COALESCE(stock, 0) >= 1
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )


async def delete_product(product_id: int) -> None:
    await _execute("DELETE FROM products WHERE id = ?", (product_id,))


async def add_city(name: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT INTO cities (name) VALUES (?)", (name,))
        city_id = int(cur.lastrowid)
        for area_name in AREAS:
            await db.execute(
                "INSERT OR IGNORE INTO areas (city_id, name) VALUES (?, ?)",
                (city_id, area_name),
            )
        await db.commit()
        return city_id


async def delete_city(city_id: int) -> None:
    await _execute("DELETE FROM cities WHERE id = ?", (city_id,))


async def add_to_cart(user_id: int, product_id: int) -> bool:
    product = await _fetch_one(
        "SELECT stock FROM products WHERE id = ? AND is_active = 1",
        (product_id,),
    )
    if not product:
        return False
    stock = int(product["stock"] or 0)
    if stock <= 0:
        return False

    existing = await _fetch_one(
        "SELECT id FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    if existing:
        return True

    await _execute(
        "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, 1)",
        (user_id, product_id),
    )
    return True


async def get_cart_items(user_id: int) -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT p.id as product_id, p.title, p.price, ci.quantity
        FROM cart_items ci
        JOIN products p ON p.id = ci.product_id
        WHERE ci.user_id = ?
        ORDER BY p.title
        """,
        (user_id,),
    )


async def clear_cart(user_id: int) -> None:
    await _execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))


async def create_order_from_cart(
    *,
    user_id: int,
    payment_photo_id: str,
) -> dict[str, int | str] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("BEGIN")

        # Cleanup any stale cart rows that reference missing products
        await db.execute(
            """
            DELETE FROM cart_items
            WHERE user_id = ?
              AND product_id NOT IN (SELECT id FROM products)
            """,
            (user_id,),
        )

        cur = await db.execute(
            """
            SELECT p.id as product_id, p.price, ci.quantity, COALESCE(p.stock, 0) as stock
            FROM cart_items ci
            JOIN products p ON p.id = ci.product_id
            WHERE ci.user_id = ?
            """,
            (user_id,),
        )
        items = await cur.fetchall()
        await cur.close()

        if not items:
            await db.execute("ROLLBACK")
            return None

        for row in items:
            if int(row["quantity"]) > 1:
                await db.execute("ROLLBACK")
                return {"error": "out_of_stock"}
            if int(row["stock"]) < 1:
                await db.execute("ROLLBACK")
                return {"error": "out_of_stock"}

        total = sum(int(row["price"]) * int(row["quantity"]) for row in items)

        cur = await db.execute(
            "INSERT INTO orders (user_id, total, status) VALUES (?, ?, ?)",
            (user_id, total, "pending_review"),
        )
        order_id = int(cur.lastrowid)

        for row in items:
            await db.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_id,
                    int(row["product_id"]),
                    int(row["quantity"]),
                    int(row["price"]),
                ),
            )
            cur_upd = await db.execute(
                """
                UPDATE products
                SET stock = 0,
                    sold_to_user_id = ?,
                    sold_order_id = ?,
                    sold_at = CURRENT_TIMESTAMP
                WHERE id = ? AND COALESCE(stock, 0) >= 1
                """,
                (user_id, order_id, int(row["product_id"])),
            )
            if cur_upd.rowcount == 0:
                await db.execute("ROLLBACK")
                return {"error": "out_of_stock"}

        cur = await db.execute(
            """
            INSERT INTO payments (order_id, user_id, total, status, photo_file_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, user_id, total, "pending", payment_photo_id),
        )
        payment_id = int(cur.lastrowid)

        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()

        return {"order_id": order_id, "payment_id": payment_id, "total": total}


async def list_pending_payments() -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT id, order_id, user_id, total, status, photo_file_id, created_at
        FROM payments
        WHERE status = 'pending'
        ORDER BY created_at ASC
        """
    )


async def get_payment(payment_id: int) -> aiosqlite.Row | None:
    return await _fetch_one(
        """
        SELECT id, order_id, user_id, total, status, photo_file_id, created_at, processed_at
        FROM payments
        WHERE id = ?
        """,
        (payment_id,),
    )


async def set_payment_status(payment_id: int, status: str) -> None:
    await _execute(
        "UPDATE payments SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, payment_id),
    )


async def set_order_status(order_id: int, status: str) -> None:
    await _execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


async def get_stats() -> dict[str, int]:
    orders_total = await _fetch_one("SELECT COUNT(*) as c FROM orders")
    orders_paid = await _fetch_one(
        "SELECT COUNT(*) as c FROM orders WHERE status = 'paid'"
    )
    orders_pending = await _fetch_one(
        "SELECT COUNT(*) as c FROM orders WHERE status = 'pending_review'"
    )
    orders_rejected = await _fetch_one(
        "SELECT COUNT(*) as c FROM orders WHERE status = 'rejected'"
    )
    payments_pending = await _fetch_one(
        "SELECT COUNT(*) as c FROM payments WHERE status = 'pending'"
    )

    return {
        "orders_total": int(orders_total["c"]),
        "orders_paid": int(orders_paid["c"]),
        "orders_pending": int(orders_pending["c"]),
        "orders_rejected": int(orders_rejected["c"]),
        "payments_pending": int(payments_pending["c"]),
    }


async def get_order_items(order_id: int) -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT oi.quantity, p.title, p.description, p.price, p.photo_file_id
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = ?
        ORDER BY oi.id
        """,
        (order_id,),
    )


async def rename_city(city_id: int, new_name: str) -> None:
    await _execute("UPDATE cities SET name = ? WHERE id = ?", (new_name, city_id))


async def rename_product(product_id: int, new_title: str) -> None:
    await _execute("UPDATE products SET title = ? WHERE id = ?", (new_title, product_id))


async def add_review(user_id: int, order_id: int, text: str) -> None:
    await _execute(
        "INSERT INTO reviews (user_id, order_id, text) VALUES (?, ?, ?)",
        (user_id, order_id, text),
    )


async def save_support_thread(
    user_tg_id: int, admin_group_id: int, admin_message_id: int
) -> None:
    await _execute(
        """
        INSERT INTO support_threads (user_tg_id, admin_group_id, admin_message_id)
        VALUES (?, ?, ?)
        """,
        (user_tg_id, admin_group_id, admin_message_id),
    )


async def get_user_by_admin_reply(
    admin_group_id: int, replied_message_id: int
) -> int | None:
    row = await _fetch_one(
        """
        SELECT user_tg_id
        FROM support_threads
        WHERE admin_group_id = ? AND admin_message_id = ?
        """,
        (admin_group_id, replied_message_id),
    )
    if not row:
        return None
    return int(row["user_tg_id"])


async def get_user_purchase_history(user_id: int) -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT o.id as order_id, o.total, o.created_at, o.status,
               p.title, oi.quantity, oi.price
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        JOIN products p ON p.id = oi.product_id
        WHERE o.user_id = ? AND o.status = 'paid'
        ORDER BY o.id DESC, oi.id ASC
        """,
        (user_id,),
    )


async def get_recent_reviews(limit: int = 20) -> list[aiosqlite.Row]:
    return await _fetch_all(
        """
        SELECT r.id, r.user_id, r.order_id, r.text, r.created_at
        FROM reviews r
        ORDER BY r.id DESC
        LIMIT ?
        """,
        (limit,),
    )
