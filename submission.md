# Submission draft (paste into the Airtable form)

**Name:** Alibi — the habit tracker that checks your alibi

**Short description:**
Habit trackers trust you. Alibi doesn't. You tell it what you're about to do ("draw for an hour", "learn C++ for 30 minutes"), and a long-running agent gathers evidence while you work: a desk camera sampled once a minute and judged by a vision-language model for physical work, your laptop's active windows for digital work, and Strava for runs. If you drift to your phone, it nudges you mid-session. When the timer ends, it gives a verdict (done / partial / slacked) backed by a contact sheet of timestamped frames or a breakdown of what was actually on screen, and only then updates your tracker. Every night it reports whether you're actually aligned with your weekly goals.

**Why I built it:** I build robots at my desk, study, and apply for internships, and my habit tracker had become fiction. I wanted something that measures what I do, not what I claim.

**How it works:** Python daemon (timers, camera sampling with motion gating, nudges, nightly report, local API) + SQLite event store + a pluggable witness: NVIDIA Build VLM for frames, or Apple's on-device Vision framework so frames never leave the Mac. LLM for intent parsing, window-title classification and the nightly summary, with rule-based fallbacks so the agent never stops. You talk to it through a Dynamic-Island-style bar that lives in the MacBook notch, plus a web dashboard showing claimed vs. seen. Zero model calls when no session is running; window titles are classified once and cached.

**Also:** every camera session becomes a short timelapse "memories reel", and you can correct any sample the witness got wrong — the verdict re-scores, but the correction stays on the record.

**What's next:** iOS Shortcuts for phone Focus + Apple Health (the endpoint already exists), learning from your corrections, a fully local VLM on DGX Spark so frames never leave the network, and 3D "where did I leave it" memory of the desk.

**Demo:** <video link>
