"""Extension points so integrations live in their own files.

Each plugin module (if present) may define any of:
  start(con)                       once, when the daemon boots
  tick(con, now)                   every daemon tick (keep it cheap; rate-limit inside)
  on_session_start(con, session)   right after a session is created
  on_verdict(con, session)         right after a session is closed and scored (row has verdict/ratio/evidence)
and api.py includes `router` (a FastAPI APIRouter) from routes_<name>.py modules.
A plugin that raises never takes the daemon down.
"""
import importlib, traceback

PLUGINS = ("calendar_sync", "integrations", "onboarding")
ROUTES = ("routes_calendar", "routes_integrations", "routes_onboarding")


def _mods(names):
    for n in names:
        try:
            yield importlib.import_module(f"alibi.{n}")
        except ModuleNotFoundError as e:
            if e.name != f"alibi.{n}":
                traceback.print_exc()


def _call(fn_name: str, *args) -> None:
    for m in _mods(PLUGINS):
        fn = getattr(m, fn_name, None)
        if fn:
            try:
                fn(*args)
            except Exception as e:
                print(f"[alibi] plugin {m.__name__}.{fn_name} failed: {e!r}", flush=True)


def start(con): _call("start", con)
def tick(con, now): _call("tick", con, now)
def on_session_start(con, session): _call("on_session_start", con, session)
def on_verdict(con, session): _call("on_verdict", con, session)


def routers():
    for m in _mods(ROUTES):
        r = getattr(m, "router", None)
        if r is not None:
            yield r
