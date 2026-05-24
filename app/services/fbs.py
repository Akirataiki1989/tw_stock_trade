"""FBS Fubon Neo SDK 封裝。

使用方式：
    from app.services.fbs import fbs_client

    # ARQ on_startup
    fbs_client.connect()

    # ARQ task
    await fbs_client.sync_quote(db, "2330")

    # FastAPI endpoint
    quote = await fbs_client.fetch_quote("2330")
"""

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any

from fubon_neo.adapter import build_rest_client
from fubon_neo.sdk import FubonSDK
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.market import HistoricalCandle, Instrument, IntradayCandle, MarketQuote

logger = logging.getLogger(__name__)


class FbsClient:
    """FBS SDK singleton 封裝。

    在 ARQ Worker on_startup 呼叫 connect()；
    所有 sync_* / fetch_* 方法供 Worker 任務與 FastAPI endpoint 使用。
    """

    def __init__(self) -> None:
        self._sdk: FubonSDK | None = None
        self._rest: Any | None = None

    # ── 連線管理 ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """登入 FBS SDK，建立 REST client。登入失敗拋 RuntimeError。"""
        sdk = FubonSDK()
        accounts = sdk.login(settings.fbs_account, settings.fbs_password, settings.fbs_cert_path)
        if not accounts.is_success:
            raise RuntimeError("FBS login failed")
        token = sdk.exchange_realtime_token()
        self._sdk = sdk
        self._rest = build_rest_client(token)
        logger.info("FBS connected, account: %s", accounts.data[0].account)

    def disconnect(self) -> None:
        """清除 SDK 連線狀態（SDK 無明確 logout API）。"""
        self._sdk = None
        self._rest = None
        logger.info("FBS disconnected")

    def is_connected(self) -> bool:
        return self._sdk is not None and self._rest is not None

    # ── 背景同步（存 DB）────────────────────────────────────────────────────

    async def sync_instruments(self, db: AsyncSession) -> int:
        """從 FBS 拉取全部股票清單，批次 upsert 到 market.instruments。

        Returns:
            寫入（新增 + 更新）的筆數。
        """
        raw: dict = await asyncio.to_thread(
            self._rest.stock.intraday.tickers, type="EQUITY"
        )
        rows: list[dict] = raw.get("data", [])
        if not rows:
            logger.warning("sync_instruments: FBS returned empty ticker list")
            return 0

        values = [
            {
                "symbol": r["symbol"],
                "name": r.get("name"),
                "industry": r.get("industry"),
            }
            for r in rows
        ]

        stmt = pg_insert(Instrument).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "industry": stmt.excluded.industry,
                "last_synced": func.now(),
            },
        )
        await db.execute(stmt)
        await db.commit()
        logger.info("sync_instruments: upserted %d instruments", len(values))
        return len(values)



# 模組層級 singleton — ARQ Worker 與 FastAPI endpoint import 這個
fbs_client = FbsClient()
