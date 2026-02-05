from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"
DB_PATH = BASE_DIR / "data" / "shop.db"
LOG_PATH = BASE_DIR / "logs" / "bot.log"

REQUIRED_TABLES = {
    "users",
    "cities",
    "areas",
    "products",
    "cart_items",
    "orders",
    "order_items",
    "payments",
    "reviews",
    "support_threads",
    "variant_photos",
    "variants",
    "classes",
    "settings",
}


def _print(title: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "FAIL"
    line = f"[{status}] {title}"
    if detail:
        line += f" - {detail}"
    print(line)


def _load_env(path: Path) -> None:
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


def check_env() -> bool:
    _load_env(ENV_PATH)
    ok = True
    token = os.getenv("BOT_TOKEN", "").strip()
    admins = os.getenv("ADMIN_IDS", "").strip()
    group_id = os.getenv("ADMIN_GROUP_ID", "").strip()
    if not token:
        _print("BOT_TOKEN", False, "empty")
        ok = False
    else:
        _print("BOT_TOKEN", True)
    if not admins:
        _print("ADMIN_IDS", False, "empty")
        ok = False
    else:
        _print("ADMIN_IDS", True)
    try:
        int(group_id)
        _print("ADMIN_GROUP_ID", True)
    except Exception:
        _print("ADMIN_GROUP_ID", False, "not an integer")
        ok = False
    return ok


def check_paths() -> bool:
    ok = True
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.touch(exist_ok=True)
        _print("Log path", True, str(LOG_PATH))
    except Exception as exc:
        _print("Log path", False, str(exc))
        ok = False
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _print("DB dir", True, str(DB_PATH.parent))
    except Exception as exc:
        _print("DB dir", False, str(exc))
        ok = False
    return ok


def check_db() -> bool:
    if not DB_PATH.exists():
        _print("DB file", False, "not found")
        return False

    ok = True
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("PRAGMA foreign_keys = ON;")
            cur.close()

            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = {row[0] for row in cur.fetchall()}
            cur.close()

            missing = REQUIRED_TABLES - tables
            if missing:
                _print("DB tables", False, "missing: " + ", ".join(sorted(missing)))
                ok = False
            else:
                _print("DB tables", True)

            cur = conn.execute("SELECT COUNT(*) FROM variants")
            vcnt = cur.fetchone()[0]
            cur.close()
            _print("Variants", vcnt > 0, f"count={vcnt}")
            if vcnt <= 0:
                ok = False

            cur = conn.execute("SELECT COUNT(*) FROM classes")
            ccnt = cur.fetchone()[0]
            cur.close()
            _print("Classes", ccnt > 0, f"count={ccnt}")
            if ccnt <= 0:
                ok = False

            cur = conn.execute("SELECT COUNT(*) FROM cities")
            cities = cur.fetchone()[0]
            cur.close()
            _print("Cities", cities > 0, f"count={cities}")
            if cities <= 0:
                ok = False

            cur = conn.execute("SELECT COUNT(*) FROM areas")
            areas = cur.fetchone()[0]
            cur.close()
            _print("Areas", areas > 0, f"count={areas}")
            if areas <= 0:
                ok = False

    except Exception as exc:
        _print("DB connect", False, str(exc))
        return False

    return ok


def main() -> int:
    print("Bot Self-Check")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    ok = True
    if not check_env():
        ok = False
    if not check_paths():
        ok = False
    if not check_db():
        ok = False

    print("-")
    if ok:
        print("Result: OK")
        return 0
    print("Result: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
