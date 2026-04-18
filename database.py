"""SQLite database initialization and async queries."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite

from config import DATABASE_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SLOW_QUERY_THRESHOLD_MS = 200.0


async def _record_slow_query(name: str, elapsed_ms: float) -> None:
    if elapsed_ms < _SLOW_QUERY_THRESHOLD_MS:
        return
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO slow_query_events (query_name, elapsed_ms, created_at)
            VALUES (?, ?, ?)
            """,
            (name[:120], float(elapsed_ms), _utc_now()),
        )
        await db.commit()


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


async def _ensure_tickets_extended_columns(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(tickets)")
    cols = {row[1] for row in await cur.fetchall()}
    migrations: list[tuple[str, str]] = [
        ("quote_total_php", "REAL"),
        ("quote_usd_approx", "REAL"),
        ("quote_snapshot_json", "TEXT"),
        ("rendering_tier", "TEXT"),
        ("background", "TEXT"),
        ("char_count_key", "TEXT"),
        ("rush_addon", "INTEGER DEFAULT 0"),
        ("ticket_status", "TEXT DEFAULT 'open'"),
        ("wip_stage", "TEXT"),
        ("revision_count", "INTEGER DEFAULT 0"),
        ("revision_extra_fee_php", "REAL DEFAULT 0"),
        ("references_json", "TEXT"),
        ("downpayment_confirmed", "INTEGER DEFAULT 0"),
        ("active_hours_notified", "INTEGER DEFAULT 0"),
        ("quote_expires_at", "TEXT"),
        ("quote_approved", "INTEGER DEFAULT 0"),
        ("payment_status", "TEXT DEFAULT 'awaiting_payment'"),
        ("payment_proof_url", "TEXT"),
        ("close_approved_by_client", "INTEGER DEFAULT 0"),
        ("close_approved_at", "TEXT"),
        ("deleted_at", "TEXT"),
    ]
    for name, typ in migrations:
        if name not in cols:
            await db.execute(f"ALTER TABLE tickets ADD COLUMN {name} {typ}")


async def _ensure_ticket_buttons_age_gate(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(ticket_buttons)")
    cols = {row[1] for row in await cur.fetchall()}
    if "require_age_verified" not in cols:
        await db.execute(
            "ALTER TABLE ticket_buttons ADD COLUMN require_age_verified INTEGER DEFAULT 0"
        )


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


async def _ensure_tos_version_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS tos_meta (
            id INTEGER PRIMARY KEY DEFAULT 1,
            current_version INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    await db.execute(
        """
        INSERT INTO tos_meta (id, current_version)
        VALUES (1, 1)
        ON CONFLICT(id) DO NOTHING
        """
    )
    cur = await db.execute("PRAGMA table_info(tos_agreements)")
    cols = {row[1] for row in await cur.fetchall()}
    if "tos_version" not in cols:
        await db.execute(
            "ALTER TABLE tos_agreements ADD COLUMN tos_version INTEGER NOT NULL DEFAULT 1"
        )


async def _ensure_soft_delete_columns(db: aiosqlite.Connection) -> None:
    specs = {
        "orders": "deleted_at",
        "warns": "deleted_at",
        "vouches": "deleted_at",
        "loyalty": "deleted_at",
    }
    for table, col in specs.items():
        cur = await db.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in await cur.fetchall()}
        if col not in cols:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")


async def _ensure_schema_migrations_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


async def _ensure_db_backup_schedule_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS db_backup_schedule (
            owner_user_id INTEGER PRIMARY KEY,
            hour_utc INTEGER NOT NULL,
            minute_utc INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_sent_date TEXT
        )
        """
    )


async def _ensure_config_audit_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS config_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            changed_by INTEGER NOT NULL,
            key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_at TEXT NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS config_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


async def _ensure_ticket_ops_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_notes (
            note_id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur = await db.execute("PRAGMA table_info(tickets)")
    cols = {row[1] for row in await cur.fetchall()}
    if "assigned_staff_id" not in cols:
        await db.execute("ALTER TABLE tickets ADD COLUMN assigned_staff_id INTEGER")


async def _ensure_shop_state_reason(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(shop_state)")
    cols = {row[1] for row in await cur.fetchall()}
    if "close_reason" not in cols:
        await db.execute("ALTER TABLE shop_state ADD COLUMN close_reason TEXT")


async def _ensure_sticky_p3_schema(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(sticky_messages)")
    cols = {row[1] for row in await cur.fetchall()}
    if "paused" not in cols:
        await db.execute("ALTER TABLE sticky_messages ADD COLUMN paused INTEGER DEFAULT 0")
    if "cooldown_seconds" not in cols:
        await db.execute("ALTER TABLE sticky_messages ADD COLUMN cooldown_seconds INTEGER DEFAULT 2")
    if "last_repost_at" not in cols:
        await db.execute("ALTER TABLE sticky_messages ADD COLUMN last_repost_at TEXT")


async def _ensure_slow_query_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS slow_query_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_name TEXT NOT NULL,
            elapsed_ms REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


async def _ensure_embed_builder_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS embed_builder_meta (
            guild_id INTEGER PRIMARY KEY,
            last_assigned_id INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS embed_builder_staff_roles (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, role_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS embed_builder_embeds (
            guild_id INTEGER NOT NULL,
            embed_id TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_edited_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            author_text TEXT,
            author_icon TEXT,
            title TEXT,
            description TEXT,
            footer_text TEXT,
            footer_icon TEXT,
            thumbnail_url TEXT,
            image_url TEXT,
            color TEXT NOT NULL DEFAULT '#5865F2',
            ts_enabled INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, embed_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS embed_builder_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            embed_id TEXT NOT NULL,
            channel_id INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )


async def _ensure_button_builder_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS button_builder_meta (
            guild_id INTEGER PRIMARY KEY,
            last_assigned_id INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS button_builder_buttons (
            guild_id INTEGER NOT NULL,
            button_id TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_edited_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            label TEXT NOT NULL DEFAULT 'Button',
            emoji_str TEXT,
            style TEXT NOT NULL DEFAULT 'secondary',
            action_type TEXT NOT NULL DEFAULT 'toggle_role',
            role_id INTEGER,
            internal_label TEXT,
            internal_note TEXT,
            responses_json TEXT,
            PRIMARY KEY (guild_id, button_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS button_builder_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            button_id TEXT NOT NULL,
            channel_id INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )


async def _ensure_autoresponder_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ar_builder_meta (
            guild_id INTEGER PRIMARY KEY,
            last_assigned_id INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ar_builder_entries (
            guild_id INTEGER NOT NULL,
            ar_id TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_edited_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            trigger_type TEXT NOT NULL DEFAULT 'message',
            match_mode TEXT NOT NULL DEFAULT 'exact',
            triggers_json TEXT NOT NULL DEFAULT '',
            response_text TEXT,
            priority INTEGER NOT NULL DEFAULT 100,
            cooldown_seconds INTEGER NOT NULL DEFAULT 0,
            required_role_id INTEGER,
            denied_role_id INTEGER,
            required_channel_id INTEGER,
            denied_channel_id INTEGER,
            fire_count INTEGER NOT NULL DEFAULT 0,
            last_fired_at TEXT,
            internal_label TEXT,
            internal_note TEXT,
            PRIMARY KEY (guild_id, ar_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ar_builder_user_cooldowns (
            guild_id INTEGER NOT NULL,
            ar_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            last_fired_ts INTEGER NOT NULL,
            PRIMARY KEY (guild_id, ar_id, user_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS ar_builder_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            ar_id TEXT NOT NULL,
            channel_id INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )


async def _ensure_autoresponder_trigger_columns(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(ar_builder_entries)")
    cols = {row[1] for row in await cur.fetchall()}
    if "trigger_role_id" not in cols:
        await db.execute("ALTER TABLE ar_builder_entries ADD COLUMN trigger_role_id INTEGER")
    if "trigger_channel_id" not in cols:
        await db.execute("ALTER TABLE ar_builder_entries ADD COLUMN trigger_channel_id INTEGER")
    if "trigger_message_id" not in cols:
        await db.execute("ALTER TABLE ar_builder_entries ADD COLUMN trigger_message_id INTEGER")
    if "trigger_emoji" not in cols:
        await db.execute("ALTER TABLE ar_builder_entries ADD COLUMN trigger_emoji TEXT")


async def _ensure_ticket_deleted_at_column(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(tickets)")
    cols = {row[1] for row in await cur.fetchall()}
    if "deleted_at" not in cols:
        await db.execute("ALTER TABLE tickets ADD COLUMN deleted_at TEXT")


async def _ensure_loyalty_cards_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS loyalty_card_meta (
            guild_id INTEGER PRIMARY KEY,
            next_seq INTEGER NOT NULL DEFAULT 0,
            recycled_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS loyalty_card_images (
            guild_id INTEGER NOT NULL,
            stamp_index INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            PRIMARY KEY (guild_id, stamp_index)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS loyalty_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            card_number INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            stamp_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            message_id INTEGER,
            thread_id INTEGER,
            channel_id INTEGER NOT NULL,
            ticket_channel_id INTEGER,
            created_at TEXT NOT NULL,
            void_deadline_ts INTEGER,
            first_vouch_ts INTEGER,
            UNIQUE (guild_id, card_number)
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_loyalty_cards_guild_user ON loyalty_cards (guild_id, user_id, status)"
    )


async def _ensure_orders_review_submitted_column(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(orders)")
    cols = {row[1] for row in await cur.fetchall()}
    if "review_submitted" not in cols:
        await db.execute(
            "ALTER TABLE orders ADD COLUMN review_submitted INTEGER NOT NULL DEFAULT 0"
        )


async def _ensure_tickets_last_client_remind_at_column(db: aiosqlite.Connection) -> None:
    cur = await db.execute("PRAGMA table_info(tickets)")
    cols = {row[1] for row in await cur.fetchall()}
    if "last_client_remind_at" not in cols:
        await db.execute(
            "ALTER TABLE tickets ADD COLUMN last_client_remind_at TEXT"
        )


async def _ensure_reviews_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS commission_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            order_id TEXT NOT NULL,
            overall_quality INTEGER NOT NULL,
            communication INTEGER NOT NULL,
            turnaround INTEGER NOT NULL,
            process_smoothness INTEGER NOT NULL,
            enjoyed_most TEXT,
            improvements TEXT,
            commission_again TEXT NOT NULL,
            recommend_friend TEXT NOT NULL,
            testimonial_consent TEXT NOT NULL,
            discount_code TEXT,
            created_at TEXT NOT NULL,
            UNIQUE (guild_id, reviewer_id, order_id)
        )
        """
    )
    await db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_commission_reviews_lookup
        ON commission_reviews (guild_id, reviewer_id, order_id)
        """
    )


async def _migration_applied(db: aiosqlite.Connection, version: int) -> bool:
    cur = await db.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ? LIMIT 1",
        (version,),
    )
    return await cur.fetchone() is not None


async def _record_migration(db: aiosqlite.Connection, version: int, name: str) -> None:
    await db.execute(
        """
        INSERT INTO schema_migrations (version, name, applied_at)
        VALUES (?, ?, ?)
        """,
        (version, name, _utc_now()),
    )


async def _run_migration(
    db: aiosqlite.Connection, version: int, name: str, runner
) -> None:
    if await _migration_applied(db, version):
        return
    await runner(db)
    await _record_migration(db, version, name)


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

        await _ensure_schema_migrations_table(db)
        await _run_migration(db, 1, "ensure_tickets_schema", _ensure_tickets_schema)
        await _run_migration(
            db, 2, "ensure_ticket_buttons_columns", _ensure_ticket_buttons_columns
        )
        await _run_migration(
            db, 3, "ensure_tickets_extended_columns", _ensure_tickets_extended_columns
        )
        await _run_migration(
            db, 4, "ensure_ticket_buttons_age_gate", _ensure_ticket_buttons_age_gate
        )
        await _run_migration(
            db, 5, "ensure_quote_and_wizard_schema", _ensure_quote_and_wizard_schema
        )
        await _run_migration(
            db, 6, "ensure_db_backup_schedule_table", _ensure_db_backup_schedule_table
        )
        await _run_migration(db, 7, "ensure_tos_version_schema", _ensure_tos_version_schema)
        await _run_migration(db, 8, "ensure_soft_delete_columns", _ensure_soft_delete_columns)
        await _run_migration(db, 9, "ensure_config_audit_schema", _ensure_config_audit_schema)
        await _run_migration(db, 10, "ensure_ticket_ops_schema", _ensure_ticket_ops_schema)
        await _run_migration(db, 11, "ensure_shop_state_reason", _ensure_shop_state_reason)
        await _run_migration(db, 12, "ensure_sticky_p3_schema", _ensure_sticky_p3_schema)
        await _run_migration(db, 13, "ensure_slow_query_schema", _ensure_slow_query_schema)
        await _run_migration(db, 14, "ensure_embed_builder_schema", _ensure_embed_builder_schema)
        await _run_migration(db, 15, "ensure_button_builder_schema", _ensure_button_builder_schema)
        await _run_migration(db, 16, "ensure_autoresponder_schema", _ensure_autoresponder_schema)
        await _run_migration(db, 17, "ensure_autoresponder_trigger_columns", _ensure_autoresponder_trigger_columns)
        await _run_migration(db, 18, "ensure_loyalty_cards_schema", _ensure_loyalty_cards_schema)
        await _run_migration(db, 19, "ensure_ticket_deleted_at_column", _ensure_ticket_deleted_at_column)
        await _run_migration(db, 20, "ensure_reviews_schema", _ensure_reviews_schema)
        await _run_migration(db, 21, "ensure_orders_review_submitted_column", _ensure_orders_review_submitted_column)
        await _run_migration(
            db, 22, "ensure_tickets_last_client_remind_at_column", _ensure_tickets_last_client_remind_at_column
        )
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


async def log_config_change(
    guild_id: int,
    changed_by: int,
    key: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO config_audit_log (guild_id, changed_by, key, old_value, new_value, changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (guild_id, changed_by, key[:100], old_value, new_value, _utc_now()),
        )
        await db.commit()


async def list_config_audit_log(guild_id: int, limit: int = 20) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM config_audit_log
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, int(limit)),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def create_config_snapshot(guild_id: int, created_by: int) -> int:
    payload = {
        "settings": await list_guild_settings(guild_id),
        "string_settings": await list_guild_string_settings(guild_id),
    }
    raw = json.dumps(payload, ensure_ascii=False)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO config_snapshots (guild_id, created_by, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, created_by, raw, _utc_now()),
        )
        await db.commit()
        return int(cur.lastrowid)


async def list_config_snapshots(guild_id: int, limit: int = 5) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM config_snapshots
            WHERE guild_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (guild_id, int(limit)),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def apply_config_snapshot(guild_id: int, snapshot_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT payload_json FROM config_snapshots WHERE id = ? AND guild_id = ?",
            (snapshot_id, guild_id),
        )
        row = await cur.fetchone()
        if not row:
            return False
        try:
            payload = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError:
            return False
        settings = payload.get("settings", {}) or {}
        str_settings = payload.get("string_settings", {}) or {}
        await db.execute("DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,))
        await db.execute("DELETE FROM guild_string_settings WHERE guild_id = ?", (guild_id,))
        for k, v in settings.items():
            await db.execute(
                "INSERT INTO guild_settings (guild_id, setting_key, value) VALUES (?, ?, ?)",
                (guild_id, str(k), int(v)),
            )
        for k, v in str_settings.items():
            await db.execute(
                "INSERT INTO guild_string_settings (guild_id, setting_key, value) VALUES (?, ?, ?)",
                (guild_id, str(k), str(v)),
            )
        await db.commit()
        return True


# --- Orders ---


async def count_orders_in_month(
    year: int, month: int, order_prefix: str = "MIKA"
) -> int:
    p = (order_prefix or "MIKA").strip()[:24]
    prefix = f"{p}-{month:02d}{year % 100:02d}-"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE order_id LIKE ? AND deleted_at IS NULL",
            (prefix + "%",),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def count_orders_for_buyer(client_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM orders WHERE client_id = ? AND deleted_at IS NULL", (client_id,)
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
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE order_id = ? AND deleted_at IS NULL",
            (order_id,),
        )
        row = await cur.fetchone()
        out = dict(row) if row else None
    await _record_slow_query("get_order", (time.perf_counter() - t0) * 1000.0)
    return out


async def get_order_for_ticket_client(ticket_channel_id: int, client_id: int) -> dict[str, Any] | None:
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE ticket_channel_id = ? AND client_id = ? AND deleted_at IS NULL
                ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC
                LIMIT 1
                """,
                (int(ticket_channel_id), int(client_id)),
            )
        except aiosqlite.OperationalError as e:
            if "no such column: deleted_at" not in str(e):
                raise
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE ticket_channel_id = ? AND client_id = ?
                ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC
                LIMIT 1
                """,
                (int(ticket_channel_id), int(client_id)),
            )
        row = await cur.fetchone()
        out = dict(row) if row else None
    await _record_slow_query(
        "get_order_for_ticket_client", (time.perf_counter() - t0) * 1000.0
    )
    return out


async def list_orders_for_client(client_id: int, limit: int = 25) -> list[dict[str, Any]]:
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE client_id = ? AND deleted_at IS NULL
                ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC
                LIMIT ?
                """,
                (int(client_id), int(limit)),
            )
        except aiosqlite.OperationalError as e:
            if "no such column: deleted_at" not in str(e):
                raise
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE client_id = ?
                ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC
                LIMIT ?
                """,
                (int(client_id), int(limit)),
            )
        rows = await cur.fetchall()
        out = [dict(r) for r in rows]
    await _record_slow_query("list_orders_for_client", (time.perf_counter() - t0) * 1000.0)
    return out


async def list_reviewable_orders_for_client(
    guild_id: int, client_id: int, limit: int = 50
) -> list[dict[str, Any]]:
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                """
                SELECT o.*
                FROM orders o
                WHERE o.client_id = ?
                  AND o.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM commission_reviews r
                      WHERE r.guild_id = ? AND r.reviewer_id = ? AND r.order_id = o.order_id
                  )
                ORDER BY datetime(o.updated_at) DESC, datetime(o.created_at) DESC
                LIMIT ?
                """,
                (int(client_id), int(guild_id), int(client_id), int(limit)),
            )
        except aiosqlite.OperationalError as e:
            if "no such column: o.deleted_at" not in str(e):
                raise
            cur = await db.execute(
                """
                SELECT o.*
                FROM orders o
                WHERE o.client_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM commission_reviews r
                      WHERE r.guild_id = ? AND r.reviewer_id = ? AND r.order_id = o.order_id
                  )
                ORDER BY datetime(o.updated_at) DESC, datetime(o.created_at) DESC
                LIMIT ?
                """,
                (int(client_id), int(guild_id), int(client_id), int(limit)),
            )
        rows = await cur.fetchall()
        out = [dict(r) for r in rows]
    await _record_slow_query(
        "list_reviewable_orders_for_client", (time.perf_counter() - t0) * 1000.0
    )
    return out


async def list_reviewable_order_tags_for_client(
    guild_id: int, client_id: int, limit: int = 50
) -> list[dict[str, Any]]:
    """Registered orders only: vouched and not yet reviewed (see list_orders_eligible_for_review)."""
    rows = await list_orders_eligible_for_review(guild_id, client_id, limit)
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "order_id": str(r.get("order_id") or ""),
                "ticket_channel_id": r.get("ticket_channel_id"),
                "source": "order",
                "last_ts": r.get("updated_at") or r.get("created_at"),
            }
        )
    return out


async def update_order_status(order_id: str, status: str) -> None:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ? AND deleted_at IS NULL",
            (status, now, order_id),
        )
        await db.commit()


async def list_orders_for_status_views() -> list[dict[str, Any]]:
    """Orders that may still have a status dropdown in the ticket channel."""
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM orders
            WHERE status IN ('Noted', 'Processing')
            AND queue_message_id IS NOT NULL
            AND deleted_at IS NULL
            """,
        )
        rows = await cur.fetchall()
        out = [dict(r) for r in rows]
    await _record_slow_query("list_orders_for_status_views", (time.perf_counter() - t0) * 1000.0)
    return out


