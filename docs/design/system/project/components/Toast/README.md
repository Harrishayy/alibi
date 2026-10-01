# Toast

A floating, polite notice: the web nudge, a verdict summary, or a sync note.

**Use it for** things that happen while the person is elsewhere on the page: a nudge (`kind="nudge"`), a finished session (`kind="verdict"`), a connection or sync event (`kind="info"`). It sits top-right on `surface-2` with `shadow-float` and announces politely (`role="status"`).

**You provide** `kind`, a short `title` ("Drawing · 12 of 25 min"), the message as `children` (Pinch's line for nudges and verdicts), up to three `actions` (objects `{label, variant, icon, onClick}` or elements; the first object defaults to primary), `onClose` for a dismiss button, and `icon` for an info toast.

It enters with translateY −12 → 0, opacity and blur 4 → 0 on `spring-bouncy`; remove it to dismiss (exits are 170ms).

- Do: order nudge actions "Back to it" (primary), "This counts" (secondary), "Quiet 5 min" (quiet).
- Don't: fill a toast red, shake it, or stack more than two.
- Don't: use it for errors that block the page; those belong in a `Card tone="warn"` where the problem is.
