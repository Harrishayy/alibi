# Alibi on the DGX Spark (NemoClaw)

The Mac is still the hub: camera, window titles, the notch island and the session database live there. The DGX
Spark adds the always-on agent: OpenClaw running inside a NemoClaw / OpenShell sandbox, talking to the Mac over
Tailscale through one narrow door.

## Models (all Nemotron)

| Role | Model | Where |
|---|---|---|
| Agent (OpenClaw driver) | `nvidia/nemotron-3-super-120b-a12b` | NVIDIA Build, via NemoClaw's `inference.local` route (key stays on the host) |
| Agent, fully local mode (not working yet) | Nemotron 3 Nano 30B-A3B (`UD-Q4_K_XL` GGUF, NemoClaw's managed llama.cpp Spark profile), sandbox `alibi-local` (stopped) | DGX Spark |
| Camera witness (video) | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | NVIDIA Build, called by the Mac daemon (`VLM_VIDEO=1`) |

Local mode status (2026-10-01): the model serves, but the managed llama.cpp recipe caps requests at 32 KB
(`maxRequestBodyBytes`), and OpenClaw's multi-step requests exceed that after one or two tool calls (HTTP 413).
Next step: an operator-run llama.cpp/vLLM server without the cap (NemoClaw "existing server" path).

Same skill, relay and tools in every mode; only the model route changes:
`nemoclaw inference set --model <model> --provider <provider> --sandbox alibi`.
With Omni on Build, camera clips leave your network. Say so.

```
 iPhone ──(Health, Tailscale)──┐
                               ▼
 MacBook  ─ Alibi daemon :8765 (camera, windows, verifier, island, SQLite)
   ▲  │        ▲ bearer ALIBI_REMOTE_TOKEN, tailnet only
   │  │        │
   │  │   ┌────┴──────────────── DGX Spark ───────────────────────────────────┐
   │  │   │ alibi.relay :8770  (systemd --user)                                │
   │  │   │   mirrors /api/state + /api/feed every 20 s -> data/relay/*.jsonl  │
   │  │   │   allow-listed API for the agent; Mac token stays on the host      │
   │  │   │        ▲ docker bridge only, egress policy "alibi-relay"           │
   │  │   │  ┌─────┴── OpenShell sandbox "alibi" (deny-by-default egress) ──┐  │
   │  │   │  │ OpenClaw agent · skill `alibi` · HEARTBEAT.md every 30 min   │  │
   │  │   │  │ memory/alibi.md (verdict history)                            │  │
   │  │   │  └─────┬────────────────────────────────────────────────────────┘  │
   │  │   │        ▼ inference.local (OpenShell route, key never in sandbox)   │
   │  │   │  vLLM (local, NemoClaw-managed)                                    │
   │  └──────────────► /v1 via relay (RELAY_TOKEN) — the Mac's witness can use it│
   │      └────────────────────────────────────────────────────────────────────┘
   └── OpenClaw web UI over Tailscale (you)
```

## What runs where

| Piece | Where | Started by |
|---|---|---|
| Alibi daemon + island | Mac | `./alibi.sh up` (Alibi.app) |
| `alibi.relay` | Spark host | `systemctl --user` unit `alibi-relay` (installed by `scripts/spark_setup.sh`) |
| OpenClaw agent | Spark, OpenShell sandbox `alibi` | NemoClaw (`nemoclaw alibi status`) |
| Local model | Spark, NemoClaw-managed vLLM | NemoClaw onboarding |

## Setup (Spark)

```bash
# once: Docker access, NemoClaw CLI, then onboard the sandbox on Nemotron 3 Super (key read from .env, never echoed)
sudo usermod -aG docker $USER
curl -fsSL https://www.nvidia.com/nemoclaw.sh | NEMOCLAW_DEFER_ONBOARDING=1 bash
set -a; . ./.env; set +a; NVIDIA_INFERENCE_API_KEY="$NVIDIA_API_KEY" NEMOCLAW_PROVIDER=build \
  NEMOCLAW_MODEL=nvidia/nemotron-3-super-120b-a12b NEMOCLAW_AGENT=openclaw NEMOCLAW_AGENT_HEARTBEAT_EVERY=30m \
  nemoclaw onboard --non-interactive --fresh --name alibi --yes-i-accept-third-party-software --yes
# then, and after any change to spark/ or the relay:
bash scripts/spark_setup.sh
```

`spark_setup.sh` writes `MAC_URL`, `ALIBI_REMOTE_TOKEN` and `RELAY_TOKEN` into the Spark's `.env` (generated, never
printed), installs and starts the relay, applies the `alibi-relay` egress preset, installs the `alibi` skill and
uploads `HEARTBEAT.md`.

## Setup (Mac)

Add to the Mac's `.env`, then `./alibi.sh down && ./alibi.sh up`:

```
API_HOST=0.0.0.0
ALIBI_REMOTE_TOKEN=<same value as on the Spark>
ALIBI_ALLOWED_HOSTS=127.0.0.1,localhost,::1,harrishs-macbook-pro,100.66.226.12
```

Video witness on Nemotron 3 Nano Omni (Mac `.env`, needs the Mac's own `NVIDIA_API_KEY`):

```
VLM_MODEL=nvidia/nemotron-3-nano-omni-30b-a3b-reasoning
VLM_VIDEO=1          # judge each minute as a timelapse clip; VLM_THINK=1 (default) lets it reason first, ~15 s/clip
```

Optional — point the Mac's models at a local server on the Spark instead of NVIDIA Build:

```
LLM_BASE_URL=http://spark:8770/v1
VLM_BASE_URL=http://spark:8770/v1
NVIDIA_API_KEY=<RELAY_TOKEN from the Spark>
LLM_MODEL=<served model id>      # nemoclaw alibi status shows it
VLM_MODEL=<served model id, if it accepts images>
```

## Security model

- **The sandbox can reach exactly one thing besides inference**: the relay, on the Docker bridge, eight
  method + path pairs, `curl` only (`spark/policy-alibi-relay.yaml`). Everything else is denied by OpenShell.
- **The Mac's token never enters the sandbox.** The relay holds it on the host.
- **The Mac refuses tailnet callers without the token** (`alibi/api.py` `_remote_auth`); with no token set it stays
  loopback-only, as before. `/ingest` keeps its own `X-Alibi-Secret`.
- **Tailnet callers to the relay need `RELAY_TOKEN`**; the `/v1` model proxy always does, even from the bridge.
- **Privacy:** with the Mac's witness pointed at the Spark, frames leave the Mac but stay on your tailnet. Say
  "frames never leave your network", not "never leave the Mac".

## Checks

```bash
.venv/bin/python tests/test_relay.py                 # hermetic: guard, mirror, stale fallback, outage record
systemctl --user status alibi-relay
curl -s http://$(docker network inspect openshell-docker -f '{{(index .IPAM.Config 0).Gateway}}'):8770/status
nemoclaw alibi exec -- openclaw agent --agent main -m "How am I doing on Alibi?"
nemoclaw alibi dashboard-url --quiet                  # OpenClaw web UI
```
