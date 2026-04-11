"""SQLite database initialization and async queries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from config import DATABASE_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                client_id INTEGER,
                client_name TEXT,
                commission_type TEXT,
                tier TEXT,
                characters INTEGER,
                background TEXT,
                notes TEXT,
                status TEXT DEFAULT 'Queued',
                boostie INTEGER DEFAULT 0,
                reseller INTEGER DEFAULT 0,
                base_price REAL,
                final_price REAL,
                payment_method TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                channel_id INTEGER,
                thread_id INTEGER,
                client_id INTEGER,
                created_at TEXT,
                closed_at TEXT,
                transcript_sent INTEGER DEFAULT 0
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS warns (
                warn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                created_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS vouches (
                vouch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                order_id TEXT,
                rating INTEGER,
                message TEXT,
                created_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sticky_messages (
                channel_id INTEGER PRIMARY KEY,
                message_content TEXT,
                embed_json TEXT,
                last_message_id INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS loyalty (
                client_id INTEGER PRIMARY KEY,
                client_name TEXT,
                completed_count INTEGER DEFAULT 0,
                last_updated TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tos_agreements (
                user_id INTEGER PRIMARY KEY,
                agreed_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS shop_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                is_open INTEGER DEFAULT 0,
                last_toggled TEXT,
                toggled_by INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS queue_message (
                id INTEGER PRIMARY KEY DEFAULT 1,
                channel_id INTEGER,
                message_id INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS drops (
                drop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                client_id INTEGER,
                link TEXT,
                sent_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS persist_panels (
                panel TEXT PRIMARY KEY,
                channel_id INTEGER,
                message_id INTEGER
            )
            """
        )
        await db.commit()


# --- Orders ---


async def count_orders_in_month(year: int, month: int) -> int:
    prefix = f"MIKA-{month:02d}{year % 100:02d}-"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE order_id LIKE ?",
            (prefix + "%",),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def insert_order(
    order_id: str,
    client_id: int,
    client_name: str,
    commission_type: str,
    tier: str,
    characters: int,
    background: str,
    notes: str,
    status: str,
    boostie: int,
    reseller: int,
    base_price: float,
    final_price: float,
) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO orders (
                order_id, client_id, client_name, commission_type, tier,
                characters, background, notes, status, boostie, reseller,
                base_price, final_price, payment_method, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                order_id,
                client_id,
                client_name,
                commission_type,
                tier,
                characters,
                background,
                notes,
                status,
                boostie,
                reseller,
                base_price,
                final_price,
                now,
                now,
            ),
        )
        await db.commit()


async def get_order(order_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def delete_order(order_id: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        await db.commit()


async def update_order_status(order_id: str, status: str) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (status, now, order_id),
        )
        await db.commit()


async def list_active_orders() -> list[dict[str, Any]]:
    """Orders shown on queue board (excludes Done and Cancelled)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM orders
            WHERE status NOT IN ('Done', 'Cancelled')
            ORDER BY created_at ASC
            """
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Tickets ---


async def insert_ticket(
    order_id: str | None,
    channel_id: int,
    thread_id: int | None,
    client_id: int,
) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO tickets (order_id, channel_id, thread_id, client_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, channel_id, thread_id, client_id, now),
        )
        await db.commit()
        return int(cur.lastrowid)


async def update_ticket_order_id(channel_id: int, order_id: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE tickets SET order_id = ? WHERE channel_id = ?",
            (order_id, channel_id),
        )
        await db.commit()


async def get_open_ticket_by_user(client_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM tickets
            WHERE client_id = ? AND closed_at IS NULL
            ORDER BY ticket_id DESC LIMIT 1
            """,
            (client_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_ticket_by_channel(channel_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND closed_at IS NULL",
            (channel_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def delete_ticket_by_channel(channel_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel_id,))
        await db.commit()


async def close_ticket_record(channel_id: int, transcript_sent: int) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE tickets SET closed_at = ?, transcript_sent = ?
            WHERE channel_id = ?
            """,
            (now, transcript_sent, channel_id),
        )
        await db.commit()


