"""Phone / Apple Health uploads now live in alibi.integrations (the opt-in phone listener, Setup → iPhone).

The daemon runs it for you once you turn on iPhone sync. Standalone (e.g. on another box behind Tailscale):
  uvicorn alibi.webhook:app --host 0.0.0.0 --port 8766
"""
from .integrations import phone_app

app = phone_app()
