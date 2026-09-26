"""``/api/detector/*``: the thresholds the dashboard draws on the risk timeline."""

from fastapi import APIRouter

from gridline.threats.indices import BANDS, Bands

router = APIRouter(prefix="/detector", tags=["detector"])


@router.get("/bands")
async def get_bands() -> Bands:
    return BANDS
