# Bot documentation index

Technical reference for the **Mika Shop** Discord bot (code under `bot/`). Operator setup is also summarized in the project [`README.md`](../README.md) if present.

| Document | Scope |
|----------|--------|
| [overview-and-core.md](overview-and-core.md) | Intents, `setup_hook`, slash sync, `on_ready`, errors, embed palette |
| [config.md](config.md) | `/config view`, `/config reset`, `/config payment` |
| [setup-wizard.md](setup-wizard.md) | `/setup`, `/setup_resume` |
| [quotes-and-pricing.md](quotes-and-pricing.md) | `/quote`, `/pricelist`, `/setprice`, …, `quote_compute` |
| [tickets-and-panels.md](tickets-and-panels.md) | `/ticketpanel`, `/ticketbutton`, `/ticketform`, `/deploy`, ticket flow, `/payment`, `/stage`, `/close` |
| [queue-templates-loyalty.md](queue-templates-loyalty.md) | `/queue`, order dropdown, templates, `/loyalty`, `/setorderprefix` |
| [shop-status-tos.md](shop-status-tos.md) | `/shop`, `/shopstatus`, TOS button panel |
| [payment-panel.md](payment-panel.md) | `/deploy payment`, `PaymentView` buttons |
| [vouches.md](vouches.md) | Vouch channel listener, `/vouch`, `/vouches` |
| [warnings.md](warnings.md) | `/warn`, `/warns`, threshold, auto-ban |
| [stickies.md](stickies.md) | Sticky repost behavior and commands |
| [drops.md](drops.md) | `/drop`, `/drophistory`, completion DM |
| [owner-tools.md](owner-tools.md) | `/purge_bot_dms` |
| [database-reference.md](database-reference.md) | SQLite tables and keys overview |

**Legacy note:** [TICKETING.md](TICKETING.md) is an older narrative; it may mention removed commands like `/serverconfig`. Prefer **tickets-and-panels.md** and **config.md** for current behavior.
