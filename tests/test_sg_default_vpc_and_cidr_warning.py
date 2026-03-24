"""
Unit tests for default VPC fallback and CIDR warning (Task 5.3).

Validates:
- Requirement 3.2: Omitting --vpc-id uses the default VPC
- Requirement 3.5: CIDR 0.0.0.0/0 triggers a warning message
"""

import os
import boto3
import pytest
from moto import mock_aws
from typer.testing import CliRunner
import typer

from src.security_groups import sg_app

runner = CliRunner()

# Wrap sg_app in a top-level app so the runner can invoke subcommands
app = typer.Typer()
app.add_typer(sg_app, name="sg")


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Pin region and dummy credentials so boto3 inside CLI commands hits moto."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


class TestDefaultVpcFallback:
    """Requirement 3.2: When no --vpc-id is provided, the default VPC is used."""

    @mock_aws
    def test_create_sg_without_vpc_id_uses_default_vpc(self):
        """Creating a security group without --vpc-id should place it in the default VPC."""
        client = boto3.client("ec2", region_name="us-east-1")

        # moto creates a default VPC automatically; find its ID
        vpcs = client.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])
        default_vpc_id = vpcs["Vpcs"][0]["VpcId"]

        result = runner.invoke(app, ["sg", "create", "test-no-vpc"])

        assert result.exit_code == 0, result.output
        assert "Created:" in result.output

        # Extract group ID from output like "Created: sg-xxx (test-no-vpc)"
        group_id = result.output.split("Created: ")[1].split(" ")[0]

        # Verify the SG was placed in the default VPC
        sg_resp = client.describe_security_groups(GroupIds=[group_id])
        assert sg_resp["SecurityGroups"][0]["VpcId"] == default_vpc_id

    @mock_aws
    def test_create_sg_with_explicit_vpc_id(self):
        """Creating a security group with --vpc-id should use that VPC, not the default."""
        client = boto3.client("ec2", region_name="us-east-1")

        # Create a non-default VPC
        vpc = client.create_vpc(CidrBlock="10.99.0.0/16")
        custom_vpc_id = vpc["Vpc"]["VpcId"]

        result = runner.invoke(app, ["sg", "create", "test-custom-vpc", "--vpc-id", custom_vpc_id])

        assert result.exit_code == 0, result.output
        group_id = result.output.split("Created: ")[1].split(" ")[0]

        sg_resp = client.describe_security_groups(GroupIds=[group_id])
        assert sg_resp["SecurityGroups"][0]["VpcId"] == custom_vpc_id


class TestCidrWarning:
    """Requirement 3.5: CIDR 0.0.0.0/0 triggers a warning."""

    @mock_aws
    def test_open_cidr_triggers_warning(self):
        """Adding a rule with 0.0.0.0/0 should print a warning about being open to the internet."""
        client = boto3.client("ec2", region_name="us-east-1")

        vpc = client.create_vpc(CidrBlock="10.0.0.0/16")
        sg = client.create_security_group(
            GroupName="warn-test", Description="test", VpcId=vpc["Vpc"]["VpcId"],
        )
        group_id = sg["GroupId"]

        result = runner.invoke(app, [
            "sg", "add-rule", group_id,
            "--from-port", "80", "--protocol", "tcp", "--cidr", "0.0.0.0/0",
        ])

        assert result.exit_code == 0, result.output
        assert "0.0.0.0/0" in result.output
        assert "warning" in result.output.lower() or "⚠" in result.output

    @mock_aws
    def test_restricted_cidr_no_warning(self):
        """Adding a rule with a restricted CIDR should NOT print a warning."""
        client = boto3.client("ec2", region_name="us-east-1")

        vpc = client.create_vpc(CidrBlock="10.0.0.0/16")
        sg = client.create_security_group(
            GroupName="no-warn-test", Description="test", VpcId=vpc["Vpc"]["VpcId"],
        )
        group_id = sg["GroupId"]

        result = runner.invoke(app, [
            "sg", "add-rule", group_id,
            "--from-port", "22", "--protocol", "tcp", "--cidr", "10.0.1.0/24",
        ])

        assert result.exit_code == 0, result.output
        assert "warning" not in result.output.lower()
        assert "⚠" not in result.output
