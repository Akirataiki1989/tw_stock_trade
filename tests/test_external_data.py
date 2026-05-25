"""tests/test_external_data.py — external_data.py 的純函式單元測試。"""

import pytest
from app.services.external_data import (
    clean_number,
    parse_institutional_row,
    parse_margin_row_full,
)


# ── clean_number ──────────────────────────────────────────────────────────────

def test_clean_number_normal():
    assert clean_number("1,234,567") == 1234567


def test_clean_number_negative():
    assert clean_number("-1,234") == -1234


def test_clean_number_zero():
    assert clean_number("0") == 0


def test_clean_number_dash_returns_none():
    assert clean_number("－") is None


def test_clean_number_hyphen_returns_none():
    assert clean_number("-") is None


def test_clean_number_empty_returns_none():
    assert clean_number("") is None


def test_clean_number_whitespace():
    assert clean_number("  1,000  ") == 1000


# ── parse_institutional_row ────────────────────────────────────────────────────

_INST_FIELDS = [
    "證券代號",
    "證券名稱",
    "外陸資買進股數(不含外資自營商)",
    "外陸資賣出股數(不含外資自營商)",
    "外陸資買賣超股數(不含外資自營商)",
    "外資自營商買進股數",
    "外資自營商賣出股數",
    "外資自營商買賣超股數",
    "投信買進股數",
    "投信賣出股數",
    "投信買賣超股數",
    "自營商買賣超股數",
    "自營商買進股數(自行買賣)",
    "自營商賣出股數(自行買賣)",
    "自營商買賣超股數(自行買賣)",
    "自營商買進股數(避險)",
    "自營商賣出股數(避險)",
    "自營商買賣超股數(避險)",
    "三大法人買賣超股數",
]

_INST_ROW_2330 = [
    "2330", "台積電",
    "10,000,000", "5,000,000", "5,000,000",   # 外陸資
    "100,000", "50,000", "50,000",              # 外資自營
    "200,000", "100,000", "100,000",            # 投信
    "50,000",                                   # 自營商合計
    "30,000", "10,000", "20,000",              # 自行買賣
    "20,000", "10,000", "10,000",              # 避險
    "5,150,000",                               # 三大法人合計
]


def test_parse_institutional_row_normal():
    result = parse_institutional_row(_INST_FIELDS, _INST_ROW_2330)
    assert result is not None
    assert result["symbol"] == "2330"
    assert result["foreign_net"] == 5_000_000
    assert result["trust_buy"] == 200_000
    assert result["trust_sell"] == 100_000
    assert result["trust_net"] == 100_000
    assert result["dealer_net"] == 50_000
    assert result["total_net"] == 5_150_000


def test_parse_institutional_row_skip_total():
    row = ["合計"] + ["0"] * (len(_INST_FIELDS) - 1)
    assert parse_institutional_row(_INST_FIELDS, row) is None


def test_parse_institutional_row_skip_empty_symbol():
    row = [""] + ["0"] * (len(_INST_FIELDS) - 1)
    assert parse_institutional_row(_INST_FIELDS, row) is None


def test_parse_institutional_row_handles_dash():
    row = _INST_ROW_2330.copy()
    row[4] = "－"  # foreign_net = None
    result = parse_institutional_row(_INST_FIELDS, row)
    assert result is not None
    assert result["foreign_net"] is None


def test_parse_institutional_row_length_mismatch():
    assert parse_institutional_row(_INST_FIELDS, ["2330"]) is None


# ── parse_margin_row_full ─────────────────────────────────────────────────────

_MARGIN_ROW_2330 = [
    "2330", "台積電",
    "1,000", "500", "0",       # 融資: 買進, 賣出, 現金償還
    "50,000", "50,500",         # 融資: 前日餘額, 今日餘額
    "999999",                   # 融資限額
    "200", "100", "0",          # 融券: 買進, 賣出, 現券償還
    "3,000", "3,100",           # 融券: 前日餘額, 今日餘額
    "999999",                   # 融券限額
    "0", " ",                   # 資券互抵, 註記
]


def test_parse_margin_row_full_normal():
    result = parse_margin_row_full([], _MARGIN_ROW_2330)
    assert result is not None
    assert result["symbol"] == "2330"
    assert result["margin_buy"] == 1_000
    assert result["margin_sell"] == 500
    assert result["margin_balance_prev"] == 50_000
    assert result["margin_balance"] == 50_500
    assert result["short_buy"] == 200
    assert result["short_sell"] == 100
    assert result["short_balance_prev"] == 3_000
    assert result["short_balance"] == 3_100


def test_parse_margin_row_full_skip_total():
    row = ["合計"] + ["0"] * 15
    assert parse_margin_row_full([], row) is None


def test_parse_margin_row_full_too_short():
    assert parse_margin_row_full([], ["2330"]) is None
