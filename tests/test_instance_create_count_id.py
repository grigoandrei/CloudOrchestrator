import os
import re
import boto3
from hypothesis import given, settings
from hypothesis import strategies as st
from moto import mock_aws
from typer.testing import CliRunner

from src.instances import instances_app

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

runner = CliRunner()

INSTANCE_ID_PATTERN = re.compile(r"^i-[0-9a-f]+$")

# Keep counts small for speed; spec says count >= 1
counts = st.integers(min_value=1, max_value=5)

# Name tags — short non-empty strings (always provided to satisfy model min_length=1 on tags)
names = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))


def _get_all_instances(client) -> list[dict]:
    """Return flat list of instance dicts (excluding terminated)."""
    instances = []
    paginator = client.get_paginator("describe_instances")
    for page in paginator.paginate():
        for res in page["Reservations"]:
            for inst in res["Instances"]:
                if inst["State"]["Name"] != "terminated":
                    instances.append(inst)
    return instances


class TestInstanceCreationCountAndIdFormat:
    """Property 1: Instance creation returns correct count with valid IDs."""

    @given(count=counts, name=names)
    @settings(max_examples=30, deadline=None)
    def test_create_returns_correct_count_with_valid_ids(self, count: int, name: str):
        """Creating N instances yields exactly N instances with valid IDs."""
        with mock_aws():
            client = boto3.client("ec2", region_name="us-east-1")

            result = runner.invoke(instances_app, [
                "create",
                "--ami", "ami-12345678",
                "--instance-type", "t2.micro",
                "--count", str(count),
                "--name", name,
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"

            instances = _get_all_instances(client)
            assert len(instances) == count, (
                f"Expected {count} instances, got {len(instances)}"
            )

            for inst in instances:
                iid = inst["InstanceId"]
                assert INSTANCE_ID_PATTERN.match(iid), (
                    f"Instance ID '{iid}' does not match i-[0-9a-f]+"
                )

    @given(count=counts, name=names)
    @settings(max_examples=30, deadline=None)
    def test_name_tag_applied_to_all_instances(self, count: int, name: str):
        """Every created instance gets a Name tag matching the provided name."""
        with mock_aws():
            client = boto3.client("ec2", region_name="us-east-1")

            result = runner.invoke(instances_app, [
                "create",
                "--ami", "ami-12345678",
                "--instance-type", "t2.micro",
                "--count", str(count),
                "--name", name,
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"

            instances = _get_all_instances(client)
            assert len(instances) == count

            for inst in instances:
                tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                assert tags.get("Name") == name, (
                    f"Instance {inst['InstanceId']} Name tag is "
                    f"'{tags.get('Name')}', expected '{name}'"
                )

    @mock_aws
    def test_concrete_single_instance(self):
        """Concrete: creating 1 instance returns exactly 1 valid ID."""
        client = boto3.client("ec2", region_name="us-east-1")

        result = runner.invoke(instances_app, [
            "create", "--ami", "ami-12345678", "--instance-type", "t2.micro",
            "--count", "1", "--name", "single",
        ])
        assert result.exit_code == 0

        instances = _get_all_instances(client)
        assert len(instances) == 1
        assert INSTANCE_ID_PATTERN.match(instances[0]["InstanceId"])

    @mock_aws
    def test_concrete_multiple_instances_with_name(self):
        """Concrete: creating 3 named instances returns 3 IDs all tagged."""
        client = boto3.client("ec2", region_name="us-east-1")

        result = runner.invoke(instances_app, [
            "create", "--ami", "ami-12345678", "--instance-type", "t2.micro",
            "--count", "3", "--name", "test-server",
        ])
        assert result.exit_code == 0

        instances = _get_all_instances(client)
        assert len(instances) == 3

        for inst in instances:
            assert INSTANCE_ID_PATTERN.match(inst["InstanceId"])
            tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
            assert tags["Name"] == "test-server"
