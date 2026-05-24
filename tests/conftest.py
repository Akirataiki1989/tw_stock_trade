import pytest
from unittest.mock import MagicMock

from app.services.fbs import FbsClient


@pytest.fixture
def client() -> FbsClient:
    """回傳一個已注入 mock _sdk / _rest 的 FbsClient（不實際登入）。"""
    c = FbsClient()
    c._sdk = MagicMock()
    c._rest = MagicMock()
    return c
