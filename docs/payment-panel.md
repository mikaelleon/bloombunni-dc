# Payment panel (`cogs/payment.py`)

## Deployment

**`/deploy payment`** (from **Tickets** cog) resolves a text channel, sets **`PAYMENT_CHANNEL`**, then calls **`PaymentCog.run_setup_payment`**.

- **`is_payment_config_complete`** must be true — **all** keys in `gk.PAYMENT_ALL_KEYS` need non-empty values (see [config.md](config.md)).
- Posts to the channel:

**Embed**

- Title: **`Mode of Payment`**
- Description: **`Choose a method below for details (ephemeral).`**
- Color: **`PRIMARY`** (`utils/embeds`)

**View:** **`PaymentView`** (registered once in **`setup_hook`**).

**Invoker** receives ephemeral **`success_embed("Posted", "Payment panel deployed.")`**

## `PaymentView` buttons

| Button | `custom_id` | Ephemeral reply |
|--------|-------------|-----------------|
| **GCash** | `pay_gcash` | Requires **`payment_gcash_details`** + **`payment_gcash_qr_url`**. Embed title **GCash**, description = details text, **`set_image`** with QR URL. Color **PRIMARY**. |
| **PayPal** | `pay_paypal` | Requires **`payment_paypal_link`** + **`payment_paypal_qr_url`**. Embed **PayPal** with `[PayPal link](url)` in description + QR image. |
| **Ko-fi** | `pay_kofi` | Requires **`payment_kofi_link`** only. Embed **Ko-fi** with `[Ko-fi](url)`. |

If configuration missing: **`user_hint("Payment not set up yet", …)`** with the relevant **`/config payment`** subcommand names.

**Note:** `/deploy` validation requires **all** payment strings including QR URLs; runtime button handlers use subsets as above.

## Persistence

**`db.set_persist_panel("payment", channel_id, message_id)`** stores the panel location (used for operational tracking; views are re-registered globally via **`add_view(PaymentView())`**).
