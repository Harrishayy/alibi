# Button

The one button: secondary by default, `primary` (green fill, black text) at most once per view, for the thing the view is for.

**Use it for** actions: "Start session", "Back to it", "Fix a moment", "See proof", "Go again". Use `Alibi.IconButton` for icon-only toolbar controls and `Alibi.Chip` for one-tap choices.

**You provide** the label as `children` (a verb first, sentence case, no "!"), a `variant`, an optional `size` and `icon`, and the usual button props (`onClick`, `disabled`, `type`). An `iconOnly` button needs `ariaLabel`.

| Variant | Looks | Use |
|---|---|---|
| `primary` | `accent` fill, `on-accent` text | the one action the view exists for |
| `secondary` | `surface-2`, `hairline` edge | everyday actions |
| `ghost` | transparent, `hairline-strong` edge | a second strong action beside primary |
| `quiet` | text in `ink-2` | dismissals and low-stakes options ("Quiet 5 min") |

Sizes are 28 / 36 / 44px tall (`sm` / `md` / `lg`). Leave `space-2` between adjacent buttons. Press scales to 0.97 over `dur-micro` and releases on `spring-micro`; focus shows the 2px `focus-ring` at a 2px offset.

- Do: put the primary first in a row of actions, then secondary, then quiet ("Back to it", "This counts", "Quiet 5 min").
- Do: keep labels to one to three words.
- Don't: put two primaries in one view, or set white text on green.
- Don't: use a red button for bad news; bad news is a word, a dot or a wash, and the fix is a normal button.
