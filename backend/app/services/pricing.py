from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MICRO = Decimal("0.000001")


def compute_cost(
    tokens_in: int,
    tokens_out: int,
    input_price_per_1m: Decimal | float | int,
    output_price_per_1m: Decimal | float | int,
) -> Decimal:
    """Cost in USD for one call. Prices are quoted per 1M tokens."""
    in_price = Decimal(str(input_price_per_1m))
    out_price = Decimal(str(output_price_per_1m))
    cost = (Decimal(tokens_in) * in_price + Decimal(tokens_out) * out_price) / Decimal(1_000_000)
    return cost.quantize(MICRO, rounding=ROUND_HALF_UP)


def estimate_tokens(text: str) -> int:
    """Rough fallback when a provider returns no usage block (~4 chars/token)."""
    return max(1, len(text) // 4) if text else 0
