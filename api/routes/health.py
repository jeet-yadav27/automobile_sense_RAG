
from fastapi import APIRouter

from api.schemas import HealthResponse


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse
)
def health():
    return HealthResponse(
        status="ok",
        service="spresso-rag-api"
    )
