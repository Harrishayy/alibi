"""Digests over HTTP (mounted by api.py through hooks.routers()).

GET  /api/digests?limit=20          newest first: {digests: [{slot, kind, ts, sent, json, text, via, proposal?, trace?,
                                    accepted_at?, card?}]}
GET  /api/digests/latest?kind=      one row (+ card), or null
POST /api/digests/run {kind}        build one now (demo, tests); a re-run gets slot "<slot>-2", never overwrites.
                                    The row comes back with its card.
POST /api/digests/{slot}/accept     put the night proposal on the plan (calendar_sync.add_once) -> {ok, reply, block}
POST /api/digests/{slot}/undo       take it off again (calendar_sync.remove_once, accepted_at cleared) -> {ok, reply};
                                    404 unknown slot, 409 {ok: false, reply} when it isn't accepted

`card` (alibi/cards.py) is built per response on a copy of the row: the row on disk never changes shape.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from . import cards, digest

router = APIRouter()


def _with_card(r: dict | None) -> dict | None:
    """A copy of the row plus its card (omitted when there's none). Never mutates what digest.rows() returned."""
    if not isinstance(r, dict):
        return r
    out = dict(r)
    out.pop("card", None)
    c = cards.for_digest(r)
    if c:
        out["card"] = c
    return out


class Run(BaseModel):
    kind: str = "checkpoint"


@router.get("/api/digests")
def list_digests(limit: int = 20, kind: str | None = None):
    return {"digests": [_with_card(r) for r in digest.rows(max(1, min(limit, 200)), kind)]}


@router.get("/api/digests/latest")
def latest_digest(kind: str | None = None):
    return _with_card(digest.latest(kind))


@router.post("/api/digests/run")
def run_digest(body: Run):
    if body.kind not in digest.KINDS:
        raise HTTPException(400, f"kind must be one of {', '.join(digest.KINDS)}.")
    return _with_card(digest.run(body.kind))


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
