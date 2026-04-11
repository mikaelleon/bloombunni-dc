"""Database keys for per-guild channel/role mappings (set via /serverconfig)."""

from __future__ import annotations

# Roles
STAFF_ROLE = "staff_role"
TOS_AGREED_ROLE = "tos_agreed_role"
COMMISSIONS_OPEN_ROLE = "commissions_open_role"
PLEASE_VOUCH_ROLE = "please_vouch_role"

# Categories
TICKET_CATEGORY = "ticket_category"
NOTED_CATEGORY = "noted_category"
PROCESSING_CATEGORY = "processing_category"
DONE_CATEGORY = "done_category"

# Text / announcement channels
QUEUE_CHANNEL = "queue_channel"
SHOP_STATUS_CHANNEL = "shop_status_channel"
TRANSCRIPT_CHANNEL = "transcript_channel"
VOUCHES_CHANNEL = "vouches_channel"
ORDER_NOTIFS_CHANNEL = "order_notifs_channel"
START_HERE_CHANNEL = "start_here_channel"
TOS_CHANNEL = "tos_channel"
PAYMENT_CHANNEL = "payment_channel"
WARN_LOG_CHANNEL = "warn_log_channel"

CHANNEL_SLOT_CHOICES: list[tuple[str, str]] = [
    ("Queue (order list)", QUEUE_CHANNEL),
    ("Shop status embed", SHOP_STATUS_CHANNEL),
    ("Transcript archive", TRANSCRIPT_CHANNEL),
    ("Vouches", VOUCHES_CHANNEL),
    ("Order notifications (optional)", ORDER_NOTIFS_CHANNEL),
    ("Start Here (ticket panel)", START_HERE_CHANNEL),
    ("TOS text channel", TOS_CHANNEL),
    ("Payment panel", PAYMENT_CHANNEL),
    ("Warn log", WARN_LOG_CHANNEL),
]

CATEGORY_SLOT_CHOICES: list[tuple[str, str]] = [
    ("New tickets", TICKET_CATEGORY),
    ("Noted orders", NOTED_CATEGORY),
    ("Processing", PROCESSING_CATEGORY),
    ("Done", DONE_CATEGORY),
]

ROLE_SLOT_CHOICES: list[tuple[str, str]] = [
    ("Staff", STAFF_ROLE),
    ("TOS agreed", TOS_AGREED_ROLE),
    ("Commissions open", COMMISSIONS_OPEN_ROLE),
    ("Please vouch", PLEASE_VOUCH_ROLE),
]

# Payment panel (string settings via /serverconfig payment …)
PAYMENT_GCASH_DETAILS = "payment_gcash_details"
PAYMENT_PAYPAL_LINK = "payment_paypal_link"
PAYMENT_KOFI_LINK = "payment_kofi_link"
PAYMENT_GCASH_QR_URL = "payment_gcash_qr_url"
PAYMENT_PAYPAL_QR_URL = "payment_paypal_qr_url"

PAYMENT_FIELD_LABELS: dict[str, str] = {
    PAYMENT_GCASH_DETAILS: "GCash instructions (body text)",
    PAYMENT_PAYPAL_LINK: "PayPal URL",
    PAYMENT_KOFI_LINK: "Ko-fi URL",
    PAYMENT_GCASH_QR_URL: "GCash QR image URL",
    PAYMENT_PAYPAL_QR_URL: "PayPal QR image URL",
}

PAYMENT_ALL_KEYS: tuple[str, ...] = (
    PAYMENT_GCASH_DETAILS,
    PAYMENT_PAYPAL_LINK,
    PAYMENT_KOFI_LINK,
    PAYMENT_GCASH_QR_URL,
    PAYMENT_PAYPAL_QR_URL,
)