async def count_active_queue_orders(guild_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            SELECT COUNT(*) FROM orders
            WHERE status IN ('Noted', 'Processing')
              AND deleted_at IS NULL
              AND ticket_channel_id IN (
                  SELECT channel_id FROM tickets
                  WHERE guild_id = ? AND deleted_at IS NULL
              )
            """,
            (guild_id,),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


# --- Tickets ---


_TICKET_UPDATEABLE: frozenset[str] = frozenset(
    {
        "quote_total_php",
        "quote_usd_approx",
        "quote_snapshot_json",
        "rendering_tier",
        "background",
        "char_count_key",
        "rush_addon",
        "ticket_status",
        "wip_stage",
        "revision_count",
        "revision_extra_fee_php",
        "references_json",
        "downpayment_confirmed",
        "active_hours_notified",
        "answers",
        "quote_expires_at",
        "quote_approved",
        "payment_status",
        "payment_proof_url",
        "close_approved_by_client",
        "close_approved_at",
        "assigned_staff_id",
        "last_client_remind_at",
    }
)


async def update_ticket_fields(channel_id: int, **fields: Any) -> None:
    if not fields:
        return
    existing_cols: set[str] = set()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("PRAGMA table_info(tickets)")
        existing_cols = {str(r[1]) for r in await cur.fetchall()}
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in _TICKET_UPDATEABLE:
            continue
        if k not in existing_cols:
            # Backward-safe: older local DB may miss newer ticket columns.
            continue
        if k == "answers" and isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return
    vals.append(channel_id)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE tickets SET {', '.join(sets)} WHERE channel_id = ?",
            vals,
        )
        await db.commit()


async def append_ticket_reference(channel_id: int, url: str) -> None:
    row = await get_ticket_by_channel(channel_id)
    if not row:
        return
    raw = row.get("references_json")
    try:
        links = json.loads(raw) if raw else []
        if not isinstance(links, list):
            links = []
    except json.JSONDecodeError:
        links = []
    links.append(url.strip())
    await update_ticket_fields(channel_id, references_json=json.dumps(links, ensure_ascii=False))


async def log_ticket_revision(channel_id: int) -> tuple[int, float, float]:
    """Increment revision count. Returns (new_count, fee_added_this_time, cumulative_extra_fee)."""
    row = await get_ticket_by_channel(channel_id)
    if not row:
        return 0, 0.0, 0.0
    n = int(row.get("revision_count") or 0) + 1
    fee_this = 200.0 if n > 2 else 0.0
    extra = float(row.get("revision_extra_fee_php") or 0.0) + fee_this
    await update_ticket_fields(
        channel_id, revision_count=n, revision_extra_fee_php=extra
    )
    return n, fee_this, extra


async def insert_ticket_open(
    channel_id: int,
    guild_id: int,
    client_id: int,
    *,
    button_id: str | None = None,
    answers: dict[str, Any] | None = None,
    quote_total_php: float | None = None,
    quote_usd_approx: float | None = None,
    quote_snapshot_json: str | None = None,
    rendering_tier: str | None = None,
    background: str | None = None,
    char_count_key: str | None = None,
    rush_addon: int = 0,
    ticket_status: str | None = None,
    quote_expires_at: str | None = None,
    quote_approved: int | None = None,
    payment_status: str | None = None,
    close_approved_by_client: int | None = None,
) -> None:
    now = _utc_now()
    ans_json = json.dumps(answers, ensure_ascii=False) if answers is not None else None
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
    extra: dict[str, Any] = {}
    if quote_total_php is not None:
        extra["quote_total_php"] = quote_total_php
    if quote_usd_approx is not None:
        extra["quote_usd_approx"] = quote_usd_approx
    if quote_snapshot_json is not None:
        extra["quote_snapshot_json"] = quote_snapshot_json
    if rendering_tier is not None:
        extra["rendering_tier"] = rendering_tier
    if background is not None:
        extra["background"] = background
    if char_count_key is not None:
        extra["char_count_key"] = char_count_key
    extra["rush_addon"] = rush_addon
    if ticket_status is not None:
        extra["ticket_status"] = ticket_status
    if quote_expires_at is not None:
        extra["quote_expires_at"] = quote_expires_at
    if quote_approved is not None:
        extra["quote_approved"] = int(quote_approved)
    if payment_status is not None:
        extra["payment_status"] = payment_status
    if close_approved_by_client is not None:
        extra["close_approved_by_client"] = int(close_approved_by_client)
    if extra:
        await update_ticket_fields(channel_id, **extra)


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


async def force_mark_ticket_close_approved(channel_id: int, approved_at_iso: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("PRAGMA table_info(tickets)")
        cols = {str(r[1]) for r in await cur.fetchall()}
        if "close_approved_by_client" not in cols:
            await db.execute(
                "ALTER TABLE tickets ADD COLUMN close_approved_by_client INTEGER DEFAULT 0"
            )
        if "close_approved_at" not in cols:
            await db.execute("ALTER TABLE tickets ADD COLUMN close_approved_at TEXT")
        await db.execute(
            """
            UPDATE tickets
            SET close_approved_by_client = 1, close_approved_at = ?
            WHERE channel_id = ?
            """,
            (approved_at_iso, channel_id),
        )
        await db.commit()


async def get_open_ticket_by_user(
    client_id: int, guild_id: int
) -> dict[str, Any] | None:
    """Open ticket for panel flow — excludes warn-appeal-only tickets so appeals don't block commissions."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                """
                SELECT * FROM tickets
                WHERE client_id = ? AND guild_id = ? AND closed_at IS NULL AND deleted_at IS NULL
                AND IFNULL(button_id, '') != 'warn_appeal'
                ORDER BY opened_at DESC LIMIT 1
                """,
                (client_id, guild_id),
            )
        except aiosqlite.OperationalError as e:
            # Backward-safe query for legacy DBs before deleted_at was added.
            if "no such column: deleted_at" not in str(e):
                raise
            cur = await db.execute(
                """
                SELECT * FROM tickets
                WHERE client_id = ? AND guild_id = ? AND closed_at IS NULL
                AND IFNULL(button_id, '') != 'warn_appeal'
                ORDER BY opened_at DESC LIMIT 1
                """,
                (client_id, guild_id),
            )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_open_warn_appeal_ticket(
    client_id: int, guild_id: int
) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM tickets
            WHERE client_id = ? AND guild_id = ? AND closed_at IS NULL AND deleted_at IS NULL
            AND button_id = 'warn_appeal'
            ORDER BY opened_at DESC LIMIT 1
            """,
            (client_id, guild_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_ticket_by_channel(channel_id: int) -> dict[str, Any] | None:
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tickets WHERE channel_id = ? AND closed_at IS NULL AND deleted_at IS NULL",
            (channel_id,),
        )
        row = await cur.fetchone()
        out = dict(row) if row else None
    await _record_slow_query("get_ticket_by_channel", (time.perf_counter() - t0) * 1000.0)
    return out


async def add_ticket_note(
    channel_id: int,
    guild_id: int,
    author_id: int,
    note: str,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO ticket_notes (channel_id, guild_id, author_id, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (channel_id, guild_id, author_id, note, _utc_now()),
        )
        await db.commit()
        return int(cur.lastrowid)


async def list_ticket_notes(channel_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM ticket_notes
            WHERE channel_id = ?
            ORDER BY note_id ASC
            """,
            (channel_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def list_open_tickets_for_staff(
    guild_id: int, staff_id: int | None = None
) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if staff_id is None:
            cur = await db.execute(
                """
                SELECT * FROM tickets
                WHERE guild_id = ? AND closed_at IS NULL AND deleted_at IS NULL
                ORDER BY opened_at DESC
                """,
                (guild_id,),
            )
        else:
            cur = await db.execute(
                """
                SELECT * FROM tickets
                WHERE guild_id = ? AND closed_at IS NULL AND deleted_at IS NULL
                  AND assigned_staff_id = ?
                ORDER BY opened_at DESC
                """,
                (guild_id, staff_id),
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


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
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE tickets SET deleted_at = ? WHERE channel_id = ?",
            (now, channel_id),
        )
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
    require_age_verified: int = 0,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO ticket_buttons (
                button_id, guild_id, label, emoji, color, category_id, form_fields, select_options,
                require_age_verified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                button_id,
                guild_id,
                label,
                emoji,
                color,
                category_id,
                form_fields,
                select_options,
                require_age_verified,
            ),
        )
        await db.commit()


async def set_ticket_button_require_age(button_id: str, require: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE ticket_buttons SET require_age_verified = ? WHERE button_id = ?",
            (1 if require else 0, button_id),
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
            "SELECT COUNT(*) FROM warns WHERE user_id = ? AND deleted_at IS NULL", (user_id,)
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def list_warns(user_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM warns WHERE user_id = ? AND deleted_at IS NULL ORDER BY warn_id ASC",
            (user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def delete_warn(warn_id: int) -> bool:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "UPDATE warns SET deleted_at = ? WHERE warn_id = ? AND deleted_at IS NULL",
            (now, warn_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def clear_warns_user(user_id: int) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "UPDATE warns SET deleted_at = ? WHERE user_id = ? AND deleted_at IS NULL",
            (now, user_id),
        )
        await db.commit()
        return cur.rowcount


async def get_warn(warn_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM warns WHERE warn_id = ? AND deleted_at IS NULL",
            (warn_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


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


async def insert_commission_review(
    *,
    guild_id: int,
    reviewer_id: int,
    order_id: str,
    overall_quality: int,
    communication: int,
    turnaround: int,
    process_smoothness: int,
    enjoyed_most: str,
    improvements: str,
    commission_again: str,
    recommend_friend: str,
    testimonial_consent: str,
    discount_code: str | None,
) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO commission_reviews (
                guild_id, reviewer_id, order_id,
                overall_quality, communication, turnaround, process_smoothness,
                enjoyed_most, improvements,
                commission_again, recommend_friend, testimonial_consent,
                discount_code, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(guild_id),
                int(reviewer_id),
                str(order_id),
                int(overall_quality),
                int(communication),
                int(turnaround),
                int(process_smoothness),
                (enjoyed_most or "")[:1500],
                (improvements or "")[:1500],
                str(commission_again)[:64],
                str(recommend_friend)[:32],
                str(testimonial_consent)[:128],
                str(discount_code)[:64] if discount_code else None,
                now,
            ),
        )
        await db.commit()
        pk = int(cur.lastrowid)
    await mark_order_review_submitted(str(order_id))
    return pk


async def mark_order_review_submitted(order_id: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                """
                UPDATE orders SET review_submitted = 1, updated_at = ?
                WHERE order_id = ? AND deleted_at IS NULL
                """,
                (_utc_now(), str(order_id)),
            )
            await db.commit()
        except aiosqlite.OperationalError as e:
            if "no such column: review_submitted" not in str(e):
                raise


async def has_commission_review(guild_id: int, reviewer_id: int, order_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            SELECT 1 FROM commission_reviews
            WHERE guild_id = ? AND reviewer_id = ? AND order_id = ?
            LIMIT 1
            """,
            (int(guild_id), int(reviewer_id), str(order_id)),
        )
        return await cur.fetchone() is not None


async def has_vouch_for_order(client_id: int, order_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            SELECT 1 FROM vouches
            WHERE client_id = ? AND order_id = ?
            LIMIT 1
            """,
            (int(client_id), str(order_id)),
        )
        return await cur.fetchone() is not None


async def resolve_order_for_client_vouch(
    guild_id: int, client_id: int, current_channel_id: int | None
) -> dict[str, Any] | None:
    """Prefer order tied to current ticket channel; else most recent order in this guild."""
    if current_channel_id is not None:
        row = await get_order_for_ticket_client(int(current_channel_id), int(client_id))
        if row:
            return row
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                """
                SELECT o.* FROM orders o
                INNER JOIN tickets t ON t.channel_id = o.ticket_channel_id
                WHERE o.client_id = ?
                  AND t.guild_id = ?
                  AND t.closed_at IS NULL AND t.deleted_at IS NULL
                  AND o.deleted_at IS NULL
                ORDER BY datetime(o.updated_at) DESC, datetime(o.created_at) DESC
                LIMIT 5
                """,
                (int(client_id), int(guild_id)),
            )
        except aiosqlite.OperationalError as e:
            if "no such column: o.deleted_at" not in str(e):
                raise
            cur = await db.execute(
                """
                SELECT o.* FROM orders o
                INNER JOIN tickets t ON t.channel_id = o.ticket_channel_id
                WHERE o.client_id = ?
                  AND t.guild_id = ?
                  AND t.closed_at IS NULL
                ORDER BY datetime(o.updated_at) DESC, datetime(o.created_at) DESC
                LIMIT 5
                """,
                (int(client_id), int(guild_id)),
            )
        rows = await cur.fetchall()
        out = [dict(r) for r in rows]
    await _record_slow_query(
        "resolve_order_for_client_vouch", (time.perf_counter() - t0) * 1000.0
    )
    return out[0] if out else None


async def list_orders_eligible_for_review(
    guild_id: int, client_id: int, limit: int = 25
) -> list[dict[str, Any]]:
    """Registered orders with a vouch, not yet reviewed (DB + commission_reviews)."""
    t0 = time.perf_counter()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cur = await db.execute(
                """
                SELECT o.* FROM orders o
                INNER JOIN tickets t ON t.channel_id = o.ticket_channel_id
                WHERE o.client_id = ?
                  AND t.guild_id = ?
                  AND t.deleted_at IS NULL
                  AND o.deleted_at IS NULL
                  AND IFNULL(o.review_submitted, 0) = 0
                  AND EXISTS (
                      SELECT 1 FROM vouches v
                      WHERE v.client_id = o.client_id AND v.order_id = o.order_id
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM commission_reviews r
                      WHERE r.guild_id = ? AND r.reviewer_id = ? AND r.order_id = o.order_id
                  )
                ORDER BY datetime(o.updated_at) DESC
                LIMIT ?
                """,
                (int(client_id), int(guild_id), int(guild_id), int(client_id), int(limit)),
            )
        except aiosqlite.OperationalError as e:
            err = str(e)
            if "no such column: o.review_submitted" in err or "no such column: o.deleted_at" in err:
                cur = await db.execute(
                    """
                    SELECT o.* FROM orders o
                    INNER JOIN tickets t ON t.channel_id = o.ticket_channel_id
                    WHERE o.client_id = ?
                      AND t.guild_id = ?
                      AND EXISTS (
                          SELECT 1 FROM vouches v
                          WHERE v.client_id = o.client_id AND v.order_id = o.order_id
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM commission_reviews r
                          WHERE r.guild_id = ? AND r.reviewer_id = ? AND r.order_id = o.order_id
                      )
                    ORDER BY datetime(o.updated_at) DESC
                    LIMIT ?
                    """,
                    (int(client_id), int(guild_id), int(guild_id), int(client_id), int(limit)),
                )
            else:
                raise
        rows = await cur.fetchall()
        out = [dict(r) for r in rows]
    await _record_slow_query(
        "list_orders_eligible_for_review", (time.perf_counter() - t0) * 1000.0
    )
    return out


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


async def get_current_tos_version() -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT current_version FROM tos_meta WHERE id = 1")
        row = await cur.fetchone()
        return int(row[0]) if row else 1


async def set_current_tos_version(version: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO tos_meta (id, current_version) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET current_version = excluded.current_version
            """,
            (int(version),),
        )
        await db.commit()


async def get_user_tos_version(user_id: int) -> int | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT tos_version FROM tos_agreements WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return int(row[0])


async def has_current_tos_agreement(user_id: int) -> bool:
    cur_ver = await get_current_tos_version()
    user_ver = await get_user_tos_version(user_id)
    return user_ver == cur_ver


async def log_tos_agreement(user_id: int, tos_version: int | None = None) -> None:
    now = _utc_now()
    if tos_version is None:
        tos_version = await get_current_tos_version()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO tos_agreements (user_id, agreed_at, tos_version) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                agreed_at = excluded.agreed_at,
                tos_version = excluded.tos_version
            """,
            (user_id, now, int(tos_version)),
        )
        await db.commit()


async def tos_stats() -> dict[str, Any]:
    cur_ver = await get_current_tos_version()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM tos_agreements")
        total = int((await cur.fetchone() or [0])[0])
        cur = await db.execute(
            "SELECT COUNT(*) FROM tos_agreements WHERE tos_version = ?",
            (cur_ver,),
        )
        current = int((await cur.fetchone() or [0])[0])
        cur = await db.execute(
            "SELECT COUNT(*) FROM tos_agreements WHERE tos_version != ?",
            (cur_ver,),
        )
        outdated = int((await cur.fetchone() or [0])[0])
        cur = await db.execute(
            "SELECT user_id, agreed_at FROM tos_agreements ORDER BY agreed_at DESC LIMIT 1"
        )
        row = await cur.fetchone()
        last_user = int(row[0]) if row else None
        last_at = str(row[1]) if row else None
        cur = await db.execute(
            "SELECT COUNT(*) FROM tos_agreements WHERE agreed_at >= ?",
            ((datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),),
        )
        week = int((await cur.fetchone() or [0])[0])
    return {
        "version": cur_ver,
        "total": total,
        "current": current,
        "outdated": outdated,
        "last_user": last_user,
        "last_at": last_at,
        "week": week,
    }


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


async def set_shop_state(is_open: bool, toggled_by: int | None, close_reason: str | None = None) -> None:
    now = _utc_now()
    flag = 1 if is_open else 0
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("SELECT id FROM shop_state WHERE id = 1")
        exists = await cur.fetchone()
        if exists:
            await db.execute(
                """
                UPDATE shop_state SET is_open = ?, last_toggled = ?, toggled_by = ?, close_reason = ?
                WHERE id = 1
                """,
                (flag, now, toggled_by, close_reason if not is_open else None),
            )
        else:
            await db.execute(
                """
                INSERT INTO shop_state (id, is_open, last_toggled, toggled_by, close_reason)
                VALUES (1, ?, ?, ?, ?)
                """,
                (flag, now, toggled_by, close_reason if not is_open else None),
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
                footer = ?, thumbnail_url = ?, paused = ?, cooldown_seconds = ?, last_repost_at = ?, updated_at = ?
            WHERE channel_id = ?
            """,
            (
                fields.get("title"),
                fields.get("description"),
                fields.get("color") or "#242429",
                fields.get("image_url"),
                fields.get("footer"),
                fields.get("thumbnail_url"),
                int(fields.get("paused") or 0),
                int(fields.get("cooldown_seconds") or 2),
                fields.get("last_repost_at"),
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
        cur = await db.execute("SELECT channel_id FROM sticky_messages WHERE IFNULL(paused,0)=0")
        rows = await cur.fetchall()
        return [int(r[0]) for r in rows]


async def set_sticky_pause(channel_id: int, paused: bool) -> bool:
    row = await get_sticky(channel_id)
    if not row:
        return False
    return await patch_sticky(channel_id, {"paused": 1 if paused else 0})


async def set_sticky_cooldown(channel_id: int, seconds: int) -> bool:
    row = await get_sticky(channel_id)
    if not row:
        return False
    return await patch_sticky(channel_id, {"cooldown_seconds": max(1, int(seconds))})


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


# --- DB backup schedules ---


async def upsert_db_backup_schedule(
    owner_user_id: int, hour_utc: int, minute_utc: int, enabled: bool
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO db_backup_schedule (owner_user_id, hour_utc, minute_utc, enabled, last_sent_date)
            VALUES (?, ?, ?, ?, NULL)
            ON CONFLICT(owner_user_id) DO UPDATE SET
                hour_utc = excluded.hour_utc,
                minute_utc = excluded.minute_utc,
                enabled = excluded.enabled
            """,
            (owner_user_id, hour_utc, minute_utc, 1 if enabled else 0),
        )
        await db.commit()


async def disable_db_backup_schedule(owner_user_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE db_backup_schedule SET enabled = 0 WHERE owner_user_id = ?",
            (owner_user_id,),
        )
        await db.commit()


async def list_due_db_backup_schedules(hour_utc: int, minute_utc: int) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).date().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM db_backup_schedule
            WHERE enabled = 1
              AND hour_utc = ?
              AND minute_utc = ?
              AND (last_sent_date IS NULL OR last_sent_date != ?)
            """,
            (hour_utc, minute_utc, today),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def mark_db_backup_schedule_sent(owner_user_id: int) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE db_backup_schedule SET last_sent_date = ? WHERE owner_user_id = ?",
            (today, owner_user_id),
        )
        await db.commit()


async def list_recent_slow_queries(limit: int = 10) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT query_name, elapsed_ms, created_at
            FROM slow_query_events
            ORDER BY elapsed_ms DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# --- Embed builder ---


async def list_embed_staff_roles(guild_id: int) -> list[int]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "SELECT role_id FROM embed_builder_staff_roles WHERE guild_id = ? ORDER BY role_id",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [int(r[0]) for r in rows]


async def add_embed_staff_role(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO embed_builder_staff_roles (guild_id, role_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, role_id) DO NOTHING
            """,
            (guild_id, role_id, _utc_now()),
        )
        await db.commit()


async def remove_embed_staff_role(guild_id: int, role_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM embed_builder_staff_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await db.commit()


async def create_builder_embed(guild_id: int, created_by: int) -> dict[str, Any]:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO embed_builder_meta (guild_id, last_assigned_id) VALUES (?, 0) ON CONFLICT(guild_id) DO NOTHING",
            (guild_id,),
        )
        cur = await db.execute(
            "SELECT last_assigned_id FROM embed_builder_meta WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        nxt = int(row[0]) + 1 if row else 1
        embed_id = f"EMB-{nxt:03d}"
        await db.execute(
            "UPDATE embed_builder_meta SET last_assigned_id = ? WHERE guild_id = ?",
            (nxt, guild_id),
        )
        await db.execute(
            """
            INSERT INTO embed_builder_embeds (
                guild_id, embed_id, created_by, created_at, last_edited_at, status, color, ts_enabled
            ) VALUES (?, ?, ?, ?, ?, 'draft', '#5865F2', 0)
            """,
            (guild_id, embed_id, created_by, now, now),
        )
        await db.commit()
    return await get_builder_embed(guild_id, embed_id) or {}


async def get_builder_embed(guild_id: int, embed_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM embed_builder_embeds WHERE guild_id = ? AND embed_id = ?",
            (guild_id, embed_id.upper()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_builder_embeds(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM embed_builder_embeds WHERE guild_id = ? ORDER BY embed_id ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def patch_builder_embed(guild_id: int, embed_id: str, updates: dict[str, Any]) -> bool:
    row = await get_builder_embed(guild_id, embed_id)
    if not row:
        return False
    allowed = {
        "author_text",
        "author_icon",
        "title",
        "description",
        "footer_text",
        "footer_icon",
        "thumbnail_url",
        "image_url",
        "color",
        "ts_enabled",
        "status",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return True
    fields["last_edited_at"] = _utc_now()
    set_sql = ", ".join(f"{k} = ?" for k in fields.keys())
    vals = list(fields.values()) + [guild_id, embed_id.upper()]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE embed_builder_embeds SET {set_sql} WHERE guild_id = ? AND embed_id = ?",
            vals,
        )
        await db.commit()
    return True


async def delete_builder_embed(guild_id: int, embed_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "DELETE FROM embed_builder_embeds WHERE guild_id = ? AND embed_id = ?",
            (guild_id, embed_id.upper()),
        )
        await db.commit()
        return int(cur.rowcount or 0) > 0


async def log_embed_builder_action(
    guild_id: int,
    actor_user_id: int,
    action: str,
    embed_id: str,
    channel_id: int | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO embed_builder_audit (guild_id, actor_user_id, action, embed_id, channel_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (guild_id, actor_user_id, action[:32], embed_id.upper(), channel_id, _utc_now()),
        )
        await db.commit()


# --- Button builder (BTN-XXX) ---


async def create_builder_button(guild_id: int, created_by: int) -> dict[str, Any]:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO button_builder_meta (guild_id, last_assigned_id) VALUES (?, 0) ON CONFLICT(guild_id) DO NOTHING",
            (guild_id,),
        )
        cur = await db.execute(
            "SELECT last_assigned_id FROM button_builder_meta WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        nxt = int(row[0]) + 1 if row else 1
        button_id = f"BTN-{nxt:03d}"
        await db.execute(
            "UPDATE button_builder_meta SET last_assigned_id = ? WHERE guild_id = ?",
            (nxt, guild_id),
        )
        await db.execute(
            """
            INSERT INTO button_builder_buttons (
                guild_id, button_id, created_by, created_at, last_edited_at, status,
                label, style, action_type
            ) VALUES (?, ?, ?, ?, ?, 'draft', 'Button', 'secondary', 'toggle_role')
            """,
            (guild_id, button_id, created_by, now, now),
        )
        await db.commit()
    return await get_builder_button(guild_id, button_id) or {}


async def get_builder_button(guild_id: int, button_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM button_builder_buttons WHERE guild_id = ? AND button_id = ?",
            (guild_id, button_id.upper()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_builder_buttons(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM button_builder_buttons WHERE guild_id = ? ORDER BY button_id ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def patch_builder_button(guild_id: int, button_id: str, updates: dict[str, Any]) -> bool:
    row = await get_builder_button(guild_id, button_id)
    if not row:
        return False
    allowed = {
        "label",
        "emoji_str",
        "style",
        "action_type",
        "role_id",
        "internal_label",
        "internal_note",
        "responses_json",
        "status",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return True
    fields["last_edited_at"] = _utc_now()
    set_sql = ", ".join(f"{k} = ?" for k in fields.keys())
    vals = list(fields.values()) + [guild_id, button_id.upper()]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE button_builder_buttons SET {set_sql} WHERE guild_id = ? AND button_id = ?",
            vals,
        )
        await db.commit()
    return True


async def delete_builder_button(guild_id: int, button_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "DELETE FROM button_builder_buttons WHERE guild_id = ? AND button_id = ?",
            (guild_id, button_id.upper()),
        )
        await db.commit()
        return int(cur.rowcount or 0) > 0


async def clone_builder_button(guild_id: int, button_id: str, created_by: int) -> dict[str, Any] | None:
    src = await get_builder_button(guild_id, button_id)
    if not src:
        return None
    new_row = await create_builder_button(guild_id, created_by)
    if not new_row:
        return None
    await patch_builder_button(
        guild_id,
        str(new_row["button_id"]),
        {
            "label": src.get("label"),
            "emoji_str": src.get("emoji_str"),
            "style": src.get("style") or "secondary",
            "action_type": src.get("action_type") or "toggle_role",
            "role_id": src.get("role_id"),
            "internal_label": src.get("internal_label"),
            "internal_note": src.get("internal_note"),
            "responses_json": src.get("responses_json"),
            "status": "draft",
        },
    )
    return await get_builder_button(guild_id, str(new_row["button_id"]))


async def log_button_builder_action(
    guild_id: int,
    actor_user_id: int,
    action: str,
    bid: str,
    channel_id: int | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO button_builder_audit (guild_id, actor_user_id, action, button_id, channel_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (guild_id, actor_user_id, action[:32], bid.upper(), channel_id, _utc_now()),
        )
        await db.commit()


# --- Autoresponder builder (AR-XXX) ---


async def create_autoresponder(guild_id: int, created_by: int) -> dict[str, Any]:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO ar_builder_meta (guild_id, last_assigned_id) VALUES (?, 0) ON CONFLICT(guild_id) DO NOTHING",
            (guild_id,),
        )
        cur = await db.execute(
            "SELECT last_assigned_id FROM ar_builder_meta WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        nxt = int(row[0]) + 1 if row else 1
        ar_id = f"AR-{nxt:03d}"
        await db.execute(
            "UPDATE ar_builder_meta SET last_assigned_id = ? WHERE guild_id = ?",
            (nxt, guild_id),
        )
        await db.execute(
            """
            INSERT INTO ar_builder_entries (
                guild_id, ar_id, created_by, created_at, last_edited_at, status,
                trigger_type, match_mode, triggers_json, response_text, priority, cooldown_seconds
            ) VALUES (?, ?, ?, ?, ?, 'draft', 'message', 'exact', '', NULL, 100, 0)
            """,
            (guild_id, ar_id, created_by, now, now),
        )
        await db.commit()
    return await get_autoresponder(guild_id, ar_id) or {}


async def get_autoresponder(guild_id: int, ar_id: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ar_builder_entries WHERE guild_id = ? AND ar_id = ?",
            (guild_id, ar_id.upper()),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_autoresponders(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ar_builder_entries WHERE guild_id = ? ORDER BY ar_id ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def list_active_autoresponders(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM ar_builder_entries WHERE guild_id = ? AND status = 'active' ORDER BY priority ASC, ar_id ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def patch_autoresponder(guild_id: int, ar_id: str, updates: dict[str, Any]) -> bool:
    row = await get_autoresponder(guild_id, ar_id)
    if not row:
        return False
    allowed = {
        "status",
        "trigger_type",
        "match_mode",
        "triggers_json",
        "response_text",
        "priority",
        "cooldown_seconds",
        "required_role_id",
        "denied_role_id",
        "required_channel_id",
        "denied_channel_id",
        "trigger_role_id",
        "trigger_channel_id",
        "trigger_message_id",
        "trigger_emoji",
        "internal_label",
        "internal_note",
    }
    fields = {k: v for k, v in updates.items() if k in allowed}
    if not fields:
        return True
    fields["last_edited_at"] = _utc_now()
    set_sql = ", ".join(f"{k} = ?" for k in fields.keys())
    vals = list(fields.values()) + [guild_id, ar_id.upper()]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE ar_builder_entries SET {set_sql} WHERE guild_id = ? AND ar_id = ?",
            vals,
        )
        await db.commit()
    return True


async def delete_autoresponder(guild_id: int, ar_id: str) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM ar_builder_user_cooldowns WHERE guild_id = ? AND ar_id = ?",
            (guild_id, ar_id.upper()),
        )
        cur = await db.execute(
            "DELETE FROM ar_builder_entries WHERE guild_id = ? AND ar_id = ?",
            (guild_id, ar_id.upper()),
        )
        await db.commit()
        return int(cur.rowcount or 0) > 0


async def get_autoresponder_last_fire(guild_id: int, ar_id: str, user_id: int) -> int | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            SELECT last_fired_ts FROM ar_builder_user_cooldowns
            WHERE guild_id = ? AND ar_id = ? AND user_id = ?
            """,
            (guild_id, ar_id.upper(), user_id),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else None


async def bump_autoresponder_fire_count(guild_id: int, ar_id: str, user_id: int) -> None:
    now = _utc_now()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE ar_builder_entries
            SET fire_count = fire_count + 1, last_fired_at = ?
            WHERE guild_id = ? AND ar_id = ?
            """,
            (now, guild_id, ar_id.upper()),
        )
        await db.execute(
            """
            INSERT INTO ar_builder_user_cooldowns (guild_id, ar_id, user_id, last_fired_ts)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, ar_id, user_id) DO UPDATE SET last_fired_ts = excluded.last_fired_ts
            """,
            (guild_id, ar_id.upper(), user_id, now_ts),
        )
        await db.commit()


async def log_autoresponder_action(
    guild_id: int,
    actor_user_id: int,
    action: str,
    ar_id: str,
    channel_id: int | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO ar_builder_audit (guild_id, actor_user_id, action, ar_id, channel_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (guild_id, actor_user_id, action[:32], ar_id.upper(), channel_id, _utc_now()),
        )
        await db.commit()


async def search_autoresponders(
    guild_id: int,
    *,
    query: str | None = None,
    status: str | None = None,
    creator_id: int | None = None,
) -> list[dict[str, Any]]:
    base = "SELECT * FROM ar_builder_entries WHERE guild_id = ?"
    params: list[Any] = [guild_id]
    if status:
        base += " AND status = ?"
        params.append(status)
    if creator_id:
        base += " AND created_by = ?"
        params.append(int(creator_id))
    if query and query.strip():
        q = f"%{query.strip()}%"
        base += " AND (ar_id LIKE ? OR triggers_json LIKE ? OR COALESCE(internal_label, '') LIKE ?)"
        params.extend([q, q, q])
    base += " ORDER BY ar_id ASC"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(base, tuple(params))
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_autoresponder_stats(guild_id: int, ar_id: str) -> dict[str, Any] | None:
    row = await get_autoresponder(guild_id, ar_id)
    if not row:
        return None
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            SELECT COUNT(*) FROM ar_builder_user_cooldowns
            WHERE guild_id = ? AND ar_id = ?
            """,
            (guild_id, ar_id.upper()),
        )
        unique_users_row = await cur.fetchone()
        unique_users = int(unique_users_row[0]) if unique_users_row else 0
        cur2 = await db.execute(
            """
            SELECT actor_user_id, created_at FROM ar_builder_audit
            WHERE guild_id = ? AND ar_id = ? AND action = 'fire'
            ORDER BY id DESC LIMIT 1
            """,
            (guild_id, ar_id.upper()),
        )
        last_fire = await cur2.fetchone()
    return {
        "ar_id": row["ar_id"],
        "fire_count": int(row.get("fire_count") or 0),
        "unique_users": unique_users,
        "last_fired_at": row.get("last_fired_at"),
        "last_actor_user_id": int(last_fire[0]) if last_fire else None,
        "status": row.get("status"),
    }


# --- Loyalty stamp cards (LC-###) ---


async def allocate_loyalty_card_number(guild_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO loyalty_card_meta (guild_id, next_seq, recycled_json)
            VALUES (?, 0, '[]')
            """,
            (guild_id,),
        )
        cur = await db.execute(
            "SELECT next_seq, recycled_json FROM loyalty_card_meta WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        if not row:
            return 1
        nxt = int(row[0])
        recycled: list[int] = []
        try:
            recycled = json.loads(row[1] or "[]")
        except json.JSONDecodeError:
            recycled = []
        if recycled:
            num = min(recycled)
            recycled.remove(num)
            await db.execute(
                "UPDATE loyalty_card_meta SET recycled_json = ? WHERE guild_id = ?",
                (json.dumps(recycled), guild_id),
            )
            await db.commit()
            return int(num)
        num = nxt + 1
        await db.execute(
            "UPDATE loyalty_card_meta SET next_seq = ? WHERE guild_id = ?",
            (num, guild_id),
        )
        await db.commit()
        return int(num)


async def recycle_loyalty_card_number(guild_id: int, n: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO loyalty_card_meta (guild_id, next_seq, recycled_json)
            VALUES (?, 0, '[]')
            """,
            (guild_id,),
        )
        cur = await db.execute(
            "SELECT recycled_json FROM loyalty_card_meta WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cur.fetchone()
        pool: list[int] = []
        if row:
            try:
                pool = json.loads(row[0] or "[]")
            except json.JSONDecodeError:
                pool = []
        if int(n) not in pool:
            pool.append(int(n))
            pool.sort()
        await db.execute(
            "UPDATE loyalty_card_meta SET recycled_json = ? WHERE guild_id = ?",
            (json.dumps(pool), guild_id),
        )
        await db.commit()


async def upsert_loyalty_card_image(
    guild_id: int, stamp_index: int, image_url: str
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO loyalty_card_images (guild_id, stamp_index, image_url)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, stamp_index) DO UPDATE SET image_url = excluded.image_url
            """,
            (guild_id, int(stamp_index), image_url[:2000]),
        )
        await db.commit()


async def delete_loyalty_card_image(guild_id: int, stamp_index: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM loyalty_card_images WHERE guild_id = ? AND stamp_index = ?",
            (guild_id, int(stamp_index)),
        )
        await db.commit()


async def list_loyalty_card_images(guild_id: int) -> dict[int, str]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            SELECT stamp_index, image_url FROM loyalty_card_images
            WHERE guild_id = ? ORDER BY stamp_index ASC
            """,
            (guild_id,),
        )
        rows = await cur.fetchall()
        return {int(r[0]): str(r[1]) for r in rows}


async def loyalty_card_max_stamp_index(guild_id: int) -> int | None:
    imgs = await list_loyalty_card_images(guild_id)
    if not imgs:
        return None
    return max(imgs.keys())


async def insert_loyalty_card(
    guild_id: int,
    *,
    card_number: int,
    user_id: int,
    stamp_count: int,
    message_id: int | None,
    thread_id: int | None,
    channel_id: int,
    ticket_channel_id: int | None,
    void_deadline_ts: int | None,
) -> int:
    now = _utc_now()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO loyalty_cards (
                guild_id, card_number, user_id, stamp_count, status,
                message_id, thread_id, channel_id, ticket_channel_id,
                created_at, void_deadline_ts, first_vouch_ts
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                guild_id,
                int(card_number),
                int(user_id),
                int(stamp_count),
                message_id,
                thread_id,
                int(channel_id),
                ticket_channel_id,
                now,
                void_deadline_ts,
            ),
        )
        await db.commit()
        return int(cur.lastrowid)


async def patch_loyalty_card(card_pk: int, updates: dict[str, Any]) -> None:
    allowed = {
        "stamp_count",
        "message_id",
        "thread_id",
        "void_deadline_ts",
        "status",
        "first_vouch_ts",
    }
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in updates.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = ?")
        if k == "status":
            vals.append(str(v)[:24])
        elif k == "void_deadline_ts":
            vals.append(v)
        elif k == "first_vouch_ts":
            vals.append(int(v) if v is not None else None)
        else:
            vals.append(int(v) if v is not None else None)
    if not sets:
        return
    vals.append(int(card_pk))
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE loyalty_cards SET {', '.join(sets)} WHERE id = ?",
            tuple(vals),
        )
        await db.commit()


