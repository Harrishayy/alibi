# Composer

The claim field: "What are you about to do?", a round green send button, and habit chips with ⌘1–⌘9.

**Use it for** the Now card when nothing is live on the dashboard, and inside the expanded island. It is the single most important input in Alibi, so there is one per view.

**You provide** `onSubmit(text)` (called on ↵ or the send button with trimmed, non-empty text), optional `chips` (habit names), an optional `placeholder`, and `value` plus `onChange` if you want it controlled. `focused` forces the focus look for screenshots.

Behaviour you get for free:

- `/` anywhere on the page focuses the first composer (not while typing in another field), and a `/` keycap hint shows while it is empty and unfocused.
- ⌘1–⌘9 fill the field from the chips while it has focus; esc blurs it.
- The send button sits at 30% opacity until there is text. Focus draws a 2px `focus-ring` edge.
- In the island the field takes `radius-md` (concentric with the 28px shape) and a 48px height.

- Do: pair it with Pinch in `listening` while it has focus.
- Do: keep the placeholder as the question Alibi asks; it is the first line a new user reads.
- Don't: add a second text input beside it, or a submit button with words.
