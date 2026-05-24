"""app/tasks.py — ARQ cron task 函式與共用 helper。

所有 cron task 接收 ARQ 提供的 ctx: dict，從中取得 db_factory（async_sessionmaker）。
"""
import logging
import traceback as tb
from datetime import datetime, time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

# ── 自訂 TRACE 層級（level=5，低於 DEBUG=10）────────────────────────────────

TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(self, msg, *args, **kwargs):  # type: ignore[override]
    if self.isEnabledFor(TRACE):
        self._log(TRACE, msg, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]

# ── logger ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── helper 函式 ────────────────────────────────────────────────────────────────

_TZ = ZoneInfo("Asia/Taipei")


def is_trading_hours() -> bool:
    """台股交易時間：週一至週五 09:00–13:30（台北時間）。"""
    now = datetime.now(_TZ)
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    return time(9, 0) <= now.time() <= time(13, 30)


async def get_watch_symbols(db: AsyncSession) -> list[str]:
    """查詢 holdings ∪ watchlist 的 symbol 清單（SQL UNION 自動去重）。"""
    result = await db.execute(
        text("""
            SELECT symbol FROM trading.holdings
            UNION
            SELECT symbol FROM trading.watchlist
        """)
    )
    return [row[0] for row in result.fetchall()]
