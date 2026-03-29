"""
Property test for volume AZ mismatch rejection (Property 4).

Validates Requirement 4.3:
- If the volume and instance are in different availability zones,
  the Volume_Manager SHALL reject the attachment and display an error
  message stating the AZ mismatch.

Uses hypothesis to generate arbitrary AZ pairs and moto to mock EC2.
"""

import boto3
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from moto import mock_aws
from typer.testing import CliRunner

from src.volumes import volume_app

runner = CliRunner()

# --- Strategies ---

# Pick two distinct AZ suffixes so volume and instance land in different zones
az_suffix = st.sampled_from(["a", "b", "c", "d", "e", "f"])
az_pairs = st.tuples(az_suffix, az_suffix).filter(lambda pair: pair[0] != pair[1])


class TestVolumeAZMismatchRejection:
    """Property 4: Volume AZ mismatch rejection."""

    @mock_aws
    @given(az_pair=az_pairs)
    @settings(max_examples=30, deadline=None)
    def test_attach_rejects_cross_az(self, az_pair):
        """Attaching a volume to an instance in a different AZ must fail
        with an error message that includes both availability zones."""
        region = "us-east-1"
        vol_az = f"{region}{az_pair[0]}"
        inst_az = f"{region}{az_pair[1]}"

        ec2_client = boto3.client("ec2", region_name=region)

        # Create a volume in vol_az
        vol = ec2_client.create_volume(
            Size=10,
            AvailabilityZone=vol_az,
            VolumeType="gp3",
        )
        volume_id = vol["VolumeId"]

        # Launch an instance — moto places it in us-east-1a by default,
        # so we use a placement override to control the AZ.
        inst = ec2_client.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            Placement={"AvailabilityZone": inst_az},
        )
        instance_id = inst["Instances"][0]["InstanceId"]

        result = runner.invoke(
            volume_app,
            ["attach", volume_id, "--instance-id", instance_id],
            env={"AWS_DEFAULT_REGION": region},
        )

        # The command must exit with a non-zero code
        assert result.exit_code != 0, (
            f"Expected non-zero exit for AZ mismatch ({vol_az} vs {inst_az}), "
            f"got exit_code={result.exit_code}"
        )

        # The error output must mention both AZs so the user knows what went wrong
        assert vol_az in result.output, (
            f"Error message should contain volume AZ '{vol_az}'. Got: {result.output}"
        )
        assert inst_az in result.output, (
            f"Error message should contain instance AZ '{inst_az}'. Got: {result.output}"
        )

    @mock_aws
    def test_same_az_attach_succeeds(self):
        """Concrete sanity check: attachment in the same AZ should succeed."""
        region = "us-east-1"
        az = f"{region}a"

        ec2_client = boto3.client("ec2", region_name=region)

        vol = ec2_client.create_volume(
            Size=10,
            AvailabilityZone=az,
            VolumeType="gp3",
        )
        volume_id = vol["VolumeId"]

        inst = ec2_client.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            Placement={"AvailabilityZone": az},
        )
        instance_id = inst["Instances"][0]["InstanceId"]

        result = runner.invoke(
            volume_app,
            ["attach", volume_id, "--instance-id", instance_id],
            env={"AWS_DEFAULT_REGION": region},
        )

        assert result.exit_code == 0, (
            f"Same-AZ attach should succeed. Got: {result.output}"
        )
        assert "Attached volume" in result.output
