# Bot documentation index

Technical reference for the **Mika Shop** Discord bot (code under `bot/`). Operator setup is also summarized in the project [`README.md`](../README.md) if present.

## Table of contents

- [Core runtime](#core-runtime)
- [Configuration and setup](#configuration-and-setup)
- [Feature modules](#feature-modules)
- [Data reference](#data-reference)

## Core runtime

| Document | Scope |
|----------|--------|
| [overview-and-core.md](overview-and-core.md) | Intents, `setup_hook`, slash sync, `on_ready`, errors, embed palette |

## Configuration and setup

| [config.md](config.md) | `/config view`, `/config reset`, `/config payment` |
| [setup-wizard.md](setup-wizard.md) | `/setup`, `/setup_resume` |

## Feature modules

| [quotes-and-pricing.md](quotes-and-pricing.md) | `/quote`, `/pricelist`, `/setprice`, …, `quote_compute` |
| [tickets-and-panels.md](tickets-and-panels.md) | `/ticketpanel`, `/ticketbutton`, `/ticketform`, `/deploy`, ticket flow, `/payment`, `/stage`, `/close` |
| [queue-templates-loyalty.md](queue-templates-loyalty.md) | `/queue`, order dropdown, templates, `/loyalty`, `/setorderprefix` |
| [shop-status-tos.md](shop-status-tos.md) | `/shop`, `/shopstatus`, TOS button panel |
| [payment-panel.md](payment-panel.md) | `/deploy payment`, `PaymentView` buttons |
| [vouches.md](vouches.md) | Vouch channel listener, `/vouch`, `/vouches` |
| [warnings.md](warnings.md) | `/warn`, `/warnreason`, warn log audit, appeal tickets, threshold, auto-ban |
| [stickies.md](stickies.md) | Sticky repost behavior and commands |
| [drops.md](drops.md) | `/drop`, `/drophistory`, completion DM |
| [owner-tools.md](owner-tools.md) | `/purge_bot_dms` |

## Data reference

| [database-reference.md](database-reference.md) | SQLite tables and keys overview |
