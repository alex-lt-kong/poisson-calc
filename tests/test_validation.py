"""Property-based tests for Pydantic model input validation.

Tests cover time range validation, window validation, probability validation,
and structured error reporting using Hypothesis to generate invalid inputs.
"""

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from pydantic import ValidationError

from app.models import (
    CalculationRequest,
    TimestampRange,
    WindowDuration,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Strategy: generate a fixed-offset timezone between -12h and +14h
_offset_strategy = st.integers(min_value=-12 * 60, max_value=14 * 60).map(
    lambda m: timezone(timedelta(minutes=m))
)


def _aware_datetime(tz):
    """Strategy for timezone-aware datetimes in a given timezone."""
    return st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2100, 1, 1),
    ).map(lambda dt: dt.replace(tzinfo=tz))


# Composite strategy: a timezone-aware datetime with a random offset
_tz_aware_dt = _offset_strategy.flatmap(_aware_datetime)


def _valid_time_range():
    """Return a valid TimestampRange for use in composite request tests."""
    start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    return {"start": start.isoformat(), "end": end.isoformat()}


def _valid_window():
    """Return a valid WindowDuration dict."""
    return {"days": 1, "hours": 0}


def _valid_probability():
    """Return a valid probability value."""
    return 50.0


# ---------------------------------------------------------------------------
# Task 3.2 — Property 2: Time range validation rejects invalid ranges
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 2: Time range validation rejects invalid ranges


@given(
    base_dt=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2100, 1, 1),
    ),
    offset_minutes_start=st.integers(min_value=-12 * 60, max_value=14 * 60),
    offset_minutes_end=st.integers(min_value=-12 * 60, max_value=14 * 60),
    delta_seconds=st.integers(min_value=0, max_value=365 * 24 * 3600),
)
@settings(max_examples=200)
def test_time_range_rejects_start_gte_end(
    base_dt: datetime,
    offset_minutes_start: int,
    offset_minutes_end: int,
    delta_seconds: int,
) -> None:
    """**Validates: Requirements 1.6**

    For any pair of timestamps where start >= end (after UTC conversion),
    the backend SHALL return a validation error on the time_range field.
    """
    tz_start = timezone(timedelta(minutes=offset_minutes_start))
    tz_end = timezone(timedelta(minutes=offset_minutes_end))

    # end_dt is the base datetime in its timezone
    end_dt = base_dt.replace(tzinfo=tz_end)

    # start_dt is end_dt + delta (in UTC terms), so start >= end after conversion
    # We construct start so that start_utc >= end_utc
    end_utc = end_dt.astimezone(timezone.utc)
    start_utc = end_utc + timedelta(seconds=delta_seconds)
    start_dt = start_utc.astimezone(tz_start)

    with pytest.raises(ValidationError) as exc_info:
        TimestampRange(start=start_dt, end=end_dt)

    # Verify the error mentions the time range / start-before-end constraint
    errors = exc_info.value.errors()
    assert len(errors) > 0
    error_messages = " ".join(e.get("msg", "") for e in errors)
    assert "start" in error_messages.lower() or "before" in error_messages.lower()


# ---------------------------------------------------------------------------
# Task 3.3 — Property 3: Window validation rejects invalid inputs
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 3: Window validation rejects invalid inputs


@given(
    data=st.one_of(
        # Case 1: negative days
        st.tuples(
            st.integers(min_value=-1000, max_value=-1),
            st.integers(min_value=0, max_value=23),
        ),
        # Case 2: hours outside 0-23 (negative)
        st.tuples(
            st.integers(min_value=0, max_value=365),
            st.integers(min_value=-1000, max_value=-1),
        ),
        # Case 3: hours outside 0-23 (too large)
        st.tuples(
            st.integers(min_value=0, max_value=365),
            st.integers(min_value=24, max_value=1000),
        ),
        # Case 4: zero total duration (days=0, hours=0)
        st.just((0, 0)),
    )
)
@settings(max_examples=200)
def test_window_rejects_invalid_inputs(data: tuple) -> None:
    """**Validates: Requirements 2.2, 2.3, 2.4**

    For any window input where days is negative, hours is outside 0-23,
    or the total duration is zero, the backend SHALL return a validation error.
    """
    days, hours = data

    with pytest.raises(ValidationError) as exc_info:
        WindowDuration(days=days, hours=hours)

    errors = exc_info.value.errors()
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# Task 3.4 — Property 4: Probability validation rejects out-of-range values
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 4: Probability validation rejects out-of-range values


