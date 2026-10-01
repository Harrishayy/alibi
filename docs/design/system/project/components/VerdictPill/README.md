# VerdictPill

The verdict as a glyph, a word and an optional percentage on a 10% wash: ✓ Done, ◐ Partly, ✕ Slacked.

**Use it for** the verdict card, the island verdict alert, session rows, and the Live Activity's end state.

**You provide** `verdict` (`done`, `partial` or `slacked`) and an optional `ratio` (0–1, shown as a whole percentage). It is announced as "Verdict: partly, 68%".

| Verdict | Fill · text |
|---|---|
| `done` | `accent-wash` · `accent-ink` |
| `partial` | `partial-wash` · `partial-ink` |
| `slacked` | `warn-wash` · `warn-ink` |

It enters with scale 0.94 → 1, opacity and a 2px blur on `spring-bouncy`.

- Do: put the verdict sentence next to it in the `voice` style, and "Fix a moment" right after.
- Don't: paint a solid red or amber slab, or drop the glyph or the word.
