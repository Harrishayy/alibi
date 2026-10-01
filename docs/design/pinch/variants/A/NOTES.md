# Pinch A: Bean detective

**Concept.** A chibi bean-shaped green lobster with mitten claws raised in a V. It wears a grey deerstalker (a crown and two peaks). Its magnifying lens glows green when the camera is on, and in the side-eye pose the lens magnifies Pinch's own suspicious eye.

**Charm.** The eyes are big (23% of body width) and set low, with a tiny mouth and amber blush. The cap and lens are the same grey, so the green stays pure. None of the poses shame the user.

**Small sizes.** Below 24 px it switches to `silhouette-16.svg`. That version has five flat shapes: a body, two notched pincers and two 2 px pupils.

**Animation.** Every part is its own `<g id>`, and the pivots are in `pivots.json`. The arm, claw and jaw groups are nested and rotate about the shoulder, wrist and hinge. The lens is a free prop.
