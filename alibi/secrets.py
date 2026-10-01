"""data/secrets.json — Strava keys/tokens and the phone-sync key. chmod 600, atomic writes, never in git.

    from alibi import secrets as store
    store.get("strava_client_id", env="STRAVA_CLIENT_ID")   # env var wins when set
    store.update(strava_refresh_token="...")                  # merge + write
"""
import json, os, threading
from . import config

_lock = threading.RLock()


def path():
    return config.DATA_DIR / "secrets.json"


def load() -> dict:
    try:
        with open(path()) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def get(key: str, default=None, env: str | None = None):
    if env and os.getenv(env):
        return os.getenv(env)
    return load().get(key, default)


def update(**kv) -> dict:
    """Merge kv into the store (value None deletes the key) and write it atomically with mode 600."""
    with _lock:
        d = load()
        for k, v in kv.items():
            if v is None:
                d.pop(k, None)
            else:
                d[k] = v
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".secrets.{os.getpid()}.{threading.get_ident()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(d, f, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
        return d
