# Card

The one container: `surface-1`, a `hairline` edge, `radius-md`, and no shadow.

**Use it for** every grouped block on the dashboard (Now, latest verdict, Today, This week) and for rows of stats. Depth comes from the hairline, not a shadow; floating layers use `Alibi.Toast` instead.

**You provide** `children`, an optional `tone` and `padding`, and `as` for a landmark element (`section`, `article`).

| Tone | Fill | Use |
|---|---|---|
| `default` | `surface-1` | almost everything |
| `raised` | `surface-2` | a card inside a card, a selected row |
| `accent` | `accent-wash` | one quiet win ("A week of alibis that checked out.") |
| `warn` | `warn-wash` | bad news and errors, always with the fix inside |

Padding is 16 / 24 / 32px (`sm` / `md` / `lg`); 24px is the web card padding. Leave `space-6` between cards.

- Do: lead each card with one number or one sentence.
- Don't: put a coloured left border on a card, stack two headlines in one, or add a shadow.
