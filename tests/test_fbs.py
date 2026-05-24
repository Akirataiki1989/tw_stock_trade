import pytest
from unittest.mock import MagicMock, patch

from app.services.fbs import FbsClient


# ── connect ────────────────────────────────────────────────────────────────


def test_connect_success():
    """登入成功時 is_connected() 回傳 True。"""
    mock_sdk = MagicMock()
    mock_accounts = MagicMock()
    mock_accounts.is_success = True
    mock_accounts.data = [MagicMock()]
    mock_sdk.login.return_value = mock_accounts
    mock_sdk.exchange_realtime_token.return_value = "fake-token"

    with (
        patch("app.services.fbs.FubonSDK", return_value=mock_sdk),
        patch("app.services.fbs.build_rest_client", return_value=MagicMock()),
    ):
        c = FbsClient()
        c.connect()

    assert c.is_connected() is True


def test_connect_login_failure_raises():
    """登入失敗時 connect() 拋 RuntimeError。"""
    mock_sdk = MagicMock()
    mock_accounts = MagicMock()
    mock_accounts.is_success = False
    mock_sdk.login.return_value = mock_accounts

    with (
        patch("app.services.fbs.FubonSDK", return_value=mock_sdk),
        patch("app.services.fbs.build_rest_client", return_value=MagicMock()),
        pytest.raises(RuntimeError, match="FBS login failed"),
    ):
        c = FbsClient()
        c.connect()


def test_disconnect_clears_state():
    """disconnect() 後 is_connected() 回傳 False。"""
    c = FbsClient()
    c._sdk = MagicMock()
    c._rest = MagicMock()
    c.disconnect()
    assert c.is_connected() is False


# ── sync_instruments ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_instruments_returns_count(client):
    """sync_instruments() 回傳寫入筆數，並呼叫 db.execute + db.commit。"""
    from unittest.mock import AsyncMock, patch

    fake_data = {
        "data": [
            {"symbol": "2330", "name": "台積電", "industry": "24"},
            {"symbol": "2317", "name": "鴻海", "industry": "28"},
        ]
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_data)):
        count = await client.sync_instruments(mock_db)

    assert count == 2
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_instruments_empty_data(client):
    """data 為空時回傳 0，不呼叫 db.execute。"""
    from unittest.mock import AsyncMock, patch

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value={"data": []})):
        mock_db = AsyncMock()
        count = await client.sync_instruments(mock_db)

    assert count == 0
    mock_db.execute.assert_not_called()


# ── sync_quote ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_quote_success(client):
    """正常回傳時 sync_quote() 回傳 True，呼叫 db.execute + db.commit。"""
    from unittest.mock import AsyncMock, patch

    fake_quote = {
        "referencePrice": 2230, "previousClose": 2230,
        "openPrice": 2245, "highPrice": 2260, "lowPrice": 2225,
        "closePrice": 2255, "lastPrice": 2255, "lastSize": 3821,
        "avgPrice": 2243.86, "change": 25, "changePercent": 1.12,
        "amplitude": 1.57, "bids": [], "asks": [], "total": {},
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_quote)):
        result = await client.sync_quote(mock_db, "2330")

    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_quote_429_returns_false(client):
    """SDK 拋 429 例外時，sync_quote() 回傳 False 而非往上拋。"""
    from unittest.mock import AsyncMock, patch

    async def raise_429(*args, **kwargs):
        raise Exception("429 Rate limit exceeded")

    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=raise_429):
        result = await client.sync_quote(mock_db, "2330")

    assert result is False
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sync_quote_other_exception_propagates(client):
    """非 429 例外應往上拋，讓 ARQ 重試機制感知。"""
    from unittest.mock import AsyncMock, patch

    async def raise_conn_err(*args, **kwargs):
        raise ConnectionError("SDK connection lost")

    mock_db = AsyncMock()

    with (
        patch("app.services.fbs.asyncio.to_thread", new=raise_conn_err),
        pytest.raises(ConnectionError),
    ):
        await client.sync_quote(mock_db, "2330")


# ── sync_intraday_candles ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_intraday_candles_returns_count(client):
    """回傳今日全部 K 棒數量，不重複插入已存在的資料。"""
    from unittest.mock import AsyncMock, patch

    fake_data = {
        "data": [
            {"time": "2026-05-24T09:00:00+08:00", "open": 100, "high": 105,
             "low": 99, "close": 103, "volume": 500, "average": 102.0},
            {"time": "2026-05-24T09:01:00+08:00", "open": 103, "high": 106,
             "low": 102, "close": 105, "volume": 300, "average": 104.0},
        ]
    }
    mock_db = AsyncMock()

    with patch("app.services.fbs.asyncio.to_thread", new=AsyncMock(return_value=fake_data)):
        count = await client.sync_intraday_candles(mock_db, "2330", "1")

    assert count == 2
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()



