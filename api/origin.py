
from fastapi import Request
from fastapi.responses import JSONResponse

ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}


async def validate_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")

        # Require an approved Origin on browser-facing
        # state-changing endpoints.
        if origin not in ALLOWED_ORIGINS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Untrusted request origin"},
            )

    return await call_next(request)
