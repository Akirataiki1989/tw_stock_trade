"""app/worker.py — ARQ WorkerSettings + startup/shutdown hooks。

執行方式（NAS DSM SSH）：
    uv run arq app.worker.WorkerSettings
"""
import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agent.graph import build_graph, get_pg_url
from app.agent.memory import make_prod_checkpointer, make_prod_store
from app.core.config import settings
from app.services.fbs import fbs_client
from app.tasks import (
    task_cleanup_checkpoints,
    task_clear_intraday_candles,
    task_maybe_run_ai,
    task_prune_store_memories,
    task_sync_historical_candles,
    task_sync_institutional_flows,
    task_sync_instruments,
    task_sync_intraday_candles,
    task_sync_margin_trading,
    task_sync_quotes,
    task_sync_us_market,
    task_update_trade_outcomes,
)

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Worker 啟動時：登入 FBS + 建立 DB engine + 初始化 LangGraph 後端。"""
    try:
        fbs_client.connect()
        logger.info("Worker startup: FBS connected")
    except Exception as e:
        logger.warning("Worker startup: FBS unavailable (%s), continuing without FBS", e)
        logger.warning("Worker startup: FBS-dependent tasks will skip until reconnected")

    engine = create_async_engine(settings.database_url, pool_size=5)
    ctx["db_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["engine"] = engine

    pg_url = get_pg_url()

    ctx["checkpointer"] = await make_prod_checkpointer(pg_url)
    logger.info("Worker startup: AsyncPostgresSaver ready")

    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.gemini_api_key,
    )
    ctx["store"] = await make_prod_store(pg_url, embeddings.aembed_documents)
    logger.info("Worker startup: AsyncPostgresStore (pgvector) ready")
    logger.info("Worker startup complete")


async def shutdown(ctx: dict) -> None:
    """Worker 關閉時：清理所有資源。"""
    fbs_client.disconnect()
    checkpointer = ctx.get("checkpointer")
    if checkpointer and hasattr(checkpointer, "_cm"):
        try:
            await checkpointer._cm.__aexit__(None, None, None)
        except Exception:
            pass
    if "engine" in ctx:
        await ctx["engine"].dispose()
    logger.info("Worker shutdown complete")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    cron_jobs = [
        # ── Data sync ──────────────────────────────────────────────────────
        cron(task_sync_instruments,         hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_us_market,           hour=8,  minute=30, run_at_startup=False),
        cron(task_sync_quotes,              minute=set(range(60))),
        cron(task_sync_intraday_candles,    minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(task_sync_historical_candles,  hour=14, minute=0,  run_at_startup=False),
        cron(task_clear_intraday_candles,   hour=14, minute=30, run_at_startup=False),
        cron(task_sync_institutional_flows, hour=16, minute=0,  run_at_startup=False),
        cron(task_sync_margin_trading,      hour=16, minute=5,  run_at_startup=False),
        # ── AI Agent ───────────────────────────────────────────────────────
        cron(task_maybe_run_ai,             minute=set(range(60))),
        # ── Memory maintenance ─────────────────────────────────────────────
        cron(task_update_trade_outcomes,    hour=17, minute=0,  run_at_startup=False),
        cron(task_cleanup_checkpoints,      hour=3,  minute=0,  run_at_startup=False),
        cron(task_prune_store_memories,     hour=2,  minute=0,  weekday=6, run_at_startup=False),
    ]
    max_jobs = 10
    job_timeout = 300
