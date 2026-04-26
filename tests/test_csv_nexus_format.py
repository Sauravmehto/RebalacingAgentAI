"""Nexus export-style CSV: parenthetical headers, footer total row, optional current price column."""

import os
import tempfile

from utils import _is_skipped_portfolio_row, _normalize_header_name, load_portfolio_csv


def test_normalize_purchase_price_header():
    assert _normalize_header_name("Purchase Price ($)") == "purchase price"
    assert _normalize_header_name("Current Price ($)") == "current price"
    assert _normalize_header_name("Return (%)") == "return"
    assert _normalize_header_name("P&L ($)") == "p&l"


def test_footer_rows_skipped():
    assert _is_skipped_portfolio_row("PORTFOLIO TOTAL") is True
    assert _is_skipped_portfolio_row("MSFT") is False
    assert _is_skipped_portfolio_row("") is True


def test_load_nexus_style_csv():
    content = (
        "Ticker,Sector,Purchase Date,Quantity,Purchase Price ($),Current Price ($),"
        "Amount Invested ($),Current Value ($),P&L ($),Return (%)\n"
        "MSFT,Tech,2/28/2026,10,100.0,110.0,1000,1100,100,10\n"
        "PORTFOLIO TOTAL,,,,,,,,,,\n"
    )
    path = _write_temp_csv(content)
    try:
        rows, errors = load_portfolio_csv(path)
    finally:
        os.unlink(path)

    assert not errors
    assert len(rows) == 1
    assert rows[0]["ticker"] == "MSFT"
    assert rows[0]["buy_price"] == 100.0
    assert rows[0]["quantity"] == 10.0
    assert rows[0]["current_price_csv"] == 110.0
    assert "amount_invested_csv" in rows[0]
    assert rows[0]["return_pct_csv"] == 10.0


def _write_temp_csv(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv", text=True)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path
