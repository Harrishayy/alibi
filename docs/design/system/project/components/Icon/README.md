# Icon

Alibi's stroke icon set: a 1.5px line on a 24 grid with round caps and joins, drawn in `currentColor`.

**Use it for** evidence sources (`camera`, `laptop`, `run` for Strava, `heart` for Health), plan blocks (`calendar`), breaks (`cup`), the streak (`claw`), and controls inside `Button`, `Chip` and `IconButton`. `Alibi.Icon.names` lists all 27 names.

**You provide** `name` and a `size` of 16, 20 (default) or 24. Icons are `aria-hidden` unless you pass `title`; colour comes from the parent (`ink-2` at rest, `ink` when active).

- Do: pair an icon with its word in lists and legends.
- Do: use the matching SF Symbol on Apple surfaces (`camera`, `laptopcomputer`, `iphone`, `figure.run`, `heart`, `cup.and.saucer`); `claw` is drawn from Pinch's claw.
- Don't: use emoji anywhere, or a flame for the streak.
- Don't: draw an icon that repeats its own label.
