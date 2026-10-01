# Alibi ↔ DGX Spark / NemoClaw contract

**What this is:** paste this whole document into the Claude session that is setting up NemoClaw on the DGX Spark. It is self-contained.

Written Thu 1 Oct 2026, 19:20 BST. The challenge submission closes 2 Oct, and the booth demo is 14 Oct.

**Marking.** Unverified items are marked **[UNVERIFIED]**: they come from public docs or issue threads and nobody has tested them on this install. Check each one on the box and report what you find. Don't assume.

**Secrets.** Never paste tokens or keys into chat, logs or this file. Hand them to the user out of band. In the commands below, `$TOKEN`-style variables are placeholders.

---

## 0. Context

**What Alibi is.** A habit tracker on the user's Mac that only ticks a habit when it has evidence. It runs:
- a Python daemon plus FastAPI;
- an Apple Vision camera witness;
- Mac signals;
- an iPhone companion.

It is **offline-first**: everything works with no model at all, using rule-based text.

**What the Spark adds.** A model that writes and *decides* (it proposes a replan of the week), and a NemoClaw agent that researches the web.

**Ownership.** Alibi owns the clock and the truth:
- Alibi always produces its own rules version first.
- The Spark's output is shown with an honest `via` tag.
- The Spark never decides whether a habit is done.

**Network.** Both machines are on the same tailnet.

| Node | Tailnet IP | Name |
|---|---|---|
| Spark | `100.76.35.21` | `spark` |
| Mac | `100.66.226.12` | `harrishs-macbook-pro.tail41fc04.ts.net` |

The tailnet also has other people's nodes (e.g. `thomas-laptop`). Being on the tailnet is not authentication; tokens are.

**Status at 19:15.**
- From the Mac, ports 8000, 11434, 18789 and 8443 on the Spark all refuse.
- The Mac has **no** `tailscale serve` config.
- Alibi's phone port `:8766` listens on all interfaces over plain HTTP. The dashboard (`:8765`) is loopback-only and must stay that way.

---

## 1. Deliverables, in priority order

Stop after any step and report. Each step is independently useful.

| # | Deliverable | Why Alibi needs it | Alibi tier |
|---|---|---|---|
| **1** | **The raw model on the tailnet, with tool calling.** It must be reachable from the Mac at `http://100.76.35.21:8000/v1` (vLLM) or `:11434/v1` (Ollama). | This is the most important one. It powers the night-review tool loop (the agent beat in the video) and the digest prose. It needs no OpenClaw config at all. | submission |
| 2 | **Thinking off by default**, or confirm how to disable it per request | Alibi uses `max_tokens` of 300–600 and a 45 s budget. A model that thinks first returns empty text. | submission |
| 3 | **OpenClaw gateway HTTP chat completions**, exposed on the tailnet, with **`web_search` working** | Grounded "Ask" (e.g. "tips for running" plus links). | submission, gated |
| 4 | **A way for NemoClaw to post briefs into Alibi** (§6): from inside the sandbox if egress allows it, otherwise a host-side job | NemoClaw becomes an author of the morning, checkpoint and night briefs. | stretch |
| 5 | MCP (`mcp add`) | Read tools plus `post_brief`. | booth (Oct 14) |

---

## 2. Ports and auth

| Direction | URL | Auth | Notes |
|---|---|---|---|
| Mac → Spark model | `http://100.76.35.21:8000/v1` (vLLM) or `http://100.76.35.21:11434/v1` (Ollama) | none, or `Authorization: Bearer $SPARK_LLM_KEY` if you set one | The bind address must include the tailnet interface. Prefer binding `100.76.35.21` (or `0.0.0.0` plus a host firewall restricting the port to `100.66.226.12`). It is plain HTTP over WireGuard. |
| Mac → OpenClaw gateway | `https://spark.<tailnet>.ts.net:8443/v1/...`, i.e. `tailscale serve --bg --https=8443 http://127.0.0.1:18789` on the Spark | `Authorization: Bearer $NEMOCLAW_TOKEN` (the gateway token, `gateway.auth.token` / `OPENCLAW_GATEWAY_TOKEN`) **[UNVERIFIED names]** | Docs say the gateway token is **full operator access**. Never expose it beyond the tailnet; use no Funnel. |
| Spark → Mac (Alibi agent API) | `http://100.66.226.12:8766/api/agent/...` today; `https://harrishs-macbook-pro.tail41fc04.ts.net/api/agent/...` if the user enables `tailscale serve` on the Mac (their decision) | Header `X-Alibi-Agent-Token: $ALIBI_AGENT_TOKEN`; `Authorization: Bearer $ALIBI_AGENT_TOKEN` is also accepted. **A query-string token is refused.** It is a separate secret from the phone key. | **Not built yet on the Alibi side**; the shapes in §5 are the contract. Writes are rate-limited (30/min) and have a 16 KB body cap. |

