"""Pure calculation functions for the Poisson annualized frequency pipeline.

All functions are pure (no side effects, no HTTP concerns). The module
implements the mathematical core: given an observed probability of at least
one event in a time window, derive the annualized frequency using the
Poisson distribution.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationSteps:
    """Intermediate and final results of the Poisson calculation pipeline."""

    lambda_value: float
    window_hours: float
    scaling_factor: float
    annualized_frequency: float


def compute_lambda(probability_pct: float) -> float:
    """Derive λ from the observed probability using the inverse Poisson CDF.

    Given P(at least 1 event) = 1 − e^(−λ), solving for λ gives:
        λ = −ln(1 − probability / 100)

    Args:
        probability_pct: Observed probability as a percentage in (0, 100).

    Returns:
        The expected number of events (λ) in the observation window.
    """
    return -math.log(1 - probability_pct / 100)


def compute_window_hours(days: int, hours: int) -> float:
    """Convert a window duration of days and hours into total hours.

    Args:
        days: Number of whole days (≥ 0).
        hours: Number of additional hours (0–23).

    Returns:
        Total window duration in hours.
    """
    return (days * 24) + hours


def compute_scaling_factor(window_hours: float, hours_in_year: float = 8766.0) -> float:
    """Compute the ratio to scale from the observation window to one year.

    Args:
        window_hours: Duration of the observation window in hours (must be > 0).
        hours_in_year: Number of hours in a year. Defaults to 8766.0
            (average accounting for leap years).

    Returns:
        The scaling factor (hours_in_year / window_hours).
    """
    return hours_in_year / window_hours


def compute_annualized_frequency(lambda_val: float, scaling_factor: float) -> float:
    """Scale λ from the observation window to an annual frequency.

    Args:
        lambda_val: Expected number of events in the observation window.
        scaling_factor: Ratio of one year to the observation window.

    Returns:
        Annualized frequency rounded to two decimal places.
    """
    return round(lambda_val * scaling_factor, 2)


def calculate_poisson(probability_pct: float, days: int, hours: int) -> CalculationSteps:
    """Run the full Poisson calculation pipeline.

    Computes all intermediate steps and returns them together with the
    final annualized frequency.

    Args:
        probability_pct: Observed probability as a percentage in (0, 100).
        days: Days component of the observation window (≥ 0).
        hours: Hours component of the observation window (0–23).

    Returns:
        A CalculationSteps object containing lambda_value, window_hours,
        scaling_factor, and annualized_frequency.
    """
    lambda_val = compute_lambda(probability_pct)
    window_hours = compute_window_hours(days, hours)
    scaling_factor = compute_scaling_factor(window_hours)
    annualized_freq = compute_annualized_frequency(lambda_val, scaling_factor)
    return CalculationSteps(
        lambda_value=lambda_val,
        window_hours=window_hours,
        scaling_factor=scaling_factor,
        annualized_frequency=annualized_freq,
    )
