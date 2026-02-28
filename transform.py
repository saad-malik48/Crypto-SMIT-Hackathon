"""
transform.py — ETL Transform Layer
=====================================
Responsibilities:
  • Receive raw validated dicts from extract.py
  • Clean string fields (strip, lowercase symbol)
  • Convert & clamp numeric fields
  • Compute volatility_score = abs(price_change_24h) * total_volume
  • Attach extracted_at timestamp
  • Return a list of TransformedCoin objects ready for load.py

Design choices:
  • Dataclass for TransformedCoin gives type safety + easy serialization
  • All transforms are pure functions (no I/O) — easy to unit-test
  • Field-level error logging with coin identity for debugging
  • Separate clean_* helpers for each domain (strings, prices, scores)
"""

import logging
import math
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  Output dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TransformedCoin:
    """
    A fully-cleaned, computation-enriched coin record ready to be loaded.
    All numeric fields are guaranteed non-None after transform.
    """
    coin_id:          str
    symbol:           str
    name:             str
    current_price:    float
    market_cap:       float
    total_volume:     float
    price_change_24h: float          # pct change, e.g. -3.14 means −3.14 %
    market_cap_rank:  int
    volatility_score: float          # abs(price_change_24h) * total_volume
    extracted_at:     datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d["extracted_at"] = self.extracted_at.isoformat()
        return d


# ══════════════════════════════════════════════════════════════════════════════
#  Field-level cleaners
# ══════════════════════════════════════════════════════════════════════════════

_MAX_PRICE       = 1_000_000_000.0   # sanity cap: $1 billion per coin
_MAX_MARKET_CAP  = 1e15              # $1 quadrillion
_MAX_VOLUME      = 1e13
_MIN_RANK        = 1
_MAX_RANK        = 100_000


