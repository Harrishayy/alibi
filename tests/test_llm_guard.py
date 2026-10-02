"""A slow or misconfigured LLM can't stall Alibi, request paths never call it, a keyless Spark counts as ready,
and vision stays on the Mac unless asked. config/llm are module-level, so each case is its own subprocess."""
import os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from harness import ROOT, check

PY = sys.executable


class Sleepy(BaseHTTPRequestHandler):
    def do_POST(self):                      # a model server that never answers in time
        time.sleep(60)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), Sleepy)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
STUB = f"http://127.0.0.1:{srv.server_address[1]}/v1"


def run(code: str, **env) -> tuple[int, str, float]:
    # Every LLM/vision knob set explicitly ("" = unset): load_dotenv never overrides, so .env can't leak in.
    e = {**os.environ, "NVIDIA_API_KEY": "", "LLM_MODEL": "", "LLM_BASE_URL": "http://127.0.0.1:9/v1",
         "VLM_MODEL": "", "VLM_BASE_URL": "http://127.0.0.1:9/v1", "VISION_BACKEND": "", **env}
    t = time.monotonic()
    p = subprocess.run([PY, "-c", code], env=e, cwd=ROOT, capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout + p.stderr).strip(), time.monotonic() - t


# 1. Interactive call against a server that sleeps 60 s: falls back to rules in under 10 s.
rc, out, dt = run("""
from alibi import config, intent
assert config.TEXT_READY, 'stub should count as ready'
print(intent.parse('draw for 25 minutes'))
""", LLM_BASE_URL=STUB, LLM_MODEL="stub")
check(rc == 0 and "'habit': 'drawing'" in out and dt < 10, f"sleeping model -> rules fallback in {dt:.1f} s ({out[-120:]})")

# 2. build_json() 50 times, model 'ready': zero LLM calls. prose=True (nightly) still asks once.
rc, out, _ = run("""
from alibi import config, db, llm, report
assert config.TEXT_READY
calls = []
llm.chat_text = lambda *a, **k: calls.append(1) or 'model prose'
llm.chat_json = lambda *a, **k: calls.append(1) or {}
db.connect()
for _ in range(50):
    r = report.build_json()
print('calls', len(calls), 'summary_ok', bool(r['summary']))
print('nightly', report.build_json(prose=True)['summary'], len(calls))
""", LLM_BASE_URL=STUB, LLM_MODEL="stub")
check(rc == 0 and "calls 0 summary_ok True" in out, f"build_json x50 -> 0 LLM calls ({out[-120:]})")
check("nightly model prose 1" in out, "build_json(prose=True) -> 1 LLM call (nightly report)")

# 3. Keyless Spark: TEXT_READY from a non-NVIDIA base URL + model. NVIDIA Build still needs a real key.
probe = "from alibi import config; print(config.TEXT_READY)"
rc, out, _ = run(probe, LLM_BASE_URL="http://100.100.100.100:8000/v1", LLM_MODEL="x")
check(rc == 0 and out.endswith("True"), f"Spark URL + LLM_MODEL, no key -> TEXT_READY ({out[-60:]})")
rc, out, _ = run(probe, LLM_BASE_URL="https://integrate.api.nvidia.com/v1", LLM_MODEL="x")
check(rc == 0 and out.endswith("False"), "Build URL, no key -> not ready")
rc, out, _ = run(probe, LLM_BASE_URL="http://100.100.100.100:8000/v1", LLM_MODEL="<text model id>")
check(rc == 0 and out.endswith("False"), "placeholder LLM_MODEL -> not ready")

# 4. Vision stays local unless VISION_BACKEND is set explicitly.
probe = "from alibi import config; print(config.VISION_BACKEND)"
rc, out, _ = run(probe, NVIDIA_API_KEY="nvapi-" + "f" * 20, LLM_MODEL="x", VLM_MODEL="some/vlm")
check(rc == 0 and out.endswith("apple"), f"VLM_MODEL set, VISION_BACKEND unset -> apple ({out[-60:]})")
rc, out, _ = run(probe, VLM_MODEL="some/vlm", VISION_BACKEND="nvidia")
check(rc == 0 and out.endswith("nvidia"), "explicit VISION_BACKEND=nvidia is kept")
# Photo wording follows the witness (rule 5): only apple/mock may say photos stay on the Mac.
probe = "from alibi import config, onboarding; print(onboarding.state()['steps'][0]['text'])"
rc, out, _ = run(probe)
check(rc == 0 and "Photos stay on this Mac." in out, f"apple witness -> 'Photos stay on this Mac.' ({out[-60:]})")
rc, out, _ = run(probe, VISION_BACKEND="nvidia", VLM_MODEL="v", VLM_BASE_URL="https://integrate.api.nvidia.com/v1")
check(rc == 0 and "NVIDIA's model" in out and "stay on this Mac" not in out, f"Build witness -> no 'stay on this Mac' ({out[-60:]})")
rc, out, _ = run(probe, VISION_BACKEND="nvidia", VLM_MODEL="v", VLM_BASE_URL="http://100.100.100.100:8000/v1")
check(rc == 0 and "own model server" in out, "Spark witness -> 'your own model server'")

# 5. One-shot calls: thinking switch only off NVIDIA Build (Build calls keep each model's default).
rc, out, _ = run("from alibi import llm; print(llm._extra('https://integrate.api.nvidia.com/v1'), "
                 "bool(llm._extra('http://100.100.100.100:8000/v1')))")
check(rc == 0 and out.endswith("{} True"), f"enable_thinking=False only for non-NVIDIA hosts ({out[-60:]})")

# 6. The tool loop: Nemotron on Build gets thinking off (else a turn ends finish_reason=length with no tool call);
#    any other model on Build, or any non-NVIDIA host, gets exactly what _extra gives.
rc, out, _ = run("""
from alibi import llm
B, S, off = 'https://integrate.api.nvidia.com/v1', 'http://100.100.100.100:8000/v1', {'enable_thinking': False}
print(llm._tools_extra(B, 'nvidia/nemotron-3-super-120b-a12b') == {'extra_body': {'chat_template_kwargs': off}},
      llm._tools_extra(B, 'meta/llama-3.3-70b-instruct') == {}, llm._tools_extra(S, 'nemotron-3-nano') == llm._extra(S))
""")
check(rc == 0 and out.endswith("True True True"),
      f"_tools_extra: Nemotron on Build -> enable_thinking False; other model or host -> nothing added ({out[-60:]})")

srv.shutdown()
print("PASS test_llm_guard")
