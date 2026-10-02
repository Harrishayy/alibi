# Alibi on the DGX Spark (NemoClaw)

The Mac is the hub and owns the truth: camera, window titles, the notch island, sessions and verdicts. The DGX
Spark runs the always-on agent: OpenClaw inside a NemoClaw / OpenShell sandbox. It reads Alibi's context and writes
briefs, and it can't start, stop or change anything. How it works: [AGENT.md](AGENT.md) (agent API, jobs, egress).

```
 MacBook  ─ Alibi daemon: :8765 dashboard (loopback only) · :8766 phone + agent API (tailnet only)
              ▲  X-Alibi-Agent-Token (nemoclaw_token): GET ping/context/digests, POST brief
              │  Tailscale
 ┌────────────┴────────────────── DGX Spark ─────────────────────────────────────────┐
 │ alibi.relay :8770 (systemd --user): holds the agent token, mirrors context and    │
 │   digests every 20 s into data/relay/, adds slot_hint (London time)               │
 │        ▲ Docker bridge only; egress preset "alibi-relay": GET status/context/     │
 │        │ digests, POST brief, curl only                                           │
 │  ┌─────┴── OpenShell sandbox "alibi" (deny-by-default egress) ──────────────────┐ │
 │  │ OpenClaw · skill `alibi` · cron: morning 07:32, checkpoints 12:02/16:02/20:02,│ │
 │  │ night 22:05 (Europe/London) · heartbeat 30 min (risk briefs) · memory/alibi.md│ │
 │  └─────┬────────────────────────────────────────────────────────────────────────┘ │
 │        ▼ inference.local (OpenShell route; the NVIDIA key never enters the sandbox)│
 └────────┼──────────────────────────────────────────────────────────────────────────┘
          ▼ NVIDIA Build: nvidia/nemotron-3-super-120b-a12b
```

## Models (all Nemotron)

| Role | Model | Called by |
|---|---|---|
| Agent (writes the briefs) | `nvidia/nemotron-3-super-120b-a12b` on NVIDIA Build | OpenClaw in the sandbox, via NemoClaw's `inference.local` |
| Night replan tool loop, digest prose | same, on Build (`LLM_BASE_URL=https://integrate.api.nvidia.com/v1`) | the Mac directly; tagged `llm:build` |
| Camera witness (video, opt-in) | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` on Build | the Mac (`VISION_BACKEND=nvidia VLM_VIDEO=1`) |

With the Omni witness on, one-minute camera clips go to NVIDIA. Say so; the default witness (Apple Vision) keeps
frames on the Mac.

Local mode is not supported yet: NemoClaw's managed llama.cpp recipe caps requests at 32 KB and OpenClaw's tool loop
exceeds that (HTTP 413), so a local Nemotron 3 Nano 30B-A3B needs an operator-run server without the cap.
**Gotcha:** an OpenShell gateway has ONE inference route shared by every sandbox; onboarding a second sandbox on
another model silently repoints the first. Switch with `nemoclaw inference set`, don't add sandboxes.

## Setup

Spark, once:
```bash
sudo usermod -aG docker $USER
curl -fsSL https://www.nvidia.com/nemoclaw.sh | NEMOCLAW_DEFER_ONBOARDING=1 bash
set -a; . ./.env; set +a; NVIDIA_INFERENCE_API_KEY="$NVIDIA_API_KEY" NEMOCLAW_PROVIDER=build \
  NEMOCLAW_MODEL=nvidia/nemotron-3-super-120b-a12b NEMOCLAW_AGENT=openclaw NEMOCLAW_AGENT_HEARTBEAT_EVERY=30m \
  nemoclaw onboard --non-interactive --fresh --name alibi --yes-i-accept-third-party-software --yes
```
Then put the Mac's agent token in the Spark's `.env` as `ALIBI_AGENT_TOKEN` (it's `nemoclaw_token` in the Mac's
`data/secrets.json`, created the first time the agent API is used; hand it over out of band) and run
`MAC_HOST=<your-mac>.<tailnet>.ts.net bash scripts/spark_setup.sh` (the Mac's tailnet name or IP; it is saved to
`.env` as `MAC_URL`). It installs the relay service, the egress preset, the skill, the heartbeat checklist
and the three cron jobs. The first `openclaw cron add` asks for an `operator.admin` scope for the sandbox's own CLI:
approve it with `nemoclaw alibi exec -- openclaw devices approve <requestId>`.

To bring the agent back by itself after a reboot or a crash, install the keep-alive timer:
`bash spark/keepalive/install.sh` ([AGENT.md](AGENT.md#staying-up)).

Mac: turn on iPhone sync (the :8766 listener). Nothing else changes; :8765 stays loopback-only.

## Checks

```bash
.venv/bin/python tests/test_relay.py      # agent API rules (source, token, no query tokens, 16 KB, idempotency,
                                          # no session writes) + relay mirror, stale fallback, outage record
systemctl --user status alibi-relay
nemoclaw alibi exec -- openclaw cron list
nemoclaw alibi exec -- openclaw cron run <night-job-id>     # posts a brief now
nemoclaw alibi dashboard-url --quiet                        # OpenClaw web UI (Spark loopback)
```

## Tested with

NemoClaw v0.0.124, OpenClaw 2026.7.1, OpenShell 0.0.116, with Nemotron 3 Super on NVIDIA Build through
`inference.local` (nothing serves a model on the Spark itself). The sandbox reaches the Mac only through the relay;
the night job posting a brief that the Mac stores and shows as the agent's was checked end to end against a
stand-in Mac.

Known limits: the managed llama.cpp 32 KB request cap (HTTP 413) blocks local mode; an OpenShell gateway has one
inference route shared by every sandbox; the first `openclaw cron add` needs an `operator.admin` scope approval.
