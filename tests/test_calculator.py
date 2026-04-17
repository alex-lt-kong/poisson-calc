"""Property-based and unit tests for the Poisson calculation pipeline.

Tests cover the pure calculation functions in app.calculator, verifying both
universal properties (via Hypothesis) and specific known input/output pairs.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.calculator import (
    CalculationSteps,
    calculate_poisson,
    compute_annualized_frequency,
    compute_lambda,
    compute_scaling_factor,
    compute_window_hours,
)

# ---------------------------------------------------------------------------
# Task 2.2 — Property-based test for calculation pipeline correctness
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 1: Calculation pipeline correctness


@given(
    probability=st.floats(min_value=0.001, max_value=99.999),
    days=st.integers(0, 365),
    hours=st.integers(0, 23),
)
@settings(max_examples=200)
def test_calculation_pipeline_correctness(
    probability: float, days: int, hours: int
) -> None:
    """**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

    For any valid probability in (0, 100) and any valid window duration
    (days >= 0, hours 0-23, total > 0), the calculation pipeline SHALL produce
    correct intermediate and final values.
    """
    # Filter: total window must be > 0
    total_hours = days * 24 + hours
    if total_hours == 0:
        return

    result = calculate_poisson(probability, days, hours)

    # lambda_value == -ln(1 - probability / 100)
    expected_lambda = -math.log(1 - probability / 100)
    assert result.lambda_value == pytest.approx(expected_lambda), (
        f"lambda mismatch: got {result.lambda_value}, expected {expected_lambda}"
    )

    # window_hours == (days * 24) + hours
    expected_window_hours = float(total_hours)
    assert result.window_hours == pytest.approx(expected_window_hours), (
        f"window_hours mismatch: got {result.window_hours}, expected {expected_window_hours}"
    )

    # scaling_factor == 8766 / window_hours
    expected_scaling = 8766.0 / expected_window_hours
    assert result.scaling_factor == pytest.approx(expected_scaling), (
        f"scaling_factor mismatch: got {result.scaling_factor}, expected {expected_scaling}"
    )

    # annualized_frequency == round(lambda_value * scaling_factor, 2)
    expected_freq = round(expected_lambda * expected_scaling, 2)
    assert result.annualized_frequency == pytest.approx(expected_freq), (
        f"annualized_frequency mismatch: got {result.annualized_frequency}, expected {expected_freq}"
    )

    # annualized_frequency has at most two decimal places
    assert result.annualized_frequency == round(result.annualized_frequency, 2)


# ---------------------------------------------------------------------------
# Task 2.3 — Unit tests for calculation functions
# ---------------------------------------------------------------------------


class TestComputeLambda:
    """Unit tests for compute_lambda."""

    def test_probability_50_percent(self) -> None:
        """50% probability -> lambda = -ln(0.5) = ln(2)."""
        expected = math.log(2)
        assert compute_lambda(50.0) == pytest.approx(expected)

    def test_probability_near_zero(self) -> None:
        """Very small probability -> lambda ≈ probability/100."""
        result = compute_lambda(0.01)
        expected = -math.log(1 - 0.0001)
        assert result == pytest.approx(expected)

    def test_probability_near_100(self) -> None:
        """Probability close to 100 -> large lambda."""
        result = compute_lambda(99.9)
        expected = -math.log(1 - 0.999)
        assert result == pytest.approx(expected)
        assert result > 5  # should be quite large


class TestComputeWindowHours:
    """Unit tests for compute_window_hours."""

    def test_one_day(self) -> None:
        assert compute_window_hours(1, 0) == 24

    def test_hours_only(self) -> None:
        assert compute_window_hours(0, 12) == 12

    def test_one_hour(self) -> None:
        """Minimum non-zero window."""
        assert compute_window_hours(0, 1) == 1

    def test_large_window(self) -> None:
        """365 days + 23 hours."""
        assert compute_window_hours(365, 23) == 365 * 24 + 23


class TestComputeScalingFactor:
    """Unit tests for compute_scaling_factor."""

    def test_one_hour_window(self) -> None:
        """1-hour window -> scaling factor = 8766."""
        assert compute_scaling_factor(1.0) == pytest.approx(8766.0)

    def test_24_hour_window(self) -> None:
        """24-hour window -> scaling factor = 8766 / 24."""
        assert compute_scaling_factor(24.0) == pytest.approx(8766.0 / 24)

    def test_full_year_window(self) -> None:
        """8766-hour window -> scaling factor = 1."""
        assert compute_scaling_factor(8766.0) == pytest.approx(1.0)

    def test_large_window(self) -> None:
        """Large window produces small scaling factor."""
        result = compute_scaling_factor(365 * 24 + 23)
        assert result == pytest.approx(8766.0 / (365 * 24 + 23))


class TestComputeAnnualizedFrequency:
    """Unit tests for compute_annualized_frequency."""

    def test_rounding(self) -> None:
        """Result is rounded to 2 decimal places."""
        result = compute_annualized_frequency(0.123456, 100.0)
        assert result == round(0.123456 * 100.0, 2)

    def test_exact_value(self) -> None:
        """Known exact computation."""
        result = compute_annualized_frequency(1.0, 1.0)
        assert result == 1.0

    def test_zero_lambda(self) -> None:
        """Lambda of 0 -> frequency of 0."""
        assert compute_annualized_frequency(0.0, 8766.0) == 0.0


class TestCalculatePoisson:
    """Unit tests for the full calculate_poisson pipeline."""

    def test_known_values_50pct_24h(self) -> None:
        """probability=50%, window=24h -> verify exact intermediate values."""
        result = calculate_poisson(50.0, 1, 0)

        expected_lambda = -math.log(1 - 0.5)
        expected_window = 24.0
        expected_scaling = 8766.0 / 24.0
        expected_freq = round(expected_lambda * expected_scaling, 2)

        assert result.lambda_value == pytest.approx(expected_lambda)
        assert result.window_hours == pytest.approx(expected_window)
        assert result.scaling_factor == pytest.approx(expected_scaling)
        assert result.annualized_frequency == pytest.approx(expected_freq)

    def test_returns_calculation_steps(self) -> None:
        """Pipeline returns a CalculationSteps dataclass."""
        result = calculate_poisson(10.0, 0, 1)
        assert isinstance(result, CalculationSteps)

    def test_one_hour_window(self) -> None:
        """Minimum window of 1 hour."""
        result = calculate_poisson(25.0, 0, 1)

        expected_lambda = -math.log(1 - 0.25)
        expected_scaling = 8766.0
        expected_freq = round(expected_lambda * expected_scaling, 2)

        assert result.window_hours == 1.0
        assert result.scaling_factor == pytest.approx(expected_scaling)
        assert result.annualized_frequency == pytest.approx(expected_freq)

    def test_large_window(self) -> None:
        """Large window: 365 days + 23 hours."""
        result = calculate_poisson(80.0, 365, 23)

        total_hours = 365 * 24 + 23
        expected_lambda = -math.log(1 - 0.8)
        expected_scaling = 8766.0 / total_hours
        expected_freq = round(expected_lambda * expected_scaling, 2)

        assert result.window_hours == pytest.approx(float(total_hours))
        assert result.scaling_factor == pytest.approx(expected_scaling)
        assert result.annualized_frequency == pytest.approx(expected_freq)

    def test_probability_near_zero(self) -> None:
        """Very small probability produces small annualized frequency."""
        result = calculate_poisson(0.01, 0, 1)
        assert result.annualized_frequency >= 0
        assert result.lambda_value > 0

    def test_probability_near_100(self) -> None:
        """Probability near 100 produces large annualized frequency."""
        result = calculate_poisson(99.9, 0, 1)
        assert result.annualized_frequency > 0
        assert result.lambda_value > 5
