import re
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from src.cost import cost_app


runner = CliRunner()


def _make_ce_response(groups: list[dict], start: str = "2026-03-01", end: str = "2026-03-31") -> dict:
    """Build a minimal Cost Explorer get_cost_and_usage response."""
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": start, "End": end},
                "Groups": groups,
            }
        ]
    }


def _make_group(instance_type: str, amount: str, unit: str = "USD") -> dict:
    return {
        "Keys": [instance_type],
        "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": unit}},
    }


class TestGenerateReport:
    """Tests for the `cost report` command."""

    @patch("src.cost.boto3.client")
    def test_single_entry_fields(self, mock_client_ctor):
        """Parsed entry contains correct service, amount, currency, and dates."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response(
            [_make_group("t2.micro", "12.34")],
            start="2026-03-01",
            end="2026-03-31",
        )
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["report", "--days", "30"])

        assert result.exit_code == 0
        assert "t2.micro" in result.output
        assert "$12.34" in result.output
        assert "USD" in result.output
        assert "2026-03-01" in result.output
        assert "2026-03-31" in result.output

    @patch("src.cost.boto3.client")
    def test_multiple_entries_all_displayed(self, mock_client_ctor):
        """All instance-type groups appear in the output."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response([
            _make_group("t2.micro", "5.00"),
            _make_group("m5.large", "42.10"),
            _make_group("c5.xlarge", "0.00"),
        ])
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["report", "--days", "30"])

        assert result.exit_code == 0
        assert "t2.micro" in result.output
        assert "m5.large" in result.output
        assert "c5.xlarge" in result.output

    @patch("src.cost.boto3.client")
    def test_zero_amount_accepted(self, mock_client_ctor):
        """A zero-cost entry is valid and displayed."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response(
            [_make_group("t3.nano", "0.00")]
        )
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["report", "--days", "7"])

        assert result.exit_code == 0
        assert "$0.00" in result.output

    @patch("src.cost.boto3.client")
    def test_dates_in_output_match_yyyy_mm_dd(self, mock_client_ctor):
        """All dates in the output conform to YYYY-MM-DD format."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response(
            [_make_group("t2.micro", "1.00")],
            start="2026-02-01",
            end="2026-02-28",
        )
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["report", "--days", "30"])

        dates_found = re.findall(r"\d{4}-\d{2}-\d{2}", result.output)
        assert len(dates_found) >= 2
        for d in dates_found:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)

    @patch("src.cost.boto3.client")
    def test_empty_response_no_crash(self, mock_client_ctor):
        """An empty ResultsByTime produces no output and no error."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["report", "--days", "30"])

        assert result.exit_code == 0


class TestCostSummary:
    """Tests for the `cost summary` command."""

    @patch("src.cost.boto3.client")
    def test_summary_aggregates_by_instance_type(self, mock_client_ctor):
        """Summary totals are displayed per instance type."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response([
            _make_group("t2.micro", "10.00"),
            _make_group("m5.large", "25.50"),
        ])
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["summary", "--days", "7"])

        assert result.exit_code == 0
        assert "t2.micro" in result.output
        assert "$10.00" in result.output
        assert "m5.large" in result.output
        assert "$25.50" in result.output

    @patch("src.cost.boto3.client")
    def test_summary_shows_grand_total(self, mock_client_ctor):
        """Summary includes a grand total line."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response([
            _make_group("t2.micro", "10.00"),
            _make_group("m5.large", "20.00"),
        ])
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["summary", "--days", "7"])

        assert result.exit_code == 0
        assert "$30.00" in result.output
        assert "Total" in result.output

    @patch("src.cost.boto3.client")
    def test_summary_amounts_non_negative(self, mock_client_ctor):
        """All dollar amounts in summary output are non-negative."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = _make_ce_response([
            _make_group("t2.micro", "0.00"),
            _make_group("c5.xlarge", "99.99"),
        ])
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["summary", "--days", "30"])

        assert result.exit_code == 0
        amounts = re.findall(r"\$(\d+\.\d{2})", result.output)
        assert len(amounts) >= 1
        for amt in amounts:
            assert float(amt) >= 0.0

    @patch("src.cost.boto3.client")
    def test_summary_empty_response(self, mock_client_ctor):
        """Empty CE response produces header and zero total without error."""
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
        mock_client_ctor.return_value = mock_ce

        result = runner.invoke(cost_app, ["summary", "--days", "7"])

        assert result.exit_code == 0
        assert "$0.00" in result.output
