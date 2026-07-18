from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "service": "loyalyn-api", "version": settings.app_version}
