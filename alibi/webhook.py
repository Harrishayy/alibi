"""P6 (stretch) — POST /ingest from iOS Shortcuts (Focus on/off, nightly Health samples).

  uvicorn alibi.webhook:app --host 0.0.0.0 --port 8787   # run on the Spark, reach it over Tailscale
"""
# TODO (P6):
#   FastAPI app; POST /ingest {source: phone|health, kind, payload} -> db.add_event(...)
#   check a shared secret header so only your phone can post
