"""Сборка приложения: единственное место, где слои встречаются."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastmcp.utilities.lifespan import combine_lifespans

from ..config import settings
from ..db import create_pool, migrate
from ..mcp.server import build_mcp_app
from .routes import router

log = logging.getLogger(__name__)

# Собранный Vite кладёт сюда bundle. Отдельного nginx нет: статики один
# каталог, и лишний контейнер ради него только добавил бы точку отказа.
STATIC_DIR = Path(__file__).resolve().parent / "static"

MINIAPP_PATH = "/app"


def create_app() -> FastAPI:
    cfg = settings()
    if not cfg.database_url:
        raise RuntimeError("DATABASE_URL пуст: API без базы не поднимается")

    logging.basicConfig(
        level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    mcp_app = build_mcp_app(cfg)

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        app.state.pool = await create_pool(cfg.database_url)
        # Миграции накатываются здесь, а не отдельным сервисом compose:
        # процесс один, гонки за блокировку нет.
        await migrate(app.state.pool)
        try:
            yield
        finally:
            await app.state.pool.close()

    app = FastAPI(
        title="vocab",
        # Без lifespan самого mcp_app его менеджер сессий не инициализируется
        # и /mcp отвечает ошибкой на первом же запросе.
        lifespan=combine_lifespans(app_lifespan, mcp_app.lifespan),
    )

    # Букмарклет исполняется на произвольной странице, расширение — со своего
    # origin. Оба присылают X-Token заголовком, не куки, поэтому «*» здесь
    # ничего не открывает: без токена запрос всё равно получит 401.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Token", "X-Init-Data", "X-Tg-Id"],
    )

    app.include_router(router)
    app.mount("/mcp", mcp_app)

    if STATIC_DIR.is_dir():
        # html=True отдаёт index.html на неизвестный путь внутри /app —
        # мини-апп открывается по прямой ссылке, а не только с корня.
        app.mount(MINIAPP_PATH, StaticFiles(directory=STATIC_DIR, html=True), name="miniapp")

        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse(MINIAPP_PATH + "/")
    else:
        log.warning("каталог статики %s отсутствует, мини-апп не отдаётся", STATIC_DIR)

    return app


app = create_app()
