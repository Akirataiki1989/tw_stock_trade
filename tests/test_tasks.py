"""tests/test_tasks.py — ARQ task helpers 單元測試。"""
from datetime import datetime
from unittest.mock import patch

from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")


# ── is_trading_hours ────────────────────────────────────────────────────────

def _patch_now(dt_str: str):
    """回傳 patch context manager，將 tasks.py 內 datetime.now 固定為 dt_str。"""
    dt = datetime.fromisoformat(dt_str).replace(tzinfo=TZ)
    return patch("app.tasks.datetime")


def test_trading_hours_weekday_inside():
    """週一 09:15 → True。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 9, 15, tzinfo=TZ)   # 2026-05-25 is Monday
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is True


def test_trading_hours_weekday_before_open():
    """週一 08:59 → False。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 8, 59, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is False


def test_trading_hours_weekday_after_close():
    """週一 13:31 → False。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 13, 31, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is False


def test_trading_hours_weekend():
    """週六 10:00 → False。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 23, 10, 0, tzinfo=TZ)   # 2026-05-23 is Saturday
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is False


def test_trading_hours_boundary_open():
    """09:00 整點 → True（邊界含）。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 9, 0, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is True


def test_trading_hours_boundary_close():
    """13:30 整點 → True（邊界含）。"""
    from app.tasks import is_trading_hours
    dt = datetime(2026, 5, 25, 13, 30, tzinfo=TZ)
    with patch("app.tasks.datetime") as mock_dt:
        mock_dt.now.return_value = dt
        assert is_trading_hours() is True


# ── get_watch_symbols ────────────────────────────────────────────────────────

async def test_get_watch_symbols_dedup():
    """holdings 與 watchlist 有重複 symbol 時，回傳去重後的清單。"""
    from unittest.mock import AsyncMock, MagicMock
    from app.tasks import get_watch_symbols

    # DB execute 回傳兩次，模擬 UNION 結果（已去重）
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("2330",), ("2317",), ("0050",)]
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    symbols = await get_watch_symbols(mock_db)

    assert symbols == ["2330", "2317", "0050"]
    mock_db.execute.assert_called_once()


async def test_get_watch_symbols_empty():
    """holdings 與 watchlist 都空時，回傳空 list。"""
    from unittest.mock import AsyncMock, MagicMock
    from app.tasks import get_watch_symbols

    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    symbols = await get_watch_symbols(mock_db)

    assert symbols == []
