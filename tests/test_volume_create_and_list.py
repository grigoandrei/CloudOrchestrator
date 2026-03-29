"""
Unit tests for volume creation and listing.

Validates:
- Requirement 4.1: create returns a valid volume ID
- Requirement 4.4: list displays correct attachment status
"""

import boto3
import pytest
from moto import mock_aws
from typer.testing import CliRunner

from src.volumes import volume_app

runner = CliRunner()

REGION = "us-east-1"
AZ = f"{REGION}a"


class TestVolumeCreation:
    """Requirement 4.1: volume creation returns valid volume ID."""

    @mock_aws
    def test_create_returns_volume_id(self):
        result = runner.invoke(
            volume_app,
            ["create", "--size", "10", "--availability-zone", AZ, "--volume-type", "gp3"],
            env={"AWS_DEFAULT_REGION": REGION},
        )
        assert result.exit_code == 0
        assert "Created volume:" in result.output
        # moto volume IDs start with vol-
        assert "vol-" in result.output

    @mock_aws
    def test_create_with_each_volume_type(self):
        for vtype in ("gp3", "gp2", "st1", "sc1"):
            result = runner.invoke(
                volume_app,
                ["create", "--size", "500", "--availability-zone", AZ, "--volume-type", vtype],
                env={"AWS_DEFAULT_REGION": REGION},
            )
            assert result.exit_code == 0, f"Failed for volume type {vtype}: {result.output}"
            assert "Created volume:" in result.output

    @mock_aws
    def test_create_io1_requires_iops(self):
        result = runner.invoke(
            volume_app,
            ["create", "--size", "10", "--availability-zone", AZ, "--volume-type", "io1"],
            env={"AWS_DEFAULT_REGION": REGION},
        )
        assert result.exit_code != 0
        assert "iops" in result.output.lower()

    @mock_aws
    def test_create_io1_with_iops_succeeds(self):
        result = runner.invoke(
            volume_app,
            ["create", "--size", "10", "--availability-zone", AZ, "--volume-type", "io1", "--iops", "100"],
            env={"AWS_DEFAULT_REGION": REGION},
        )
        assert result.exit_code == 0
        assert "Created volume:" in result.output

    @mock_aws
    def test_create_shows_size_and_az(self):
        result = runner.invoke(
            volume_app,
            ["create", "--size", "20", "--availability-zone", AZ, "--volume-type", "gp3"],
            env={"AWS_DEFAULT_REGION": REGION},
        )
        assert "20 GiB" in result.output
        assert AZ in result.output


class TestVolumeList:
    """Requirement 4.4: list displays volumes with correct attachment status."""

    @mock_aws
    def test_list_shows_unattached_volume(self):
        ec2 = boto3.client("ec2", region_name=REGION)
        ec2.create_volume(Size=10, AvailabilityZone=AZ, VolumeType="gp3")

        result = runner.invoke(
            volume_app, ["list"], env={"AWS_DEFAULT_REGION": REGION}
        )
        assert result.exit_code == 0
        assert "vol-" in result.output
        assert "attached: none" in result.output.lower()

    @mock_aws
    def test_list_shows_attached_volume(self):
        ec2 = boto3.client("ec2", region_name=REGION)

        vol = ec2.create_volume(Size=10, AvailabilityZone=AZ, VolumeType="gp3")
        volume_id = vol["VolumeId"]

        inst = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1, MaxCount=1,
            InstanceType="t2.micro",
            Placement={"AvailabilityZone": AZ},
        )
        instance_id = inst["Instances"][0]["InstanceId"]

        ec2.attach_volume(VolumeId=volume_id, InstanceId=instance_id, Device="/dev/sdf")

        result = runner.invoke(
            volume_app, ["list"], env={"AWS_DEFAULT_REGION": REGION}
        )
        assert result.exit_code == 0
        assert instance_id in result.output

    @mock_aws
    def test_list_empty_when_no_volumes(self):
        result = runner.invoke(
            volume_app, ["list"], env={"AWS_DEFAULT_REGION": REGION}
        )
        assert result.exit_code == 0

    @mock_aws
    def test_list_shows_multiple_volumes(self):
        ec2 = boto3.client("ec2", region_name=REGION)
        v1 = ec2.create_volume(Size=10, AvailabilityZone=AZ, VolumeType="gp3")
        v2 = ec2.create_volume(Size=50, AvailabilityZone=AZ, VolumeType="gp2")

        result = runner.invoke(
            volume_app, ["list"], env={"AWS_DEFAULT_REGION": REGION}
        )
        assert result.exit_code == 0
        assert v1["VolumeId"] in result.output
        assert v2["VolumeId"] in result.output
