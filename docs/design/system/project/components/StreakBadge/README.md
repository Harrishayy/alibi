# StreakBadge

The streak as a pill: the claw glyph, a rolling day count and the freezes left, never a flame.

**Use it for** the dashboard hero strip and the island's footer line.

**You provide** `days` and optional `freezes` (shown only when above 0). When `days` goes up the badge bumps (scale 1 → 1.18 → 1 on `spring-bouncy`) and the digit rolls on `spring-snappy`. It is announced as "Streak: 6 days, 1 freeze left".

- Do: say "1 day", "6 days", "1 freeze left", "2 freezes left".
- Don't: warn that a streak is about to break, or use fire, red or urgency.
- Don't: show a zero streak; the hero line covers a fresh start.
