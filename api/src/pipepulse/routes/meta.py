from fastapi import APIRouter
from pydantic import BaseModel

from pipepulse.deps import SettingsDep

router = APIRouter(prefix="/api", tags=["meta"])


class Meta(BaseModel):
    demo_mode: bool


@router.get("/meta")
async def meta(settings: SettingsDep) -> Meta:
    """Instance facts the dashboard needs, e.g. to label generated demo data."""
    return Meta(demo_mode=settings.demo_mode)
