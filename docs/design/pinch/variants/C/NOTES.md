# Pinch, variant C: glyph-first precision

**Concept.** Built up from the 16 px notch glyph: a gumdrop body (a 36 px arc plus 26 px corners), two raised bold-arc claws (palm plus hinged dactyl), and a loupe worn as a monocle that glows green while the camera samples.

**Why it charms.** Big wide-set eyes with one shine each. The detective cue is a prop, not a costume. Half-lids give a dry side-eye, never a frown.

**Why it reads small.** `silhouette-16.svg` has five shapes: body, two eye holes and two U-bite mittens, all at least 2 px. One fill, so the wing tints by state. `pinch.svg` sheds detail by itself below 48 px and 24 px (`@media` in an `<img>`, `@container pinch` when inlined).

**How it animates.** Each part rotates about its pivot in `pivots.json`. Jaws close at +11°. Lids scale on Y from the brow. Squash happens at the feet.
