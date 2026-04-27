from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import install_handlers
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.redis import close_redis
from app.routers.admin import router as admin_router
from app.routers.public import router as public_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="wangyang.dev API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_handlers(app)

    app.include_router(public_router)
    app.include_router(admin_router)

    media_dir = settings.data_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir), check_dir=False), name="media")

    return app


app = create_app()
