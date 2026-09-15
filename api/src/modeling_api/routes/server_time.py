"""Server clock used to timestamp browser-side model patches."""

from datetime import datetime

from fastapi import APIRouter

from modeling_api.db.store import utcnow

router = APIRouter(tags=["Server time"])


@router.get("/time", summary="Aktuelle Serverzeit liefern")
async def get_server_time() -> dict[str, datetime]:
    return {"serverTime": utcnow()}