async def get_loyalty_card_by_id(card_pk: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM loyalty_cards WHERE id = ?", (card_pk,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_active_loyalty_cards_for_user(
    guild_id: int, user_id: int
) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM loyalty_cards
            WHERE guild_id = ? AND user_id = ? AND status = 'active'
            ORDER BY id DESC
            """,
            (guild_id, int(user_id)),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def list_loyalty_cards_active_or_pending_void(guild_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM loyalty_cards
            WHERE guild_id = ? AND status = 'active'
            ORDER BY card_number ASC
            """,
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def delete_loyalty_card_row(card_pk: int) -> dict[str, Any] | None:
    row = await get_loyalty_card_by_id(card_pk)
    if not row:
        return None
    gid = int(row["guild_id"])
    cnum = int(row["card_number"])
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM loyalty_cards WHERE id = ?", (card_pk,))
        await db.commit()
    await recycle_loyalty_card_number(gid, cnum)
    return row


async def void_loyalty_card(card_pk: int, status: str = "voided") -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            "UPDATE loyalty_cards SET status = ? WHERE id = ? AND status = 'active'",
            (status[:24], int(card_pk)),
        )
        await db.commit()
        return int(cur.rowcount or 0) > 0


async def list_loyalty_cards_due_void(now_ts: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM loyalty_cards
            WHERE status = 'active'
              AND void_deadline_ts IS NOT NULL
              AND void_deadline_ts < ?
              AND stamp_count = 0
            """,
            (int(now_ts),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
