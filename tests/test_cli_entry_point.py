from typer.testing import CliRunner
from src.main import app

runner = CliRunner()

SUBCOMMAND_GROUPS = ["instances", "sg", "volumes", "tags", "monitor", "cost"]


def test_help_lists_all_subcommand_groups():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in SUBCOMMAND_GROUPS:
        assert group in result.output, f"Subcommand group '{group}' not found in --help output"


def test_help_contains_app_description():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CloudOrchestrator" in result.output


def test_invalid_subcommand_shows_error():
    result = runner.invoke(app, ["nonexistent"])
    assert result.exit_code != 0
    assert "No such command" in result.output or "Error" in result.output or "Usage" in result.output


def test_region_option_accepted():
    result = runner.invoke(app, ["--region", "us-west-2", "--help"])
    assert result.exit_code == 0


def test_profile_option_accepted():
    result = runner.invoke(app, ["--profile", "test-profile", "--help"])
    assert result.exit_code == 0


def test_region_and_profile_shown_in_help():
    result = runner.invoke(app, ["--help"])
    assert "--region" in result.output
    assert "--profile" in result.output