async def get_ticket_by_order(order_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tickets WHERE order_id = ? AND closed_at IS NULL",
            (order_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# --- Warns ---


async def add_warn(user_id: int, moderator_id: int, reason: str) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO warns (user_id, moderator_id, reason, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, moderator_id, reason, now),
        )
        await db.commit()
        return int(cur.lastrowid)


async def count_warns(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM warns WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def list_warns(user_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM warns WHERE user_id = ? ORDER BY warn_id ASC",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def delete_warn(warn_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("DELETE FROM warns WHERE warn_id = ?", (warn_id,))
        await db.commit()
        return cur.rowcount > 0


async def clear_warns_user(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("DELETE FROM warns WHERE user_id = ?", (user_id,))
        await db.commit()
        return cur.rowcount


# --- Vouches ---


async def insert_vouch(
    client_id: int,
    order_id: str | None,
    rating: int,
    message: str,
) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO vouches (client_id, order_id, rating, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_id, order_id, rating, message, now),
        )
        await db.commit()
        return int(cur.lastrowid)


async def list_vouches_for_user(client_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM vouches WHERE client_id = ? ORDER BY vouch_id DESC",
            (client_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Sticky ---


async def upsert_sticky(
    channel_id: int,
    message_content: str,
    embed_json: str | None,
    last_message_id: int | None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO sticky_messages (channel_id, message_content, embed_json, last_message_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                message_content = excluded.message_content,
                embed_json = excluded.embed_json,
                last_message_id = excluded.last_message_id
            """,
            (channel_id, message_content, embed_json, last_message_id),
        )
        await db.commit()


async def update_sticky_message_id(channel_id: int, last_message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE sticky_messages SET last_message_id = ? WHERE channel_id = ?",
            (last_message_id, channel_id),
        )
        await db.commit()


async def get_sticky(channel_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM sticky_messages WHERE channel_id = ?", (channel_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def delete_sticky(channel_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM sticky_messages WHERE channel_id = ?", (channel_id,))
        await db.commit()


async def list_all_stickies() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM sticky_messages")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Loyalty ---


async def increment_loyalty(client_id: int, client_name: str) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO loyalty (client_id, client_name, completed_count, last_updated)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                completed_count = completed_count + 1,
                client_name = excluded.client_name,
                last_updated = excluded.last_updated
            """,
            (client_id, client_name, now),
        )
        await db.commit()
    row = await get_loyalty(client_id)
    return int(row["completed_count"]) if row else 1


async def get_loyalty(client_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM loyalty WHERE client_id = ?", (client_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def loyalty_top(limit: int = 10) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM loyalty ORDER BY completed_count DESC LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- TOS ---


async def log_tos_agreement(user_id: int) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO tos_agreements (user_id, agreed_at) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET agreed_at = excluded.agreed_at
            """,
            (user_id, now),
        )
        await db.commit()


# --- Shop ---


async def get_shop_state() -> dict[str, Any]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM shop_state WHERE id = 1")
        row = await cur.fetchone()
        if row:
            return dict(row)
        await db.execute(
            "INSERT INTO shop_state (id, is_open, last_toggled, toggled_by) VALUES (1, 0, NULL, NULL)"
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM shop_state WHERE id = 1")
        row = await cur.fetchone()
        return dict(row) if row else {"is_open": 0}


async def set_shop_state(
    is_open: bool,
    toggled_by: int | None,
) -> None:
    now = _utc_now()
    flag = 1 if is_open else 0
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT id FROM shop_state WHERE id = 1")
        exists = await cur.fetchone()
        if exists:
            await db.execute(
                """
                UPDATE shop_state SET is_open = ?, last_toggled = ?, toggled_by = ?
                WHERE id = 1
                """,
                (flag, now, toggled_by),
            )
        else:
            await db.execute(
                """
                INSERT INTO shop_state (id, is_open, last_toggled, toggled_by)
                VALUES (1, ?, ?, ?)
                """,
                (flag, now, toggled_by),
            )
        await db.commit()


# --- Queue message ---


async def set_queue_message(channel_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO queue_message (id, channel_id, message_id)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id
            """,
            (channel_id, message_id),
        )
        await db.commit()


async def get_queue_message() -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM queue_message WHERE id = 1")
        row = await cur.fetchone()
        return dict(row) if row else None


# --- Drops ---


async def insert_drop(order_id: str | None, client_id: int, link: str) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO drops (order_id, client_id, link, sent_at) VALUES (?, ?, ?, ?)",
            (order_id, client_id, link, now),
        )
        await db.commit()


async def list_drops_for_user(client_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM drops WHERE client_id = ? ORDER BY drop_id DESC",
            (client_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Persist panels (ticket, tos, payment) ---


async def set_persist_panel(panel: str, channel_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO persist_panels (panel, channel_id, message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(panel) DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id
            """,
            (panel, channel_id, message_id),
        )
        await db.commit()


async def get_persist_panel(panel: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM persist_panels WHERE panel = ?", (panel,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def shop_is_open_db() -> bool:
    st = await get_shop_state()
    return bool(st.get("is_open", 0))


# --- Stocks JSON ---


def load_stocks() -> dict[str, Any]:
    from config import STOCKS_FILE

    if not STOCKS_FILE.exists():
        STOCKS_FILE.write_text("{}", encoding="utf-8")
    return json.loads(STOCKS_FILE.read_text(encoding="utf-8"))


def save_stocks(data: dict[str, Any]) -> None:
    from config import STOCKS_FILE

    STOCKS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
