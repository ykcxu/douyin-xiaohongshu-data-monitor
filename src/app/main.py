from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.config.settings import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "message": "Monitoring service scaffold is ready.",
    }
