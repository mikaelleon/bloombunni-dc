"""SQLite database initialization and async queries."""

from __future__ import annotations

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
                handler_id INTEGER,
                client_id INTEGER,
                client_name TEXT,
                item TEXT,
                amount TEXT,
                mop TEXT,
                price TEXT,
                ticket_channel_id INTEGER,
                status TEXT DEFAULT 'Noted',
                queue_message_id INTEGER,
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
                client_id INTEGER,
                order_number INTEGER,
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
                message TEXT,
                created_at TEXT
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
            CREATE TABLE IF NOT EXISTS message_templates (
                template_key TEXT PRIMARY KEY,
                content TEXT,
                updated_by INTEGER,
                updated_at TEXT
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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sticky_messages (
                channel_id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                color TEXT DEFAULT '#669b9a',
                image_url TEXT,
                footer TEXT,
                thumbnail_url TEXT,
                last_message_id INTEGER,
                created_by INTEGER,
                updated_at TEXT
            )
            """
        )
        await db.commit()


# --- Orders ---


async def count_orders_in_month(year: int, month: int) -> int:
    prefix = f"MIKA-{month:02d}{year % 100:02d}-"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE order_id LIKE ?",
            (prefix + "%",),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def count_orders_for_buyer(client_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE client_id = ?", (client_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def insert_order(
    order_id: str,
    handler_id: int,
    client_id: int,
    client_name: str,
    item: str,
    amount: str,
    mop: str,
    price: str,
    ticket_channel_id: int,
    status: str,
) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO orders (
                order_id, handler_id, client_id, client_name, item, amount,
                mop, price, ticket_channel_id, status, queue_message_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                order_id,
                handler_id,
                client_id,
                client_name,
                item,
                amount,
                mop,
                price,
                ticket_channel_id,
                status,
                now,
                now,
            ),
        )
        await db.commit()


async def set_order_queue_message_id(order_id: str, queue_message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET queue_message_id = ? WHERE order_id = ?",
            (queue_message_id, order_id),
        )
        await db.commit()


async def get_order(order_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_order_status(order_id: str, status: str) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (status, now, order_id),
        )
        await db.commit()


async def list_orders_for_status_views() -> list[dict[str, Any]]:
    """Orders that may still have a status dropdown in the ticket channel."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM orders
            WHERE status IN ('Noted', 'Processing')
            AND queue_message_id IS NOT NULL
            """,
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Tickets ---


async def insert_ticket_open(channel_id: int, client_id: int) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO tickets (order_id, channel_id, client_id, order_number, created_at)
            VALUES (NULL, ?, ?, NULL, ?)
            """,
            (channel_id, client_id, now),
        )
        await db.commit()
        return int(cur.lastrowid)


async def update_ticket_order(
    channel_id: int, order_id: str, order_number: int
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE tickets SET order_id = ?, order_number = ?
            WHERE channel_id = ?
            """,
            (order_id, order_number, channel_id),
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


async def delete_ticket_by_channel(channel_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel_id,))
        await db.commit()


# --- Message templates ---


async def get_message_template_row(key: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM message_templates WHERE template_key = ?", (key,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_message_template(
    key: str, content: str, updated_by: int
) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO message_templates (template_key, content, updated_by, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(template_key) DO UPDATE SET
                content = excluded.content,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (key, content, updated_by, now),
        )
        await db.commit()


async def delete_all_message_templates() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("DELETE FROM message_templates")
        await db.commit()
        return cur.rowcount


async def list_message_template_rows() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM message_templates ORDER BY template_key"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


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


async def insert_vouch(client_id: int, order_id: str | None, message: str) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO vouches (client_id, order_id, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (client_id, order_id, message, now),
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
            "SELECT * FROM loyalty ORDER BY completed_count DESC LIMIT ?",
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


async def set_shop_state(is_open: bool, toggled_by: int | None) -> None:
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


async def shop_is_open_db() -> bool:
    st = await get_shop_state()
    return bool(st.get("is_open", 0))


# --- Persist panels ---


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


# --- Sticky messages ---


async def upsert_sticky_full(
    channel_id: int,
    title: str,
    description: str,
    color: str,
    image_url: str | None,
    footer: str | None,
    thumbnail_url: str | None,
    last_message_id: int | None,
    created_by: int,
) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO sticky_messages (
                channel_id, title, description, color, image_url, footer,
                thumbnail_url, last_message_id, created_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                color = excluded.color,
                image_url = excluded.image_url,
                footer = excluded.footer,
                thumbnail_url = excluded.thumbnail_url,
                last_message_id = excluded.last_message_id,
                created_by = excluded.created_by,
                updated_at = excluded.updated_at
            """,
            (
                channel_id,
                title,
                description,
                color,
                image_url,
                footer,
                thumbnail_url,
                last_message_id,
                created_by,
                now,
            ),
        )
        await db.commit()


async def patch_sticky(channel_id: int, updates: dict[str, Any]) -> bool:
    """Merge `updates` into existing row. Returns False if no row exists."""
    row = await get_sticky(channel_id)
    if not row:
        return False
    now = _utc_now()
    fields: dict[str, Any] = dict(row)
    for k, v in updates.items():
        fields[k] = v
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE sticky_messages SET
                title = ?, description = ?, color = ?, image_url = ?,
                footer = ?, thumbnail_url = ?, updated_at = ?
            WHERE channel_id = ?
            """,
            (
                fields.get("title"),
                fields.get("description"),
                fields.get("color") or "#669b9a",
                fields.get("image_url"),
                fields.get("footer"),
                fields.get("thumbnail_url"),
                now,
                channel_id,
            ),
        )
        await db.commit()
    return True


async def set_sticky_last_message_id(channel_id: int, message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE sticky_messages SET last_message_id = ? WHERE channel_id = ?",
            (message_id, channel_id),
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


async def delete_sticky(channel_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "DELETE FROM sticky_messages WHERE channel_id = ?", (channel_id,)
        )
        await db.commit()
        return cur.rowcount > 0


async def list_all_stickies() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM sticky_messages ORDER BY channel_id"
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def all_sticky_channel_ids() -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT channel_id FROM sticky_messages")
        rows = await cur.fetchall()
        return [int(r[0]) for r in rows]


# --- Default templates JSON (sync) ---


def load_default_templates() -> dict[str, str]:
    import json

    from config import TEMPLATES_FILE

    if not TEMPLATES_FILE.exists():
        return {}
    return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
