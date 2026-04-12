"""SQLite database initialization and async queries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from config import DATABASE_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_tickets_schema(db: aiosqlite.Connection) -> None:
    """Create or migrate `tickets` to channel_id PK + guild_id + form metadata."""
    cur = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tickets'"
    )
    if not await cur.fetchone():
        await db.execute(
            """
            CREATE TABLE tickets (
                channel_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                client_id INTEGER NOT NULL,
                button_id TEXT,
                answers TEXT,
                opened_at TEXT,
                closed_at TEXT,
                order_id TEXT,
                order_number INTEGER,
                transcript_sent INTEGER DEFAULT 0
            )
            """
        )
        return

    cur = await db.execute("PRAGMA table_info(tickets)")
    col_names = {row[1] for row in await cur.fetchall()}
    if "guild_id" in col_names:
        return

    await db.execute(
        """
        CREATE TABLE tickets_new (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            button_id TEXT,
            answers TEXT,
            opened_at TEXT,
            closed_at TEXT,
            order_id TEXT,
            order_number INTEGER,
            transcript_sent INTEGER DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        INSERT INTO tickets_new (
            channel_id, guild_id, client_id, button_id, answers, opened_at, closed_at,
            order_id, order_number, transcript_sent
        )
        SELECT
            channel_id,
            0,
            client_id,
            NULL,
            NULL,
            created_at,
            closed_at,
            order_id,
            order_number,
            COALESCE(transcript_sent, 0)
        FROM tickets
        """
    )
    await db.execute("DROP TABLE tickets")
    await db.execute("ALTER TABLE tickets_new RENAME TO tickets")


async def _ensure_ticket_buttons_columns(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(ticket_buttons)")
    cols = {row[1] for row in await cur.fetchall()}
    if "select_options" not in cols:
        await db.execute("ALTER TABLE ticket_buttons ADD COLUMN select_options TEXT")


async def _ensure_quote_and_wizard_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_guild_settings (
            guild_id INTEGER PRIMARY KEY,
            extra_character_php INTEGER NOT NULL DEFAULT 0,
            bg_simple_php INTEGER NOT NULL DEFAULT 0,
            bg_detailed_php INTEGER NOT NULL DEFAULT 0,
            brand_name TEXT DEFAULT 'Mikaelleon'
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_base_price (
            guild_id INTEGER NOT NULL,
            commission_type TEXT NOT NULL,
            tier TEXT NOT NULL,
            price_php INTEGER NOT NULL,
            PRIMARY KEY (guild_id, commission_type, tier)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_role_discount (
            guild_id INTEGER NOT NULL,
            discount_key TEXT NOT NULL,
            role_id INTEGER,
            percent REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, discount_key)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_currency (
            guild_id INTEGER NOT NULL,
            currency_code TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (guild_id, currency_code)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS wizard_sessions (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_flags (
            guild_id INTEGER PRIMARY KEY,
            setup_hint_sent INTEGER NOT NULL DEFAULT 0
        )
        """
    )


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
                color TEXT DEFAULT '#242429',
                image_url TEXT,
                footer TEXT,
                thumbnail_url TEXT,
                last_message_id INTEGER,
                created_by INTEGER,
                updated_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                value INTEGER NOT NULL,
                PRIMARY KEY (guild_id, setting_key)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_string_settings (
                guild_id INTEGER NOT NULL,
                setting_key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (guild_id, setting_key)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_panel (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                embed_title TEXT NOT NULL,
                embed_description TEXT NOT NULL,
                embed_color TEXT DEFAULT '#669b9a',
                embed_footer TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_buttons (
                button_id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                emoji TEXT,
                color TEXT DEFAULT 'blurple',
                category_id INTEGER,
                form_fields TEXT,
                select_options TEXT
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ticket_buttons_guild ON ticket_buttons (guild_id)"
        )

        await _ensure_tickets_schema(db)
        await _ensure_ticket_buttons_columns(db)
        await _ensure_quote_and_wizard_schema(db)
        await db.commit()


# --- Guild settings (channels / roles) ---


async def get_guild_setting(guild_id: int, key: str) -> int | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT value FROM guild_settings WHERE guild_id = ? AND setting_key = ?",
            (guild_id, key),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return int(row[0])


async def set_guild_setting(guild_id: int, key: str, value: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM guild_settings WHERE guild_id = ? AND setting_key = ?",
            (guild_id, key),
        )
        await db.execute(
            "INSERT INTO guild_settings (guild_id, setting_key, value) VALUES (?, ?, ?)",
            (guild_id, key, value),
        )
        await db.commit()


async def delete_guild_settings_keys(guild_id: int, keys: list[str]) -> None:
    if not keys:
        return
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for k in keys:
            await db.execute(
                "DELETE FROM guild_settings WHERE guild_id = ? AND setting_key = ?",
                (guild_id, k),
            )
        await db.commit()


async def delete_guild_string_settings_keys(guild_id: int, keys: list[str]) -> None:
    if not keys:
        return
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for k in keys:
            await db.execute(
                "DELETE FROM guild_string_settings WHERE guild_id = ? AND setting_key = ?",
                (guild_id, k),
            )
        await db.commit()


async def clear_quote_data_for_guild(guild_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM quote_base_price WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM quote_guild_settings WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM quote_role_discount WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM quote_currency WHERE guild_id = ?", (guild_id,))
        await db.commit()


async def list_guild_settings(guild_id: int) -> dict[str, int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT setting_key, value FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return {str(r["setting_key"]): int(r["value"]) for r in rows}


# --- Guild string settings (payment copy, etc.) ---


async def get_guild_string_setting(guild_id: int, key: str) -> str | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT value FROM guild_string_settings WHERE guild_id = ? AND setting_key = ?",
            (guild_id, key),
        )
        row = await cur.fetchone()
        if not row:
            return None
        v = row[0]
        return str(v) if v is not None and str(v).strip() else None


async def set_guild_string_setting(guild_id: int, key: str, value: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM guild_string_settings WHERE guild_id = ? AND setting_key = ?",
            (guild_id, key),
        )
        await db.execute(
            "INSERT INTO guild_string_settings (guild_id, setting_key, value) VALUES (?, ?, ?)",
            (guild_id, key, value),
        )
        await db.commit()


async def list_guild_string_settings(guild_id: int) -> dict[str, str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT setting_key, value FROM guild_string_settings WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return {str(r["setting_key"]): str(r["value"]) for r in rows}


# --- Orders ---


async def count_orders_in_month(
    year: int, month: int, order_prefix: str = "MIKA"
) -> int:
    p = (order_prefix or "MIKA").strip()[:24]
    prefix = f"{p}-{month:02d}{year % 100:02d}-"
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


async def insert_ticket_open(
    channel_id: int,
    guild_id: int,
    client_id: int,
    *,
    button_id: str | None = None,
    answers: dict[str, Any] | None = None,
) -> None:
    now = _utc_now()
    ans_json = json.dumps(answers) if answers is not None else None
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO tickets (
                channel_id, guild_id, client_id, button_id, answers, opened_at,
                order_id, order_number, transcript_sent
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 0)
            """,
            (channel_id, guild_id, client_id, button_id, ans_json, now),
        )
        await db.commit()


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


async def get_open_ticket_by_user(
    client_id: int, guild_id: int
) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM tickets
            WHERE client_id = ? AND guild_id = ? AND closed_at IS NULL
            ORDER BY opened_at DESC LIMIT 1
            """,
            (client_id, guild_id),
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


# --- Ticket panel (configurable buttons + forms) ---


async def get_ticket_panel(guild_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ticket_panel WHERE guild_id = ?", (guild_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_ticket_panel(
    guild_id: int,
    channel_id: int,
    message_id: int,
    embed_title: str,
    embed_description: str,
    embed_color: str,
    embed_footer: str | None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO ticket_panel (
                guild_id, channel_id, message_id, embed_title, embed_description,
                embed_color, embed_footer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id,
                embed_title = excluded.embed_title,
                embed_description = excluded.embed_description,
                embed_color = excluded.embed_color,
                embed_footer = excluded.embed_footer
            """,
            (
                guild_id,
                channel_id,
                message_id,
                embed_title,
                embed_description,
                embed_color,
                embed_footer,
            ),
        )
        await db.commit()


async def count_ticket_buttons(guild_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM ticket_buttons WHERE guild_id = ?", (guild_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def list_ticket_buttons(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ticket_buttons WHERE guild_id = ? ORDER BY label",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_ticket_button_by_id(button_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ticket_buttons WHERE button_id = ?", (button_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def find_ticket_button_by_label(
    guild_id: int, label: str
) -> dict[str, Any] | None:
    label_l = label.strip().lower()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ticket_buttons WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cur.fetchall()
        for r in rows:
            if str(r["label"]).strip().lower() == label_l:
                return dict(r)
        return None


async def insert_ticket_button(
    button_id: str,
    guild_id: int,
    label: str,
    emoji: str | None,
    color: str,
    category_id: int | None,
    form_fields: str | None,
    select_options: str | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO ticket_buttons (
                button_id, guild_id, label, emoji, color, category_id, form_fields, select_options
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (button_id, guild_id, label, emoji, color, category_id, form_fields, select_options),
        )
        await db.commit()


async def delete_ticket_button_by_label(guild_id: int, label: str) -> bool:
    row = await find_ticket_button_by_label(guild_id, label)
    if not row:
        return False
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM ticket_buttons WHERE button_id = ?", (row["button_id"],)
        )
        await db.commit()
    return True


async def update_ticket_button_form_fields(button_id: str, form_fields: str | None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE ticket_buttons SET form_fields = ? WHERE button_id = ?",
            (form_fields, button_id),
        )
        await db.commit()


async def update_ticket_button_select_options(
    button_id: str, select_options: str | None
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE ticket_buttons SET select_options = ? WHERE button_id = ?",
            (select_options, button_id),
        )
        await db.commit()


async def all_ticket_panels() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM ticket_panel")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


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
                fields.get("color") or "#242429",
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


# --- Quote calculator ---


async def guild_has_any_config(guild_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM guild_settings WHERE guild_id = ? LIMIT 1", (guild_id,)
        )
        if await cur.fetchone():
            return True
        cur = await db.execute(
            "SELECT 1 FROM guild_string_settings WHERE guild_id = ? LIMIT 1",
            (guild_id,),
        )
        return await cur.fetchone() is not None


async def get_quote_guild_settings(guild_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM quote_guild_settings WHERE guild_id = ?", (guild_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_quote_guild_settings(
    guild_id: int,
    *,
    extra_character_php: int | None = None,
    bg_simple_php: int | None = None,
    bg_detailed_php: int | None = None,
    brand_name: str | None = None,
) -> None:
    row = await get_quote_guild_settings(guild_id)
    ex = row["extra_character_php"] if row else 0
    bs = row["bg_simple_php"] if row else 0
    bd = row["bg_detailed_php"] if row else 0
    br = row["brand_name"] if row else "Mikaelleon"
    if extra_character_php is not None:
        ex = extra_character_php
    if bg_simple_php is not None:
        bs = bg_simple_php
    if bg_detailed_php is not None:
        bd = bg_detailed_php
    if brand_name is not None:
        br = brand_name[:200]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO quote_guild_settings (
                guild_id, extra_character_php, bg_simple_php, bg_detailed_php, brand_name
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                extra_character_php = excluded.extra_character_php,
                bg_simple_php = excluded.bg_simple_php,
                bg_detailed_php = excluded.bg_detailed_php,
                brand_name = excluded.brand_name
            """,
            (guild_id, ex, bs, bd, br),
        )
        await db.commit()


async def list_quote_base_prices(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM quote_base_price WHERE guild_id = ? ORDER BY commission_type, tier",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def upsert_quote_base_price(
    guild_id: int, commission_type: str, tier: str, price_php: int
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO quote_base_price (guild_id, commission_type, tier, price_php)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, commission_type, tier) DO UPDATE SET
                price_php = excluded.price_php
            """,
            (guild_id, commission_type[:80], tier[:80], price_php),
        )
        await db.commit()


async def get_quote_discount(
    guild_id: int, discount_key: str
) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM quote_role_discount WHERE guild_id = ? AND discount_key = ?",
            (guild_id, discount_key),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_quote_discount(
    guild_id: int,
    discount_key: str,
    *,
    role_id: int | None,
    percent: float,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO quote_role_discount (guild_id, discount_key, role_id, percent)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, discount_key) DO UPDATE SET
                role_id = excluded.role_id,
                percent = excluded.percent
            """,
            (guild_id, discount_key[:32], role_id, percent),
        )
        await db.commit()


async def list_quote_currencies(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM quote_currency WHERE guild_id = ? ORDER BY currency_code",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def set_quote_currency_enabled(
    guild_id: int, currency_code: str, enabled: bool
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO quote_currency (guild_id, currency_code, enabled)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, currency_code) DO UPDATE SET enabled = excluded.enabled
            """,
            (guild_id, currency_code.upper()[:8], 1 if enabled else 0),
        )
        await db.commit()


async def ensure_default_quote_currencies(guild_id: int) -> None:
    defaults = ("USD", "SGD", "MYR", "EUR")
    existing = {r["currency_code"] for r in await list_quote_currencies(guild_id)}
    for code in defaults:
        if code not in existing:
            await set_quote_currency_enabled(guild_id, code, True)


# --- Wizard session + guild flags ---


async def get_wizard_session(guild_id: int, user_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM wizard_sessions WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def save_wizard_session(
    guild_id: int, user_id: int, state: dict[str, Any]
) -> None:
    now = _utc_now()
    raw = json.dumps(state, ensure_ascii=False)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO wizard_sessions (guild_id, user_id, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (guild_id, user_id, raw, now),
        )
        await db.commit()


async def delete_wizard_session(guild_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM wizard_sessions WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await db.commit()


async def get_setup_hint_sent(guild_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT setup_hint_sent FROM guild_flags WHERE guild_id = ?", (guild_id,)
        )
        row = await cur.fetchone()
        return bool(row and row[0])


async def set_setup_hint_sent(guild_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO guild_flags (guild_id, setup_hint_sent)
            VALUES (?, 1)
            ON CONFLICT(guild_id) DO UPDATE SET setup_hint_sent = 1
            """,
            (guild_id,),
        )
        await db.commit()


# --- Default templates JSON (sync) ---


def load_default_templates() -> dict[str, str]:
    import json

    from config import TEMPLATES_FILE

    if not TEMPLATES_FILE.exists():
        return {}
    return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