**Where the tokens live.**
- **On the Mac:**
  - `NEMOCLAW_URL`, `NEMOCLAW_TOKEN`, `LLM_BASE_URL`, `LLM_MODEL` in Alibi's `.env`;
  - `nemoclaw_token` (Alibi's agent token) in `data/secrets.json`.
- **On the Spark:** as an OpenShell provider secret or env var. Never in a URL.

---

## 3. Step 1–2 details: the raw model (most important)

**Model choice.** Sources disagree on the Spark default **[UNVERIFIED]**:
- the current playbook says `qwen3.6-35b-a3b-nvfp4` on managed vLLM `:8000`;
- an earlier NVIDIA blog uses Nemotron 3 Super 120B on Ollama `:11434`.

Report:
1. which one is installed;
2. tokens/s for a 300-token reply;
3. whether it supports OpenAI-style `tools` / `tool_calls`.

Nemotron reads best for the challenge, if it is fast enough (a 4-turn loop must finish in under 45 s).

**Tool calling.**
- **vLLM** needs `--enable-auto-tool-choice --tool-call-parser <parser>` (e.g. `hermes` for Qwen-family) **[UNVERIFIED for this model/version]**. If NemoClaw manages vLLM, find where its launch flags live.
- **Ollama** supports `tools` for models whose template declares it **[UNVERIFIED for Nemotron]**.

**Thinking off.**
- Qwen3 on vLLM: per request, `{"chat_template_kwargs":{"enable_thinking":false}}`.
- Nemotron: a `/no_think` system line **[UNVERIFIED per model]**.

Report which form works.

**What Alibi will send** (the night-review loop: at most 4 turns, `temperature` 0.2, `tool_choice:"auto"`):

```json
{
  "model": "<MODEL_ID>",
  "temperature": 0.2,
  "max_tokens": 600,
  "chat_template_kwargs": {"enable_thinking": false},
  "messages": [
    {"role": "system", "content": "You are Alibi's night planner. Facts come only from tools. Propose at most one recovery block for tomorrow or the day after by calling propose(). Never claim a habit is done. Dry, short, no exclamation marks."},
    {"role": "user", "content": "Night review for 2026-10-01. Missed today: drawing 19:00 (25 min)."}
  ],
  "tools": [
    {"type": "function", "function": {"name": "week_status", "description": "Per-habit this week: target, verified, status3, buffer_days, need_per_day_min", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "plan", "description": "Planned blocks for a day", "parameters": {"type": "object", "properties": {"day": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["day"]}}},
    {"type": "function", "function": {"name": "free_gaps", "description": "Free gaps 07:00-22:00 on a day", "parameters": {"type": "object", "properties": {"day": {"type": "string"}, "min_minutes": {"type": "integer"}}, "required": ["day", "min_minutes"]}}},
    {"type": "function", "function": {"name": "history", "description": "Daily verified minutes for a habit", "parameters": {"type": "object", "properties": {"habit": {"type": "string"}, "days": {"type": "integer"}}, "required": ["habit"]}}},
    {"type": "function", "function": {"name": "propose", "description": "Propose one recovery block; the user confirms", "parameters": {"type": "object", "properties": {"habit": {"type": "string"}, "day": {"type": "string"}, "at": {"type": "string", "description": "HH:MM"}, "minutes": {"type": "integer"}, "why": {"type": "string"}}, "required": ["habit", "day", "at", "minutes", "why"]}}}
  ]
}
```

**What Alibi expects back** on each turn:
- either `choices[0].message.tool_calls[]` (`function.name` plus JSON-string `arguments`), or
- a final `content`.

Alibi executes the tools locally (no data leaves except what is in these messages) and validates `propose()`. Anything invalid falls back to Alibi's rules picker.

**What leaves the Mac in this loop:** habit names, minutes, planned times and free gaps. No frames, window titles or phone data.

---

## 4. Step 3 details: grounded Ask through the OpenClaw gateway

**Enable** `gateway.http.endpoints.chatCompletions.enabled: true` **[UNVERIFIED key path]**.

**Biggest known risk:** `/sandbox/.openclaw/openclaw.json` is reported root-owned, read-only and Landlock-locked, so `openclaw config set` fails with EACCES (NemoClaw issues #719, #1699, #2537, #2544) **[UNVERIFIED on this version]**. Try these in order:
1. `nemoclaw <sb> config set …`
2. a custom image via `nemoclaw onboard --from <Dockerfile>` / `rebuild`
3. `nemoclaw <sb> snapshot --backup` first

**Expose it:**
1. `openshell forward start 18789 <sb> --background` (or `nemoclaw <sb> forward 18789`) **[UNVERIFIED]**
2. then `tailscale serve --bg --https=8443 http://127.0.0.1:18789`

Also report whether the gateway needs `gateway.trustedProxies` behind `tailscale serve` **[UNVERIFIED]**.

**Web search.** Brave via onboarding (`BRAVE_API_KEY=… nemoclaw onboard --name <sb> --recreate-sandbox`), or a keyless provider (DuckDuckGo / SearXNG) plus a custom egress preset **[UNVERIFIED provider names on this version]**.

**Request Alibi sends:**

```json
POST /v1/chat/completions
Authorization: Bearer $NEMOCLAW_TOKEN
{
  "model": "openclaw/default",
  "user": "alibi-ask",
  "stream": false,
  "messages": [
    {"role": "system", "content": "Answer in at most 80 words, dry, no exclamation marks. Use web_search. End with a fenced JSON block: {\"links\":[{\"title\":\"…\",\"url\":\"…\"}]} using only URLs returned by web_search. Do not restate the user's numbers; Alibi shows them."},
    {"role": "user", "content": "Question: tips for running\nContext (from Alibi, for relevance only): habit=running; this week 1 of 3 runs; next free 30+ min: 2026-10-02 07:00."}
  ]
}
```

**Expected response:** standard OpenAI chat completion. `choices[0].message.content` holds the answer text plus a fenced JSON links block.

**What Alibi does with it:**
- parses the links block;
- **HEAD-checks every URL from the Mac** (2 s timeout) and keeps only 2xx/3xx;
- tags the result `via:"nemoclaw"`.

The model's numbers are never shown; Alibi renders the facts line itself.

**Timeouts on the Alibi side:** connect 3 s, total 30 s. Health probe: `GET /v1/models`, cached 60 s.

---

## 5. Alibi agent API (Spark → Mac)

**Status.** These routes are the contract. **They are not built yet on the Alibi side.** Until Alibi says they are live, treat them as a spec, not as endpoints.

**Common rules:**
- **Base URL:** `http://100.66.226.12:8766`, or the Mac's ts.net HTTPS name if `tailscale serve` is enabled.
- **Headers:** `X-Alibi-Agent-Token: $ALIBI_AGENT_TOKEN` and `Content-Type: application/json`.
- **Response fields:** all responses include `ts` (unix seconds) and `tz` (`"Europe/London"`).

**Error codes:**

| Code | Meaning |
|---|---|
| 401 | Bad or missing token, or token sent in the query |
| 403 | Source is not tailnet or loopback |
| 413 | Body over 16 KB |
| 429 | Rate limit (30 writes/min) |

**Agent permissions.** No agent write can start, stop, or alter sessions, habits, goals or evidence. Writes are limited to `post_brief`. Replans are proposals that the user confirms in Alibi.

### `GET /api/agent/context`
A one-call snapshot for a brief.

```json
{
  "ts": 1790000000, "tz": "Europe/London",
  "week": {"start": "2026-09-28", "end": "2026-10-04"},
  "habits": [
    {"key": "drawing", "label": "Drawing", "unit": "min", "target": 180, "verified": 140, "claimed": 165,
     "status3": "at_risk", "buffer_days": -1.0, "need_per_day_min": 35, "need_today_min": 25, "stale": false,
     "reason": "40 min behind"}
  ],
  "today": {"planned_min": 135, "seen_min": 100, "picked_apps_min": 38, "phone_last_synced": "18:42",
            "blocks": [{"key": "drawing@2026-10-01T19:00", "habit": "drawing", "at": "19:00", "min": 25, "state": "missed"}]},
  "free_gaps_tomorrow": [{"at": "07:00", "min": 60}, {"at": "12:30", "min": 45}],
  "last_night": {"slot": "2026-09-30-night", "proposal": {"habit": "drawing", "day": "2026-10-01", "at": "07:30", "minutes": 25},
                 "accepted": true, "kept": {"seen_min": 22, "of": 25}},
  "milestones": [{"title": "Submit Claw challenge", "due": "2026-10-02", "done": false}],
  "signals": {"flowing": 8, "total": 14, "text": "8 of 14 sources flowing"},
  "never_included": ["camera frames", "window titles", "app names", "location coordinates", "notification text"]
}
```

`picked_apps_min` is an **aggregate** of the user's chosen distracting apps (YouTube, Instagram). There are **no per-app minutes**, and briefs must never claim any.

### `GET /api/agent/digests?limit=5`
Alibi's own recent rules digests, so the agent can build on them.

```json
{"items": [{"slot": "2026-10-01-check-16", "kind": "checkpoint", "ts": 1790000000, "sent": false,
            "text": "No change since 12:00.", "via": "rules"}]}
```

### `POST /api/agent/brief`
The agent posts its version of a slot's brief.

Request:
```json
{
  "idempotency_key": "2026-10-02-morning-nemoclaw",
  "slot": "2026-10-02-morning",
  "kind": "morning",
  "text": "Drawing needs 25 minutes today to stay on pace. Your 07:30 block from last night is the easiest place for it.",
  "items": [{"habit": "drawing", "note": "25 min today"}],
  "links": [{"title": "…", "url": "https://…"}],
  "model": "<MODEL_ID>",
  "tools_used": ["alibi.context", "web_search"]
}
```

**Validation:** `kind` is one of `morning|checkpoint|night|risk`; `slot` matches `YYYY-MM-DD-kind[-HH]`; `text` is at most 600 characters; at most 5 links.

**Duplicate key:** returns the stored response.

Response:
```json
{"ok": true, "stored": "2026-10-02-morning", "shown_as": "agent", "rules_version_folded": true}
```

**How Alibi shows it:**
- An agent brief that arrives **within 20 minutes of the slot time** is shown above Alibi's rules brief, tagged `via: nemoclaw`.
- One that arrives later is stored but not notified.
- Links are HEAD-checked by the Mac before display.

### `GET /api/agent/ping`
Liveness, and `agent_last_seen` for Alibi's Streams page.

```json
{"ok": true, "ts": 1790000000, "agent_last_seen": 1789999000}
```

---

## 6. Scheduled jobs (NemoClaw side; stretch)

Alibi's own slots are 07:30 (morning), 12:00, 16:00 and 20:00 (checkpoints, suppressed when nothing has changed), and 22:00 (night). Offset the agent's jobs by two to five minutes so Alibi's rules version exists first.

| Job | Cron (Europe/London) | Prompt gist |
|---|---|---|
| morning | `32 7 * * *` | GET context → if `last_night.accepted`, mention whether it was kept → post_brief(kind=morning) |
| checkpoint | `2 12,16,20 * * *` | GET context and digests → post only if `status3` changed or a block starts within 4 h |
| night | `5 22 * * *` | GET context → write a `memory/` note (what slipped, why) → post_brief(kind=night) |
| risk (optional) | `*/30 7-23 * * *` | Post only if a habit newly moved to off_track |

**Plan A: inside the sandbox** with OpenClaw cron:
```
nemoclaw <sb> cron add …  /  openclaw automations create "<cron>" "<prompt>" --name alibi-<job> --session isolated --tz Europe/London --no-deliver
```
**[UNVERIFIED flags]**

This needs the sandbox to reach the Mac. Facts to check:
- OpenShell's SSRF guard blocks private and CGNAT addresses (100.64/10) unless the host is admitted with `--trusted-private-host`, and **may require HTTPS with a matching cert** **[UNVERIFIED for non-MCP egress]**.
- The egress policy is scoped per binary; `curl` from the shell is blocked **[UNVERIFIED]**.
- Whether MagicDNS `*.ts.net` resolves inside the sandbox **[UNVERIFIED]**.

Test with `policy add --from-file … --dry-run`.

**Plan B: host-side.** Use this if Plan A's egress is not workable by submission. Run a systemd timer or cron **on the Spark host**, outside the sandbox. For each slot it:
1. `curl`s `GET /api/agent/context` from the Mac;
2. sends it to the gateway's `/v1/chat/completions` (`model: openclaw/default`, `user: alibi-briefs`) so the OpenClaw agent (with memory and web_search) writes the brief;
3. `curl`s the result to `POST /api/agent/brief`.

The OpenClaw agent still authors the brief (so `via: nemoclaw` is true), and the sandbox needs no egress to the Mac.

**Workspace standing orders** (`AGENTS.md` in the OpenClaw workspace):
- "You are Alibi's coach. Truth comes only from Alibi's context. Never claim a habit is done. Never state per-app phone minutes. Dry, short, no exclamation marks. Every brief ends with a POST to /api/agent/brief."

`USER.md`:
- "No Apple Watch. Distracting apps: YouTube, Instagram (tracked only as an aggregate). Repos `c++` and `smintweb` are evidence for C++ and portfolio."

---

## 7. Egress allowlist (sandbox)

| Destination | Why | How |
|---|---|---|
| Local inference (vLLM or Ollama on the Spark) | the model | Default; no external egress |
| Search provider (`api.search.brave.com:443`, or the keyless provider's host) | `web_search` | Onboarding preset, or `policy add --from-file` **[UNVERIFIED preset names]** |
| `web_fetch` targets | Optional | Prefer **off** for Alibi. Ask only needs search results; Alibi HEAD-checks links itself. |
| Mac `100.66.226.12:8766`, or `harrishs-macbook-pro.tail41fc04.ts.net:443` | Plan A briefs / MCP | `--trusted-private-host`; HTTPS likely required **[UNVERIFIED]** |
| Telegram | Not needed | Alibi routes its own notifications |

**Do not allow:** anything else. The agent needs no access to the Mac's `:8765`; it is loopback-only and must stay that way.

**Privacy statement Alibi displays** (keep it true):
- Habit names, minutes and planned times go to the Spark over Tailscale.
- Search questions go to the search provider.
- Camera frames, window titles, app names, coordinates and notification text are never sent.

---

## 8. Test checklist (run in this order, from the Mac unless noted)

```bash
# 0. Tailnet reachability
tailscale ping spark

# 1. Raw model is up and lists the model ID
curl -s -m 5 http://100.76.35.21:8000/v1/models | head -c 400          # or :11434/v1/models

# 2. Plain completion, thinking off, timed (target under 10 s for ~150 tokens)
time curl -s -m 45 http://100.76.35.21:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model":"<MODEL_ID>","max_tokens":150,"chat_template_kwargs":{"enable_thinking":false},
  "messages":[{"role":"user","content":"Say: drawing needs 25 minutes today. One sentence."}]}' | head -c 600
#    PASS: non-empty content, no <think> block.

# 3. Tool calling: the model must emit a tool_call, not prose
curl -s -m 45 http://100.76.35.21:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model":"<MODEL_ID>","tool_choice":"auto","chat_template_kwargs":{"enable_thinking":false},
  "messages":[{"role":"user","content":"What are tomorrow free gaps of at least 25 minutes? Use the tool."}],
  "tools":[{"type":"function","function":{"name":"free_gaps","parameters":{"type":"object",
    "properties":{"day":{"type":"string"},"min_minutes":{"type":"integer"}},"required":["day","min_minutes"]}}}]}' \
  | python3 -c 'import json,sys; m=json.load(sys.stdin)["choices"][0]["message"]; print(m.get("tool_calls"))'
#    PASS: prints a list with function.name == "free_gaps" and JSON arguments.

# 4. Gateway (only if step 3 of §1 was attempted); token comes from the environment, never pasted
curl -s -m 5 -H "Authorization: Bearer $NEMOCLAW_TOKEN" https://spark.<tailnet>.ts.net:8443/v1/models | head -c 400

# 5. Grounded ask returns links from web_search
curl -s -m 40 -H "Authorization: Bearer $NEMOCLAW_TOKEN" -H 'Content-Type: application/json' \
  https://spark.<tailnet>.ts.net:8443/v1/chat/completions -d '{"model":"openclaw/default","user":"alibi-ask",
  "messages":[{"role":"user","content":"tips for running. End with a fenced JSON block {\"links\":[{\"title\":\"\",\"url\":\"\"}]} using only web_search URLs."}]}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"][-800:])'
#    PASS: 3 or more https URLs that open in a browser.

# 6. (Once Alibi announces /api/agent/* is live) Spark → Mac, run ON THE SPARK host
curl -s -m 5 -H "X-Alibi-Agent-Token: $ALIBI_AGENT_TOKEN" http://100.66.226.12:8766/api/agent/ping
curl -s -m 5 -H "X-Alibi-Agent-Token: $ALIBI_AGENT_TOKEN" http://100.66.226.12:8766/api/agent/context | head -c 600
curl -s -m 5 -X POST -H "X-Alibi-Agent-Token: $ALIBI_AGENT_TOKEN" -H 'Content-Type: application/json' \
  http://100.66.226.12:8766/api/agent/brief -d '{"idempotency_key":"test-1","slot":"2026-10-02-morning","kind":"morning","text":"Test brief.","items":[],"links":[]}'
curl -s -m 5 "http://100.66.226.12:8766/api/agent/ping?key=x"     # PASS: 401 (query tokens refused)

# 7. Kill test: stop the model or the sandbox, then on the Mac:
#    ./alibi.sh say "status"                      -> still answers, instantly
#    curl -s -X POST 127.0.0.1:8765/api/digests/run -d '{"kind":"checkpoint"}' -H 'Content-Type: application/json'
#    PASS: a digest with "via":"rules" in under 2 s; /signals egress shows the summary "stays on Mac".
```

---

## 9. What Alibi does when the Spark or NemoClaw is down

| Feature | Spark up | Spark down | Time to fall back |
|---|---|---|---|
| Night replan | Tool loop on the Spark model, `via: llm:spark` (or `nemoclaw` if an agent brief arrives) | Rules picker: most-behind habit → first free gap tomorrow, `via: rules`. The same confirm card. | < 2 s (connect refused), otherwise a 45 s budget |
| Digest prose | Model prose after the rules text | Rules text only | Rules text is shown immediately; prose replaces it if it arrives |
| Ask | `via: nemoclaw` with HEAD-checked links | Raw model answer with no links, "No web results: NemoClaw is offline"; or `offline`. **No queued replay.** | Probe cached 60 s; < 4 s |
| Agent briefs | Shown above the rules brief | Rules brief only; Streams shows "agent last seen HH:MM" | — |
| Sessions, witness, verdicts, nudges, phone sync | Unaffected (never use the Spark) | Unaffected | — |
| Egress row on `/signals` | "Summary → Spark (tailnet)", active | "Stays on Mac" | Next 60 s probe |

The core loop (declare, witness, verify, verdict) never calls the Spark, and no request path waits on it.

---

## 10. Report back to the user (fill in, no secrets)

```
model_id:                 
server + port:            vLLM :8000 | Ollama :11434
bound to tailnet:         yes/no (address)
tool calling works:       yes/no (parser flag used)
thinking-off method:      chat_template_kwargs | /no_think | n/a
tokens/s (300-token reply):
nemoclaw version:         
gateway chatCompletions:  enabled/blocked (how; EACCES?)
gateway URL:              https://spark.<tailnet>.ts.net:8443  (serve on? yes/no)
web_search provider:      brave | duckduckgo | searxng | none
sandbox → Mac egress:     works / blocked (which guard)  → plan A or B for briefs
tokens handed over OOB:   NEMOCLAW_TOKEN yes/no ; ALIBI_AGENT_TOKEN received yes/no
open issues hit:          (#719/#2537 etc.)
```

## 11. Unverified facts in this document

These come from docs or issues and were not tested on this box:
- the model default (Qwen vLLM vs Nemotron Ollama);
- vLLM tool parser flags for this model;
- the Nemotron no-think switch;
- the `gateway.http.endpoints.chatCompletions.enabled` key path;
- the gateway token names;
- `model: "openclaw/default"`;
- the read-only `openclaw.json` (#719/#1699/#2537/#2544);
- `openshell forward start`;
- the need for `gateway.trustedProxies`;
- the `nemoclaw … cron` / `openclaw automations create` flags;
- the web provider and preset names;
- the SSRF guard's behaviour for non-MCP egress;
- MagicDNS inside the sandbox;
- `mcp add --trusted-private-host` and the header it emits.

**Verified from the Mac:**
- the Spark is on the tailnet at 100.76.35.21;
- nothing listens yet on 8000, 11434, 18789 or 8443;
- the Mac has no `tailscale serve` config.
