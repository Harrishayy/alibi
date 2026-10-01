# Chip

A one-tap choice in one or two words: habit chips under the composer, filters, and the island's state picker.

**Use it for** picking a habit to claim ("Drawing", "C++", "Reading"), filtering a list, or choosing one of a few states. Use `Alibi.Button` for actions.

**You provide** the label as `children`, `selected` (rendered as `aria-pressed`), an optional leading `icon` and an optional trailing `kbd` shortcut ("⌘1"). Chips are 32px tall with a `radius-xs` corner, like keycaps and inline tags.

Selection crossfades the fill to `accent-wash` and the text to `accent-ink` on `spring-micro`.

- Do: number the first nine habit chips ⌘1–⌘9 and make those shortcuts work.
- Do: keep a row of chips to four or fewer in the island.
- Don't: use a chip as a status display; status is `StatusDot` or `VerdictPill`.
