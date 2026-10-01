# Submission draft (paste into the Airtable form)

**Name:** Alibi — the habit tracker that checks your alibi

**Agent harness (form):** NemoClaw (OpenClaw in an OpenShell sandbox on a DGX Spark, local vLLM)

**Short description:**
Habit trackers trust you. Alibi doesn't. You tell it what you're about to do ("draw for an hour", "learn C++ for 30 minutes"), and a long-running agent gathers evidence while you work: a desk camera sampled once a minute and judged by a vision-language model for physical work, your laptop's active windows for digital work, and Strava for runs. If you drift to your phone, it nudges you mid-session. When the timer ends, it gives a verdict (done / partial / slacked) backed by a contact sheet of timestamped frames or a breakdown of what was actually on screen, and only then updates your tracker. Every night it reports whether you're actually aligned with your weekly goals.

**Why I built it:** I build robots at my desk, study, and apply for internships, and my habit tracker had become fiction. I wanted something that measures what I do, not what I claim.

**How it works:** Python daemon (timers, camera sampling with motion gating, nudges, nightly report, local API) + SQLite event store + a pluggable witness: NVIDIA Build VLM for frames, or Apple's on-device Vision framework so frames never leave the Mac. LLM for intent parsing, window-title classification and the nightly summary, with rule-based fallbacks so the agent never stops. You talk to it through a Dynamic-Island-style bar that lives in the MacBook notch, plus a web dashboard showing claimed vs. seen. Zero model calls when no session is running; window titles are classified once and cached.

**Also:** every camera session becomes a short timelapse "memories reel", and you can correct any sample the witness got wrong — the verdict re-scores, but the correction stays on the record.

**Where the agent lives:** an OpenClaw agent runs 24/7 inside a NemoClaw / OpenShell sandbox on a DGX Spark, on a local model served by vLLM. It reaches the Mac over Tailscale through a single relay: deny-by-default egress, eight allowed API calls, and the Mac's token never enters the sandbox. The relay mirrors the Mac's state every 20 seconds, so the agent still knows what happened while the laptop slept. A heartbeat every 30 minutes reads new verdicts and nudges, keeps a long-term verdict memory, and tells you which habit is still open tonight. You can start a session from the OpenClaw web UI on any device, and the notch island on the Mac lights up.

**What's next:** iOS Shortcuts for phone Focus + Apple Health (the endpoint already exists), learning from your corrections, the camera witness on the Spark's local VLM so frames never leave your network, agent messages straight into the island and iPhone app, and 3D "where did I leave it" memory of the desk.

**Demo:** <video link>
