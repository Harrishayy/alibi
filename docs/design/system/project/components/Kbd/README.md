# Kbd

A keycap in the mono face that shows a keyboard shortcut.

**Use it for** the shortcuts Alibi actually supports: ⌥⌘A toggles the island, `/` focuses the composer, ↵ starts a session, esc closes, ⌘1–⌘9 pick a habit chip.

**You provide** the key as glyphs in `children`: "⌥⌘A", "↵", "esc", "⌘1", "/". It renders in `--font-mono` 12px on `surface-2` with a `hairline-strong` edge and a `radius-xs` corner.

- Do: put it next to the words it explains ("Toggle the island ⌥⌘A").
- Don't: show a shortcut that does nothing.
- Don't: use the mono face for anything other than keycaps and IDs.
