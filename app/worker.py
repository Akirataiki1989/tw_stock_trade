"""app/worker.py — ARQ WorkerSettings + startup/shutdown hooks。

執行方式（NAS DSM SSH）：
    uv run arq app.worker.WorkerSettings
"""
import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.services.fbs import fbs_client
from app.tasks import (
    task_clear_intraday_candles,
    task_sync_historical_candles,
    task_sync_institutional_flows,
    task_sync_instruments,
    task_sync_intraday_candles,
    task_sync_margin_trading,
    task_sync_quotes,
    task_sync_us_market,
)

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Worker 啟動時：登入 FBS + 建立 DB engine。"""
    try:
        fbs_client.connect()
        logger.info("Worker started: FBS connected")
    except RuntimeError as e:
        logger.critical("Worker startup failed: FBS login error - %s", e)
        raise  # 讓 ARQ 感知，終止 Worker

    engine = create_async_engine(settings.database_url, pool_size=5)
    ctx["db_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["engine"] = engine
    logger.info("Worker startup complete")


async def shutdown(ctx: dict) -> None:
    """Worker 關閉時：清理資源。"""
    fbs_client.disconnect()
    if "engine" in ctx:
        await ctx["engine"].dispose()
    logger.info("Worker shutdown complete")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        cron(task_sync_instruments,          hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_us_market,            hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_quotes,               minute=set(range(60))),
        cron(task_sync_intraday_candles,     minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(task_sync_historical_candles,   hour=14, minute=0,  run_at_startup=False),
        cron(task_clear_intraday_candles,    hour=14, minute=30, run_at_startup=False),
        cron(task_sync_institutional_flows,  hour=16, minute=0,  run_at_startup=False),
        cron(task_sync_margin_trading,       hour=16, minute=5,  run_at_startup=False),
    ]
    max_jobs = 10
    job_timeout = 300  # 5 分鐘，避免 task 卡住
