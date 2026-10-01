# IconButton

A quiet, icon-only control for headers, toolbars and dismiss buttons, always with an accessible name.

**Use it for** setup (`settings`), dismiss (`x`), pause, undo and show-frames toggles. If the action needs words to be understood, use `Alibi.Button` with an icon instead.

**You provide** `icon`, `ariaLabel` (required, a verb phrase such as "Open setup") and an optional `size` (`sm` 28px, `md` 36px, `lg` 44px; the icon is 16 / 20 / 24px). Pass `aria-pressed` for toggles, which then hold the `surface-3` fill.

- Do: keep targets at 28px or larger on the web and in the island, and 44pt on iPhone.
- Do: use `sm` inside cards and toasts, `md` in headers.
- Don't: tint it green; icons go green only inside a primary button.
- Don't: ship one without `ariaLabel`.
