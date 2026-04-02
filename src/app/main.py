from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.accounts import router as accounts_router
from app.api.routes.douyin_live_data import router as douyin_live_data_router
from app.api.routes.douyin_live_rooms import router as douyin_live_rooms_router
from app.api.routes.health import router as health_router
from app.api.routes.monitor import router as monitor_router
from app.config.settings import get_settings
from app.scheduler.runtime import SchedulerRuntime

settings = get_settings()
scheduler_runtime = SchedulerRuntime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler_runtime.start()
    try:
        yield
    finally:
        scheduler_runtime.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(accounts_router)
app.include_router(douyin_live_data_router)
app.include_router(douyin_live_rooms_router)
app.include_router(health_router)
app.include_router(monitor_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "message": "Monitoring service scaffold is ready.",
    }
