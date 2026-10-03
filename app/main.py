from fastapi import FastAPI

from app.core.config import settings
from app.api.router import api_router


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Ticketing platform modular monolith.",
    root_path="/api",
)

app.include_router(
    api_router,
    prefix="/v1",
)


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "ok",
        "service": "ticketing-monolith",
    }