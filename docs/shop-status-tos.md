# Shop status and TOS (`cogs/shop.py`)

## `/shop` (group)

| Subcommand | Behavior |
|------------|----------|
| **`open`** | **`db.set_shop_state(True, user)`**. Edits or creates **shop status** embed in **`SHOP_STATUS_CHANNEL`** (`_apply_status_embed`). If **Start here** + roles configured: hides **Start here** from `@everyone`, shows it to **TOS agreed** and **Commissions open** roles. Ephemeral **`success_embed("Shop", "Commissions are now **open**.")`** |
| **`close`** | Sets shop closed; inverse permission tweaks on **Start here**; status embed **🔴 Commissions CLOSED**. |

**Status embed (`_embed`):**

- Open: title **`✅ Commissions OPEN`**, green (`SUCCESS`), body shows last toggled time + moderator mention.
- Closed: title **`🔴 Commissions CLOSED`**, red (`DANGER` / `EMBED_ACCENT_RED`).

Panel message pointer stored in **`persist_panels`** key **`shop_status`**.

## `/shopstatus`

Anyone — ephemeral **`info_embed("Shop status", "✅ **Open**" | "🔴 **Closed**")`** from **`shop_state`** table.

## TOS panel (`TOSAgreeView`)

- Registered in **`setup_hook`** with **`bot.add_view(TOSAgreeView())`**.
- Button: **`I Have Read & Agree to the TOS`** (`custom_id="tos_agree"`).
- On click: requires **`TOS_AGREED_ROLE`** mapping; adds role; **`log_tos_agreement`**; ephemeral **"✅ You've agreed! You can now open a commission ticket."**

## `/deploy tos` (see tickets doc)

**`run_setup_tos`:** reads **`config.TOS_FILE`** (`tos.txt`) into embed **`Terms of Service`** (color **`DANGER`**), posts with **`TOSAgreeView`**, saves **`persist_panels`** key **`tos`**.

## Gate checks

Opening a ticket from the panel requires **TOS agreed role** and **`db.shop_is_open_db()`** — see [tickets-and-panels.md](tickets-and-panels.md).