def _clean_str(value, field_name: str, coin_id: str, default: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        logger.warning("[%s] field '%s' is blank/missing — using '%s'", coin_id, field_name, default)
        return default
    return value.strip()


def _clean_symbol(value, coin_id: str) -> str:
    raw = _clean_str(value, "symbol", coin_id, coin_id)
    return raw.upper()


def _clean_float(value, field_name: str, coin_id: str,
                 min_val: float = 0.0, max_val: float = float("inf"),
                 default: float = 0.0) -> float:
    """
    Coerce value to float, clamp to [min_val, max_val].
    Returns default on failure.
    """
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            raise ValueError("nan/inf")
        v = max(min_val, min(v, max_val))
        return round(v, 8)
    except (TypeError, ValueError) as exc:
        logger.warning("[%s] field '%s' invalid (%s) — defaulting to %.2f", coin_id, field_name, exc, default)
        return default


def _clean_int(value, field_name: str, coin_id: str,
               min_val: int = 1, max_val: int = _MAX_RANK,
               default: int = _MAX_RANK) -> int:
    try:
        return max(min_val, min(int(float(value)), max_val))
    except (TypeError, ValueError):
        logger.warning("[%s] field '%s' invalid — defaulting to %d", coin_id, field_name, default)
        return default


def _compute_volatility(price_change_24h: float, total_volume: float) -> float:
    """
    volatility_score = |price_change_24h_pct| × total_volume_usd
    
    Interpretation:
      High price swing + high volume = extreme volatility.
      Used for ranking coins by market impact of their movement.
    """
    score = abs(price_change_24h) * total_volume
    return round(score, 4)


# ══════════════════════════════════════════════════════════════════════════════
#  Single-record transform
# ══════════════════════════════════════════════════════════════════════════════

def transform_coin(raw: dict, extracted_at: datetime) -> Optional[TransformedCoin]:
    """
    Transform one raw coin dict into a TransformedCoin.

    Args:
        raw: Validated dict from extract layer (keys match CoinGecko schema).
        extracted_at: The UTC datetime when extraction occurred.

    Returns:
        TransformedCoin or None if the record is fundamentally broken.
    """
    coin_id = raw.get("id", "unknown")

    # ── Strings ───────────────────────────────────────────────────────────────
    symbol = _clean_symbol(raw.get("symbol"), coin_id)
    name   = _clean_str(raw.get("name"), "name", coin_id, coin_id)

    # ── Numeric ───────────────────────────────────────────────────────────────
    price = _clean_float(
        raw.get("current_price"), "current_price", coin_id,
        min_val=0.0, max_val=_MAX_PRICE
    )
    if price <= 0:
        logger.warning("[%s] current_price=0 — record may be junk", coin_id)

    market_cap = _clean_float(
        raw.get("market_cap"), "market_cap", coin_id,
        min_val=0.0, max_val=_MAX_MARKET_CAP
    )
    total_volume = _clean_float(
        raw.get("total_volume"), "total_volume", coin_id,
        min_val=0.0, max_val=_MAX_VOLUME
    )
    # CoinGecko returns pct as a plain float e.g. -3.14 (meaning −3.14 %)
    price_change = _clean_float(
        raw.get("price_change_percentage_24h"), "price_change_24h", coin_id,
        min_val=-100.0, max_val=10_000.0, default=0.0
    )
    rank = _clean_int(
        raw.get("market_cap_rank"), "market_cap_rank", coin_id
    )

    # ── Derived ───────────────────────────────────────────────────────────────
    volatility = _compute_volatility(price_change, total_volume)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    if extracted_at.tzinfo is None:
        extracted_at = extracted_at.replace(tzinfo=timezone.utc)

    return TransformedCoin(
        coin_id=coin_id,
        symbol=symbol,
        name=name,
        current_price=price,
        market_cap=market_cap,
        total_volume=total_volume,
        price_change_24h=price_change,
        market_cap_rank=rank,
        volatility_score=volatility,
        extracted_at=extracted_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Batch transform
# ══════════════════════════════════════════════════════════════════════════════

def transform(raw_coins: list[dict], extracted_at: datetime) -> list[TransformedCoin]:
    """
    Transform a batch of raw coin dicts.

    Args:
        raw_coins:    Output from extract.validate_response()
        extracted_at: UTC datetime stamped at extraction time

    Returns:
        List of TransformedCoin records (failures silently dropped with warning)
    """
    logger.info("Transforming %d raw coins (timestamp: %s)", len(raw_coins), extracted_at.isoformat())

    results: list[TransformedCoin] = []
    for raw in raw_coins:
        try:
            coin = transform_coin(raw, extracted_at)
            if coin is not None:
                results.append(coin)
        except Exception as exc:
            logger.error("Unexpected transform error for %s: %s", raw.get("id", "?"), exc)

    logger.info(
        "Transform complete: %d/%d records ready (dropped %d)",
        len(results), len(raw_coins), len(raw_coins) - len(results)
    )

    # Sort by market cap rank so load order is deterministic
    results.sort(key=lambda c: c.market_cap_rank)
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  Summary statistics (for logging / dashboard)
# ══════════════════════════════════════════════════════════════════════════════

def summarize(coins: list[TransformedCoin]) -> dict:
    """Return a quick summary dict for logging and KPI display."""
    if not coins:
        return {}

    prices      = [c.current_price   for c in coins]
    mcaps       = [c.market_cap       for c in coins]
    changes     = [c.price_change_24h for c in coins]
    volatilities= [c.volatility_score for c in coins]

    gainers  = [c for c in coins if c.price_change_24h > 0]
    losers   = [c for c in coins if c.price_change_24h < 0]
    top_vol  = max(coins, key=lambda c: c.volatility_score)
    top_gain = max(coins, key=lambda c: c.price_change_24h)

    return {
        "total_coins":       len(coins),
        "total_market_cap":  sum(mcaps),
        "avg_price":         sum(prices) / len(prices),
        "avg_change_24h":    sum(changes) / len(changes),
        "gainers":           len(gainers),
        "losers":            len(losers),
        "top_gainer":        {"coin": top_gain.symbol, "change": top_gain.price_change_24h},
        "most_volatile":     {"coin": top_vol.symbol,  "score": top_vol.volatility_score},
        "extracted_at":      coins[0].extracted_at.isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  CLI test
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Inline sample data so transform can be tested without network
    SAMPLE = [
        {
            "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
            "current_price": 67_432.10, "market_cap": 1_328_000_000_000,
            "total_volume": 28_500_000_000,
            "price_change_percentage_24h": 2.34, "market_cap_rank": 1,
        },
        {
            "id": "ethereum", "symbol": "eth", "name": "Ethereum",
            "current_price": 3_812.50, "market_cap": 457_000_000_000,
            "total_volume": 15_200_000_000,
            "price_change_percentage_24h": -1.87, "market_cap_rank": 2,
        },
        {
            "id": "solana", "symbol": "sol", "name": "Solana",
            "current_price": 178.40, "market_cap": 78_500_000_000,
            "total_volume": 3_400_000_000,
            "price_change_percentage_24h": 5.61, "market_cap_rank": 5,
        },
        # Edge case: null price
        {
            "id": "badcoin", "symbol": "bad", "name": "Bad Coin",
            "current_price": None, "market_cap": 0,
            "total_volume": 0, "price_change_percentage_24h": None,
            "market_cap_rank": None,
        },
    ]

    ts = datetime.now(tz=timezone.utc)
    coins = transform(SAMPLE, ts)

    print(f"\n✓ Transformed {len(coins)} coins\n")
    print(f"  {'Rank':<5} {'Symbol':<8} {'Price':>14} {'Chg 24h':>10} {'Volatility':>20}")
    print("  " + "─" * 62)
    for c in coins:
        print(
            f"  {c.market_cap_rank:<5}"
            f"  {c.symbol:<8}"
            f"  ${c.current_price:>13,.2f}"
            f"  {c.price_change_24h:>+9.2f}%"
            f"  {c.volatility_score:>20,.0f}"
        )

    summary = summarize(coins)
    print(f"\nSummary:")
    print(f"  Total Market Cap : ${summary['total_market_cap']:>25,.0f}")
    print(f"  Top Gainer       : {summary['top_gainer']['coin']} (+{summary['top_gainer']['change']:.2f}%)")
    print(f"  Most Volatile    : {summary['most_volatile']['coin']} (score={summary['most_volatile']['score']:,.0f})")
