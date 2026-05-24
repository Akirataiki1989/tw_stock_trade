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
