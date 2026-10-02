# The always-on agent

Alibi's Mac sleeps when the lid closes. The agent doesn't. An OpenClaw agent runs around the clock inside a NemoClaw
(OpenShell) sandbox on an NVIDIA DGX Spark. It reads what Alibi has seen, keeps a memory of what slipped and why, and
writes the morning, checkpoint and night briefs. It can't start, stop or change anything: Alibi on the Mac owns the
clock and the truth, and its verdicts are final.

Setup and checks: [SPARK.md](SPARK.md). Every field the agent reads: the "Agent context" section of [SIGNALS.md](SIGNALS.md).

```
 Mac ─ Alibi daemon: :8765 dashboard (loopback only) · :8766 phone + agent API (tailnet only)
          ▲  X-Alibi-Agent-Token
          │  Tailscale
 DGX Spark host
   alibi.relay :8770 (systemd user service): holds the agent token, mirrors the Mac every 20 s into data/relay/
          ▲  Docker bridge; egress preset "alibi-relay"
   OpenShell sandbox "alibi" (deny-by-default egress)
     OpenClaw · skill `alibi` · cron jobs · 30-minute heartbeat · memory/alibi.md
          ▼  inference.local (OpenShell route: the NVIDIA key stays on the host)
 NVIDIA Build: Nemotron 3 Super (nvidia/nemotron-3-super-120b-a12b)
```

## What it does

Alibi writes its own rules digest at 07:30, 12:00, 16:00, 20:00 and 22:00. The agent's jobs run a few minutes later,
so the rules version always exists first (OpenClaw cron, Europe/London; jobs in `spark/briefs.json`):

| Job | When | What |
|---|---|---|
| Morning | 07:32 | Reads `/status`, `/context` and its memory. If last night's review proposed a block, says whether it was kept. Posts the morning brief. |
| Checkpoint | 12:02, 16:02, 20:02 | Reads `/context` and `/digests`. Posts only if a habit's status changed or a planned block starts within 4 hours. |
| Night | 22:05 | Appends what slipped today to `memory/alibi.md`, then posts the night brief. |
| Heartbeat | every 30 min | Checks the Mac is reachable. Posts one `risk` brief the first time a habit goes off track that day (`spark/HEARTBEAT.md`). |

**Memory.** One line per night in `memory/alibi.md` in the OpenClaw workspace:
`YYYY-MM-DD · what slipped · why, if the context says · what it proposed`. The morning job reads it back, so the
brief can say whether the plan held. `last_night.kept` in `/context` is the fact; the memory note is the story.

**Briefs.** Each brief is a `POST /brief` with an idempotency key. `kind` is `morning`, `checkpoint`, `night` or
`risk`; text is at most 600 characters, with at most 5 `https://` links. A brief that arrives within 20 minutes of
its slot is shown above Alibi's rules brief, tagged `via: nemoclaw`, and drops down on the notch island once per slot
unless a session is live. A later one is stored but not notified. Briefs are derived output
(`agent_briefs.jsonl` in the data directory), never evidence.

**Standing orders** (`spark/skills/alibi/SKILL.md`): truth comes only from `/context` and `/digests`; never claim a
habit is done; never state per-app minutes (`picked_apps_min` is an aggregate of the apps you marked as
distracting); if the Mac is asleep, say so with its last-seen time and post nothing; dry, short, at most three
sentences, no exclamation marks.

## How it reaches the Mac

**The relay** (`alibi/relay.py`) runs on the Spark host, outside the sandbox, so the Mac's agent token never enters
the sandbox. It mirrors the Mac's context and digests every 20 seconds (`RELAY_POLL_S`) into `data/relay/`; while the
laptop sleeps, the agent gets the last mirrored copy marked `stale: true`. It serves the sandbox four calls and
refuses callers outside loopback and the Docker bridge:

| Call | What |
|---|---|
| `GET /status` | `mac_online`, `last_seen`, `last_error` |
| `GET /context` | the live context, or the mirrored copy with `stale: true` |
| `GET /digests?limit=5` | Alibi's own recent rules digests |
| `POST /brief` | the agent's only write, passed to the Mac |

**The agent API** (`alibi/routes_agent.py`) lives on the Mac's phone listener (:8766), never on the loopback
dashboard:

| Route | What |
|---|---|
| `GET /api/agent/ping` | liveness and `agent_last_seen` |
| `GET /api/agent/context` | one snapshot for a brief: the week per habit, today, free gaps tomorrow, last night's proposal, milestones, signals |
| `GET /api/agent/digests?limit=5` | recent rules digests |
| `POST /api/agent/brief` | store the agent's brief for a slot |

- Token in the `X-Alibi-Agent-Token` header (or `Authorization: Bearer`). It is its own secret (`nemoclaw_token` in
  `data/secrets.json`), separate from the phone key. A token in the query string gets 401.
- Loopback or tailnet sources only (403 otherwise). Bodies up to 16 KB (413), 30 writes a minute (429), duplicate
  idempotency keys return the stored response.
- The context is aggregates only. `never_included` lists what it never carries: camera frames, window titles, app
  names, location coordinates, notification text.

## Egress

The sandbox denies all egress by default. The `alibi-relay` preset (`spark/policy-alibi-relay.yaml`) opens exactly one
destination, the relay on the Docker bridge, for four rules (`GET /status`, `GET /context`, `GET /digests`,
`POST /brief`), and only for `/usr/bin/curl`. Inference goes through OpenShell's `inference.local` route to NVIDIA
Build, so the NVIDIA key stays with the host and never enters the sandbox.

What leaves the Mac for the agent: habit names, minutes, planned times, verdicts and statuses, run distances,
milestone titles, days-off labels and aggregate counts.

## Staying up

`spark/keepalive/` installs a systemd user timer (`bash spark/keepalive/install.sh`) that runs 2 minutes after boot
and every 10 minutes. It restarts the OpenShell gateway service if it is down, starts the sandbox (or recovers it),
restarts the OpenClaw gateway inside it if `openclaw cron list` stops answering, and restarts the relay. It is quiet
when all is well. User services run without a login once lingering is on (`scripts/spark_setup.sh` turns it on).

## When the Spark is down

Nothing on the Mac waits for the agent. Sessions, the witness, verdicts, nudges and phone sync never call the Spark.
Alibi's rules digests still arrive on time.
