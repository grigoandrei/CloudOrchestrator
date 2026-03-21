"""
Property tests for CPU metric range and cost entry validation (Properties 9 & 10).

Property 9: CPU metric range invariant — average_cpu and max_cpu always in [0.0, 100.0]
Property 10: Cost entry non-negative amounts — amount >= 0.0 and dates match YYYY-MM-DD

Validates: Requirements 6.6, 7.3, 9.4, 9.5
"""

import re
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src.models import CPUMetric, CostEntry


# --- Strategies ---

valid_cpu_values = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
invalid_cpu_high = st.floats(min_value=100.01, max_value=1e6, allow_nan=False, allow_infinity=False)
invalid_cpu_low = st.floats(min_value=-1e6, max_value=-0.01, allow_nan=False, allow_infinity=False)
valid_amounts = st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False)
negative_amounts = st.floats(min_value=-1e9, max_value=-0.01, allow_nan=False, allow_infinity=False)
valid_dates = st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31))


def _make_cpu_metric(average_cpu: float = 50.0, max_cpu: float = 75.0) -> CPUMetric:
    return CPUMetric(
        instance_id="i-abc123",
        average_cpu=average_cpu,
        max_cpu=max_cpu,
        period_hours=24,
        data_points=10,
    )


def _make_cost_entry(amount: float = 10.0, start_date: date = date(2025, 1, 1), end_date: date = date(2025, 1, 31)) -> CostEntry:
    return CostEntry(
        service="t2.micro",
        amount=amount,
        currency="USD",
        start_date=start_date,
        end_date=end_date,
    )

class TestCpuMetricRangeInvariant:
    """average_cpu and max_cpu must always be in [0.0, 100.0]."""

    @given(avg=valid_cpu_values, mx=valid_cpu_values)
    @settings(max_examples=200)
    def test_valid_cpu_values_accepted(self, avg: float, mx: float):
        """Any float in [0.0, 100.0] is accepted for both fields."""
        metric = _make_cpu_metric(average_cpu=avg, max_cpu=mx)
        assert 0.0 <= metric.average_cpu <= 100.0
        assert 0.0 <= metric.max_cpu <= 100.0

    @given(avg=invalid_cpu_high)
    @settings(max_examples=100)
    def test_average_cpu_above_100_rejected(self, avg: float):
        """average_cpu values above 100.0 are rejected."""
        with pytest.raises(ValidationError):
            _make_cpu_metric(average_cpu=avg)

    @given(avg=invalid_cpu_low)
    @settings(max_examples=100)
    def test_average_cpu_below_zero_rejected(self, avg: float):
        """average_cpu values below 0.0 are rejected."""
        with pytest.raises(ValidationError):
            _make_cpu_metric(average_cpu=avg)

    @given(mx=invalid_cpu_high)
    @settings(max_examples=100)
    def test_max_cpu_above_100_rejected(self, mx: float):
        """max_cpu values above 100.0 are rejected."""
        with pytest.raises(ValidationError):
            _make_cpu_metric(max_cpu=mx)

    @given(mx=invalid_cpu_low)
    @settings(max_examples=100)
    def test_max_cpu_below_zero_rejected(self, mx: float):
        """max_cpu values below 0.0 are rejected."""
        with pytest.raises(ValidationError):
            _make_cpu_metric(max_cpu=mx)

    def test_boundary_zero_accepted(self):
        """Boundary value 0.0 is accepted."""
        metric = _make_cpu_metric(average_cpu=0.0, max_cpu=0.0)
        assert metric.average_cpu == 0.0
        assert metric.max_cpu == 0.0

    def test_boundary_100_accepted(self):
        """Boundary value 100.0 is accepted."""
        metric = _make_cpu_metric(average_cpu=100.0, max_cpu=100.0)
        assert metric.average_cpu == 100.0
        assert metric.max_cpu == 100.0

    def test_nan_rejected(self):
        """NaN is not a valid CPU value."""
        with pytest.raises(ValidationError):
            _make_cpu_metric(average_cpu=float("nan"))

    def test_infinity_rejected(self):
        """Infinity is not a valid CPU value."""
        with pytest.raises(ValidationError):
            _make_cpu_metric(average_cpu=float("inf"))

class TestCostEntryValidation:
    """amount >= 0.0 and dates conform to YYYY-MM-DD."""

    @given(amount=valid_amounts)
    @settings(max_examples=200)
    def test_non_negative_amounts_accepted(self, amount: float):
        """Any non-negative float is accepted as amount."""
        entry = _make_cost_entry(amount=amount)
        assert entry.amount >= 0.0

    @given(amount=negative_amounts)
    @settings(max_examples=100)
    def test_negative_amounts_rejected(self, amount: float):
        """Negative amounts are always rejected."""
        with pytest.raises(ValidationError):
            _make_cost_entry(amount=amount)

    def test_zero_amount_accepted(self):
        """Boundary value 0.0 is accepted."""
        entry = _make_cost_entry(amount=0.0)
        assert entry.amount == 0.0

    @given(d=valid_dates)
    @settings(max_examples=100)
    def test_valid_dates_conform_to_yyyy_mm_dd(self, d: date):
        """All valid date objects serialize to YYYY-MM-DD format."""
        entry = _make_cost_entry(start_date=d, end_date=d)
        # Pydantic stores as date objects; isoformat gives YYYY-MM-DD
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.start_date.isoformat())
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry.end_date.isoformat())

    @given(d=valid_dates)
    @settings(max_examples=100)
    def test_date_strings_accepted_as_input(self, d: date):
        """YYYY-MM-DD strings are accepted and parsed correctly."""
        date_str = d.isoformat()
        entry = CostEntry(
            service="t2.micro",
            amount=5.0,
            currency="USD",
            start_date=date_str,
            end_date=date_str,
        )
        assert entry.start_date == d
        assert entry.end_date == d

    @pytest.mark.parametrize("bad_date", ["2025-13-01", "not-a-date", "01-01-2025", "2025/01/01", ""])
    def test_invalid_date_strings_rejected(self, bad_date: str):
        """Malformed date strings are rejected."""
        with pytest.raises(ValidationError):
            CostEntry(
                service="t2.micro",
                amount=5.0,
                currency="USD",
                start_date=bad_date,
                end_date=bad_date,
            )
