from __future__ import annotations

from decimal import Decimal

from app.services.pricing import compute_cost, estimate_tokens


def test_cost_uses_per_million_prices() -> None:
    # 1000 input tokens at $3/1M and 500 output at $6/1M
    assert compute_cost(1000, 500, 3.0, 6.0) == Decimal("0.006000")


def test_cost_is_zero_for_free_local_models() -> None:
    assert compute_cost(12000, 8000, 0, 0) == Decimal("0.000000")


def test_cost_accepts_decimal_prices() -> None:
    assert compute_cost(1_000_000, 0, Decimal("2.50"), Decimal("10")) == Decimal("2.500000")


def test_cost_rounds_to_micro_dollars() -> None:
    # 1 token at $0.15/1M = 0.00000015 -> rounds to 0.000000
    assert compute_cost(1, 0, 0.15, 0) == Decimal("0.000000")
    # 5 tokens at $0.15/1M = 0.00000075 -> rounds up
    assert compute_cost(5, 0, 0.15, 0) == Decimal("0.000001")


def test_estimate_tokens_is_roughly_quarter_of_length() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 400) == 100