@given(
    probability=st.one_of(
        # Values <= 0
        st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
        # Values >= 100
        st.floats(min_value=100.0, allow_nan=False, allow_infinity=False),
    )
)
@settings(max_examples=200)
def test_probability_rejects_out_of_range(probability: float) -> None:
    """**Validates: Requirements 3.2, 3.3**

    For any probability value <= 0 or >= 100, the backend SHALL return
    a validation error on the probability field.
    """
    # Build a full CalculationRequest with valid time_range and window,
    # but invalid probability
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, tzinfo=timezone.utc)

    with pytest.raises(ValidationError) as exc_info:
        CalculationRequest(
            time_range={"start": start, "end": end},
            window={"days": 1, "hours": 0},
            probability=probability,
        )

    errors = exc_info.value.errors()
    assert len(errors) > 0
    # At least one error should relate to the probability field
    error_fields = [
        ".".join(str(loc) for loc in e.get("loc", ()))
        for e in errors
    ]
    assert any("probability" in f for f in error_fields)


# ---------------------------------------------------------------------------
# Task 3.5 — Property 5: Structured validation errors identify all invalid fields
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 5: Structured validation errors identify all invalid fields


@given(
    invalid_time_range=st.booleans(),
    invalid_window=st.booleans(),
    invalid_probability=st.booleans(),
)
@settings(max_examples=200)
def test_structured_errors_identify_all_invalid_fields(
    invalid_time_range: bool,
    invalid_window: bool,
    invalid_probability: bool,
) -> None:
    """**Validates: Requirements 5.1, 8.3**

    For any request with random combinations of invalid fields, the backend
    SHALL return a structured error response where the set of identified
    fields matches exactly the set of fields that are invalid.
    """
    # Need at least one invalid field
    assume(invalid_time_range or invalid_window or invalid_probability)

    # Build request data
    if invalid_time_range:
        # start == end -> invalid
        same_dt = datetime(2024, 6, 1, tzinfo=timezone.utc)
        time_range_data = {"start": same_dt, "end": same_dt}
    else:
        time_range_data = {
            "start": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "end": datetime(2024, 6, 1, tzinfo=timezone.utc),
        }

    if invalid_window:
        # zero duration -> invalid
        window_data = {"days": 0, "hours": 0}
    else:
        window_data = {"days": 1, "hours": 0}

    if invalid_probability:
        # out of range -> invalid
        probability_val = 0.0
    else:
        probability_val = 50.0

    with pytest.raises(ValidationError) as exc_info:
        CalculationRequest(
            time_range=time_range_data,
            window=window_data,
            probability=probability_val,
        )

    errors = exc_info.value.errors()
    assert len(errors) > 0

    # Extract the top-level field names from error locations
    error_top_fields = set()
    for e in errors:
        loc = e.get("loc", ())
        if loc:
            error_top_fields.add(str(loc[0]))

    # Build expected set of invalid fields
    expected_invalid = set()
    if invalid_time_range:
        expected_invalid.add("time_range")
    if invalid_window:
        expected_invalid.add("window")
    if invalid_probability:
        expected_invalid.add("probability")

    # Every expected invalid field should appear in the errors
    for field in expected_invalid:
        assert field in error_top_fields, (
            f"Expected error for '{field}' but got errors for: {error_top_fields}"
        )

    # Errors should not flag fields that are valid
    valid_fields = {"time_range", "window", "probability"} - expected_invalid
    for field in valid_fields:
        assert field not in error_top_fields, (
            f"Unexpected error for valid field '{field}': {error_top_fields}"
        )
