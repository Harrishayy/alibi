# Stat

One number with its label: the headline figure of a card, set in the rounded face with tabular figures.

**Use it for** "On task 82%", "Seen today 1h 52m", "Days in a row 6", and the time beside a compact `RingTimer`.

**You provide** `value` (preformatted: "82%", "1h 52m", 6), `label` (sentence case) and an optional `sub` line of context ("Claimed 2h 10m"). When `value` changes, only the changed digits roll on `spring-snappy`; screen readers get the whole value.

- Do: write totals as `2h 10m` and times as `18:04`.
- Do: lead a card with one Stat, or a row of up to three.
- Don't: put two Stats with competing jobs in one card.
