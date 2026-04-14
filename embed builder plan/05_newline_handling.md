# Feature 05 — Newline Handling

**Priority:** 🟠 Medium (UX fix — resolved as a consequence of the modal system)

> Addresses the Discord desktop limitation where users cannot press Enter in a slash command text argument to create new lines.

---

## The Problem

Discord's desktop client does not allow the Enter key to create a new line inside a slash command argument field. If a user types `/embed edit id:EMB-001 field:description` and tries to write multi-line text, pressing Enter submits the command instead.

This is a **platform constraint** — not a bot bug. Two approaches can solve it:

---

## ⭐ Recommendation: Use Modals as the Primary Solution

**Go with the modal-first approach. Do not rely on `{newline}` as the main fix.**

Here's why:

| Factor | Modal Approach | `{newline}` Variable Approach |
|---|---|---|
| **User experience** | Natural — press Enter in the text area, done | Requires learning a special token and mentally parsing where lines break |
| **Discoverability** | Zero learning curve — it works like any text editor | Users must know `{newline}` exists; easy to forget |
| **Error-prone** | Very low — user sees what they type | Medium — easy to misplace, double-use, or forget entirely |
| **Preview accuracy** | Preview shows actual line breaks immediately | Preview only shows breaks after resolving `{newline}` |
| **Works on mobile** | Yes — modals work on mobile Discord | Yes — but redundant if modal is already solving it |
| **Implementation cost** | Already part of the modal system (Feature 03) — zero extra work | Requires a separate resolution pass in the variable engine |

**Conclusion:** Since your system already uses modals for field input (Feature 03), the newline problem is **already solved for free**. The Description modal uses a paragraph-type input (`TextInputStyle.Paragraph`) which natively supports Enter key line breaks. No workaround needed.

`{newline}` can still exist as a variable (Feature 04 includes it), but it should be a **fallback** for the `/embed edit field:description` slash command shortcut path only — not the main solution.

---

## Subfeatures (Sorted by Priority)

---

### 5.1 — Paragraph-Type Input in Description Modal *(Highest)*

**What it does:** The Description field modal uses Discord's `TextInputStyle.Paragraph` input type (as opposed to `TextInputStyle.Short`).

**Effect:**
- The text area is tall (multi-line)
- The Enter key creates a new line instead of submitting
- Shift+Enter also works for line breaks (standard behavior)
- The user submits by clicking the modal's "Submit" button

**This is the primary and complete solution to the newline problem.**

Implementation note: In Discord.js, this is simply:
```js
new TextInputBuilder()
  .setStyle(TextInputStyle.Paragraph)  // ← this is all it takes
```

---

### 5.2 — `{newline}` Variable as Slash Command Fallback *(Medium)*

**What it does:** For users who use the `/embed edit id:EMB-XXX field:description` slash command shortcut (Feature 03 §3.4) rather than the full builder, the `{newline}` variable allows them to indicate line breaks inline.

**Usage example:**
```
/embed edit id:EMB-001 field:description
description: Welcome!{newline}Check out our rules.{newline}{newline}Enjoy your stay!
```

**Resolves to:**
```
Welcome!
Check out our rules.

Enjoy your stay!
```

**Resolution timing:** `{newline}` is resolved **at display/send time**, not at save time. The raw `{newline}` token is stored in the database. This means:
- The preview (Feature 03 §3.3) shows the raw token, not the actual break
- Add a note in the preview: *"📝 `{newline}` tokens will appear as line breaks when posted."*

**This is a secondary/fallback solution only.** Direct users to the modal builder for multi-line descriptions whenever possible.

---

### 5.3 — User-Facing Documentation in Builder *(Low)*

**What it does:** In the builder's "Variables" reference panel (Feature 04 §4.4), include a clear note about the newline variable and when to use it vs. the modal.

**Text to include:**
```
{newline}  → Line break

Tip: If you're using the builder buttons, you don't need {newline} —
just press Enter in the Description text area. Use {newline} only
when editing via slash command directly.
```

---

## Summary

| Situation | Solution |
|---|---|
| User is in the modal builder (button interface) | Press Enter in the Description text area — works natively |
| User is using `/embed edit id:X field:description` slash command | Use `{newline}` where line breaks are needed |
| User is on mobile | Both work fine — modal is still recommended |

---

## Dependencies

- `03_embed_editing.md` — Modal system is where the primary fix lives
- `04_dynamic_variables.md` — `{newline}` is implemented as part of the variable system

## Referenced By

- Nothing directly depends on this feature, but it improves the UX of Feature 03 and Feature 04
