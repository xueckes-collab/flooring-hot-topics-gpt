"""Per-user quota check.  Called from /analyze before doing real work."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.storage import get_active_record


@dataclass
class QuotaDecision:
    allowed: bool
    reason: Optional[str]
    daily_used: int
    daily_limit: int
    monthly_used: int
    monthly_limit: int


def check(user_token: str) -> QuotaDecision:
    row = get_active_record(user_token)
    if not row:
        return QuotaDecision(False, "user_token not found or revoked", 0, 0, 0, 0)

    daily_limit = row["daily_quota"] if row["daily_quota"] is not None else settings.default_daily_quota
    monthly_limit = row["monthly_quota"] if row["monthly_quota"] is not None else settings.default_monthly_quota

    # Counts in DB are still on the OLD window if we haven't rolled yet.
    # record_usage() does the roll when it writes; here we read what's
    # there and trust that if windows just rolled, the count is 0 again.
    daily_used = row["day_request_count"] or 0
    monthly_used = row["month_request_count"] or 0

    if daily_limit > 0 and daily_used >= daily_limit:
        return QuotaDecision(
            False,
            f"daily quota exhausted ({daily_used}/{daily_limit}). Resets at 00:00 UTC.",
            daily_used, daily_limit, monthly_used, monthly_limit,
        )
    if monthly_limit > 0 and monthly_used >= monthly_limit:
        return QuotaDecision(
            False,
            f"monthly quota exhausted ({monthly_used}/{monthly_limit}). Resets on the 1st.",
            daily_used, daily_limit, monthly_used, monthly_limit,
        )
    return QuotaDecision(
        True, None,
        daily_used, daily_limit, monthly_used, monthly_limit,
    )
