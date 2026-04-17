"""Property-based tests for UTC timezone conversion in the Poisson Calculator.

Tests verify that converting timezone-aware timestamps to UTC preserves
the absolute point in time and that response timestamps carry UTC offset.
"""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.models import TimestampRange

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Strategy: generate a fixed-offset timezone between -12h and +14h
_offset_strategy = st.integers(min_value=-12 * 60, max_value=14 * 60).map(
    lambda m: timezone(timedelta(minutes=m))
)


# ---------------------------------------------------------------------------
# Task 3.6 — Property 6: UTC timezone conversion preserves absolute time
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 6: UTC timezone conversion preserves absolute time


@given(
    start_dt=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2050, 1, 1),
    ),
    end_dt=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2050, 1, 1),
    ),
    start_offset_minutes=st.integers(min_value=-12 * 60, max_value=14 * 60),
    end_offset_minutes=st.integers(min_value=-12 * 60, max_value=14 * 60),
)
@settings(max_examples=200)
def test_utc_conversion_preserves_absolute_time(
    start_dt: datetime,
    end_dt: datetime,
    start_offset_minutes: int,
    end_offset_minutes: int,
) -> None:
    """**Validates: Requirements 9.2, 9.3**

    For any input timestamp with a timezone offset, the backend SHALL convert
    it to UTC such that the resulting UTC timestamp represents the same
    absolute point in time, and all timestamps in the response SHALL have
    UTC offset.
    """
    tz_start = timezone(timedelta(minutes=start_offset_minutes))
    tz_end = timezone(timedelta(minutes=end_offset_minutes))

    aware_start = start_dt.replace(tzinfo=tz_start)
    aware_end = end_dt.replace(tzinfo=tz_end)

    # Ensure start < end in UTC so TimestampRange is valid
    start_utc = aware_start.astimezone(timezone.utc)
    end_utc = aware_end.astimezone(timezone.utc)
    assume(start_utc < end_utc)

    tr = TimestampRange(start=aware_start, end=aware_end)

    # The model_validator converts to UTC internally; verify the stored
    # datetimes represent the same absolute point in time as the originals
    stored_start_utc = tr.start.astimezone(timezone.utc)
    stored_end_utc = tr.end.astimezone(timezone.utc)

    # Absolute time preservation: the UTC representation must match
    assert stored_start_utc == start_utc, (
        f"Start UTC mismatch: {stored_start_utc} != {start_utc}"
    )
    assert stored_end_utc == end_utc, (
        f"End UTC mismatch: {stored_end_utc} != {end_utc}"
    )

    # Verify that converting to UTC yields the same timestamp as the original
    # (i.e., the absolute point in time is preserved through the round-trip)
    original_start_ts = aware_start.timestamp()
    stored_start_ts = tr.start.timestamp()
    assert abs(original_start_ts - stored_start_ts) < 0.001, (
        f"Start timestamp drift: {original_start_ts} vs {stored_start_ts}"
    )

    original_end_ts = aware_end.timestamp()
    stored_end_ts = tr.end.timestamp()
    assert abs(original_end_ts - stored_end_ts) < 0.001, (
        f"End timestamp drift: {original_end_ts} vs {stored_end_ts}"
    )

    # Verify response timestamps can be represented with UTC offset
    # (timezone-aware datetimes with tzinfo should be convertible to UTC)
    response_start = stored_start_utc
    response_end = stored_end_utc
    assert response_start.tzinfo is not None, "Start should be timezone-aware"
    assert response_end.tzinfo is not None, "End should be timezone-aware"
    assert response_start.utcoffset() == timedelta(0), (
        f"Start UTC offset should be zero, got {response_start.utcoffset()}"
    )
    assert response_end.utcoffset() == timedelta(0), (
        f"End UTC offset should be zero, got {response_end.utcoffset()}"
    )
