import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse

from app.api import api_router
from app.config import get_settings
from app.db import async_session_maker, init_models
from app.deps import require_csrf
from app.models import User
from app.security import generate_token, hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("vehrep")


async def bootstrap_admin() -> None:
    settings = get_settings()
    async with async_session_maker() as db:
        count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        if count:
            return
        password = settings.bootstrap_admin_password
        generated = False
        if not password:
            password = generate_token()[:14]
            generated = True
        admin = User(
            username=settings.bootstrap_admin_username,
            display_name="Administrator",
            role="admin",
            password_hash=hash_password(password),
            must_change_password=generated,
        )
        db.add(admin)
        await db.commit()
        banner = "=" * 64
        logger.info(
            "\n%s\nAdmin user created: %s\nPassword: %s%s\n%s",
            banner,
            admin.username,
            password,
            "\n(change it at first login)" if generated else "",
            banner,
        )


class SPAStaticFiles(StaticFiles):
    """Serve built frontend; unknown non-API paths fall back to index.html."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return self._index_response(exc)
        if response.status_code == 404 and not path.startswith("api/"):
            return self._index_response(None)
        return response

    def _index_response(self, exc):
        index = os.path.join(self.directory, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        if exc is not None:
            raise exc
        from starlette.responses import PlainTextResponse

        return PlainTextResponse("frontend not built", status_code=404)


def _static_dir() -> str | None:
    settings = get_settings()
    candidates = [
        settings.static_dir,
        str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"),
    ]
    for cand in candidates:
        if cand and os.path.isdir(cand) and os.path.exists(os.path.join(cand, "index.html")):
            return cand
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.email import reschedule_email_job, start_scheduler, stop_scheduler

    if get_settings().automigrate:
        await init_models()
    await bootstrap_admin()
    start_scheduler()
    await reschedule_email_job()
    logger.info("Vehicle Report v2 started (env=%s)", get_settings().app_env)
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api", dependencies=[Depends(require_csrf)])

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "version": settings.version}

    static = _static_dir()
    if static:
        app.mount("/", SPAStaticFiles(directory=static, html=True), name="static")
        logger.info("Serving frontend from %s", static)
    return app


app = create_app()
