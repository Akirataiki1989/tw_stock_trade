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


# ── task_sync_instruments ────────────────────────────────────────────────────

async def test_task_sync_instruments_calls_fbs(monkeypatch):
    """task_sync_instruments 呼叫 fbs_client.sync_instruments(db)。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    mock_sync = AsyncMock(return_value=5)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_instruments", mock_sync)

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    ctx = {"db_factory": mock_db_factory}
    await tasks_module.task_sync_instruments(ctx)

    mock_sync.assert_called_once_with(mock_db)


# ── task_sync_quotes ─────────────────────────────────────────────────────────

async def test_task_sync_quotes_skip_outside_hours(monkeypatch):
    """非交易時間 → 直接 return，不查 DB 也不呼叫 FBS。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: False)
    mock_db_factory = MagicMock()
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_quotes(ctx)

    mock_db_factory.assert_not_called()


async def test_task_sync_quotes_skip_market_closed(monkeypatch):
    """交易時間內但 isClose=True → 跳過，不同步。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: True)
    monkeypatch.setattr(
        tasks_module.fbs_client, "fetch_quote",
        AsyncMock(return_value={"isClose": True})
    )

    mock_db_factory = MagicMock()
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_quotes(ctx)

    mock_db_factory.assert_not_called()


async def test_task_sync_quotes_syncs_all_symbols(monkeypatch):
    """正常盤中：對每個 symbol 呼叫一次 sync_quote。"""
    from unittest.mock import AsyncMock, MagicMock, call
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: True)
    monkeypatch.setattr(
        tasks_module.fbs_client, "fetch_quote",
        AsyncMock(return_value={"isClose": False})
    )
    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330", "2317"]))

    mock_sync = AsyncMock(return_value=True)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_quote", mock_sync)

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_quotes(ctx)

    assert mock_sync.call_count == 2
    mock_sync.assert_any_call(mock_db, "2330")
    mock_sync.assert_any_call(mock_db, "2317")


# ── task_sync_intraday_candles ────────────────────────────────────────────────

async def test_task_sync_intraday_candles_skip_outside_hours(monkeypatch):
    """非交易時間 → 跳過。"""
    from unittest.mock import MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: False)
    mock_db_factory = MagicMock()
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_intraday_candles(ctx)

    mock_db_factory.assert_not_called()


async def test_task_sync_intraday_candles_uses_tf5(monkeypatch):
    """盤中 → 以 timeframe='5' 呼叫 sync_intraday_candles。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "is_trading_hours", lambda: True)
    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=12)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_intraday_candles", mock_sync)

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_intraday_candles(ctx)

    mock_sync.assert_called_once_with(mock_db, "2330", "5")


# ── task_sync_historical_candles ──────────────────────────────────────────────

async def test_task_sync_historical_candles_initial_load(monkeypatch):
    """首次載入（DB 無資料）→ 補抓 2 年（可能分兩次查）。"""
    from datetime import date, timedelta
    from unittest.mock import AsyncMock, MagicMock, call
    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=50)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_historical_candles", mock_sync)

    # DB scalar 回傳 None → 首次載入
    mock_db = AsyncMock()
    mock_db.scalar.return_value = None
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_historical_candles(ctx)

    # 2 年 = 730 天 > 365 天限制 → 一定拆兩次
    assert mock_sync.call_count == 2

    # 第一次 from_date 距今 ≥ 729 天
    first_call_from = mock_sync.call_args_list[0].args[3]
    assert (date.today() - first_call_from).days >= 729


async def test_task_sync_historical_candles_incremental(monkeypatch):
    """增量同步：last_date 為昨天 → 只查今天一筆。"""
    from datetime import date, timedelta
    from unittest.mock import AsyncMock, MagicMock

    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=1)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_historical_candles", mock_sync)

    yesterday = date.today() - timedelta(days=1)
    mock_db = AsyncMock()
    mock_db.scalar.return_value = yesterday  # last_date = 昨天
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_historical_candles(ctx)

    # from_date = yesterday + 1 = today → 只呼叫一次
    assert mock_sync.call_count == 1
    call_args = mock_sync.call_args
    assert call_args.args[3] == date.today()
    assert call_args.args[4] == date.today()


async def test_task_sync_historical_candles_up_to_date(monkeypatch):
    """last_date = 今天 → 已是最新，不呼叫 sync。"""
    from datetime import date
    from unittest.mock import AsyncMock, MagicMock

    import app.tasks as tasks_module

    monkeypatch.setattr(tasks_module, "get_watch_symbols", AsyncMock(return_value=["2330"]))

    mock_sync = AsyncMock(return_value=0)
    monkeypatch.setattr(tasks_module.fbs_client, "sync_historical_candles", mock_sync)

    mock_db = AsyncMock()
    mock_db.scalar.return_value = date.today()  # last_date = 今天
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_sync_historical_candles(ctx)

    mock_sync.assert_not_called()


# ── task_clear_intraday_candles ───────────────────────────────────────────────

async def test_task_clear_intraday_candles_executes_delete(monkeypatch):
    """task_clear_intraday_candles 呼叫 DELETE FROM market.intraday_candles 並 commit。"""
    from unittest.mock import AsyncMock, MagicMock
    import app.tasks as tasks_module

    mock_db = AsyncMock()
    mock_db_factory = MagicMock()
    mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": mock_db_factory}

    await tasks_module.task_clear_intraday_candles(ctx)

    mock_db.execute.assert_called_once()
    # 確認 SQL 包含 DELETE
    executed_sql = str(mock_db.execute.call_args.args[0])
    assert "DELETE" in executed_sql.upper() or "delete" in executed_sql
    mock_db.commit.assert_called_once()





