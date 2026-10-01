# PinchLine

A 20px Pinch and one sentence in Alibi's voice: the way Alibi speaks anywhere outside the hero.

**Use it for** nudges, verdict sentences, the drift line on the live card, correction replies ("Fair. I've changed that one.") and empty states ("Nothing claimed yet. What are you about to do?").

**You provide** the sentence as `children`, an optional `mood` for the avatar, `compact` for the island-sized 15px line, and `theme` when it sits on a surface that differs from the page. Wrap only the cause noun in `<span className="al-cause">` to set it in `warn-ink`.

The line uses the `voice` style (20/1.45, weight 500, −0.01em) in `ink`; the avatar centres on the first line.

- Do: write in the first person, 12 words or fewer, digits for numbers: "You said drawing. I've seen your phone for 3 minutes."
- Do: offer the fix after any bad news.
- Don't: use "!", emoji, "busted", "lazy" or "you failed", or colour the whole sentence.
