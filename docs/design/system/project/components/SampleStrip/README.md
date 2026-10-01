# SampleStrip

The last few samples of a live session in a row of small cells, newest on the right.

**Use it for** the live session card (web Now card and the expanded island) and session rows that expand to show what Alibi saw.

**You provide** `labels` oldest to newest (pass the last 6), an optional `size` (cell height, default 28px), `develop` to play the polaroid develop on the newest cell whenever the labels change, and optional `frames` (thumbnail URLs, one per label) to draw each mark over its frame.

The develop: the new cell rises 6px with opacity over `dur-medium`, a frame goes from grey and blurred to sharp over `dur-reveal`, and its dot pops in on `spring-bouncy` at 900ms. Pinch never reacts to it. The strip is announced as one image: "Last 6 samples: on task, phone, …".

- Do: keep cells at 64px or under so the develop filter stays cheap.
- Don't: put Pinch on or beside evidence frames.
- Don't: show more than 6 in the live card; the full record belongs to the contact sheet.
