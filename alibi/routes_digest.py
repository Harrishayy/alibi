"""F5 digests over HTTP (mounted by api.py through hooks.routers()).

GET  /api/digests?limit=20          newest first: {digests: [{slot, kind, ts, sent, json, text, via, proposal?, trace?,
                                    accepted_at?}]}
GET  /api/digests/latest?kind=      one row, or null
POST /api/digests/run {kind}        build one now (demo, tests); a re-run gets slot "<slot>-2", never overwrites
POST /api/digests/{slot}/accept     put the night proposal on the plan (calendar_sync.add_once) -> {ok, reply, block}
POST /api/digests/{slot}/undo       take it off again (calendar_sync.remove_once, accepted_at cleared) -> {ok, reply};
                                    404 unknown slot, 409 {ok: false, reply} when it isn't accepted
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from . import digest

router = APIRouter()


class Run(BaseModel):
    kind: str = "checkpoint"


@router.get("/api/digests")
def list_digests(limit: int = 20, kind: str | None = None):
    return {"digests": digest.rows(max(1, min(limit, 200)), kind)}


@router.get("/api/digests/latest")
def latest_digest(kind: str | None = None):
    return digest.latest(kind)


@router.post("/api/digests/run")
def run_digest(body: Run):
    if body.kind not in digest.KINDS:
        raise HTTPException(400, f"kind must be one of {', '.join(digest.KINDS)}.")
    return digest.run(body.kind)


@router.post("/api/digests/{slot}/accept")
def accept_digest(slot: str):
    try:
        return digest.accept(slot)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/digests/{slot}/undo")
def undo_digest(slot: str):
    try:
        return digest.undo(slot)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except digest.NotAccepted as e:
        return JSONResponse({"ok": False, "reply": str(e)}, status_code=409)
