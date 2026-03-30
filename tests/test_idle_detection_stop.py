"""
Property test for idle detection and stop correctness (Property 7).

Validates Requirements 6.3, 6.4:
- stop-idle identifies all running instances whose average CPU is below the
  threshold AND that have at least one datapoint.
- Only those instances are stopped; instances at or above the threshold
  (or with zero datapoints) remain running.

Uses hypothesis to generate varying CPU levels and thresholds, moto to mock
EC2, and unittest.mock.patch to control CloudWatch CPU responses.
"""

import os
import boto3
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from moto import mock_aws
from typer.testing import CliRunner
from unittest.mock import patch
from collections import namedtuple

from src.monitor import monitor_app, get_average_cpu

# Force boto3 default region so moto-mocked resources are found by the CLI
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# Lightweight stand-in matching the positional constructor in monitor.py
CpuMetric = namedtuple("CpuMetric", ["instance_id", "average_cpu", "max_cpu", "period_hours", "datapoints"])

runner = CliRunner()

# --- Strategies ---

# CPU average values in valid range
cpu_values = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

# Datapoint counts: 0 means no data, >0 means real metrics
datapoint_counts = st.integers(min_value=0, max_value=50)

# Threshold for idle detection
thresholds = st.floats(min_value=0.1, max_value=99.9, allow_nan=False, allow_infinity=False)

# Number of instances to create (keep small for speed)
instance_counts = st.integers(min_value=1, max_value=6)

# Per-instance strategy: (cpu_average, datapoints)
instance_cpu_profile = st.tuples(cpu_values, datapoint_counts)


def _create_running_instances(client, count: int) -> list[str]:
    """Launch `count` instances via moto and return their IDs."""
    resp = client.run_instances(ImageId="ami-12345678", MinCount=count, MaxCount=count)
    return [inst["InstanceId"] for inst in resp["Instances"]]


def _get_instance_states(client, instance_ids: list[str]) -> dict[str, str]:
    """Return {instance_id: state_name} for the given IDs."""
    resp = client.describe_instances(InstanceIds=instance_ids)
    states = {}
    for res in resp["Reservations"]:
        for inst in res["Instances"]:
            states[inst["InstanceId"]] = inst["State"]["Name"]
    return states


def _build_cpu_side_effect(profiles: dict[str, tuple[float, int]], period_hours: int = 24):
    """
    Return a function suitable for patching get_average_cpu.

    profiles: {instance_id: (avg_cpu, datapoints)}
    """
    def _side_effect(instance_id, period_hours_arg=24):
        avg, dp = profiles.get(instance_id, (0.0, 0))
        return CpuMetric(
            instance_id=instance_id,
            average_cpu=avg,
            max_cpu=avg,  # max >= avg; use same value for simplicity
            period_hours=period_hours_arg,
            datapoints=dp,
        )
    return _side_effect


class TestIdleDetectionStopCorrectness:
    """Property 7: Idle detection and stop correctness."""

    @mock_aws
    @given(
        profiles=st.lists(instance_cpu_profile, min_size=1, max_size=6),
        threshold=thresholds,
    )
    @settings(max_examples=50, deadline=None)
    def test_only_idle_instances_with_datapoints_are_stopped(self, profiles, threshold):
        """
        For any mix of CPU levels and datapoint counts, stop-idle must stop
        exactly those instances with avg CPU < threshold AND datapoints > 0.
        """
        client = boto3.client("ec2", region_name="us-east-1")
        instance_ids = _create_running_instances(client, len(profiles))

        # Build the mapping from instance ID to (cpu, datapoints)
        cpu_map = {}
        for iid, (avg_cpu, dp) in zip(instance_ids, profiles):
            cpu_map[iid] = (avg_cpu, dp)

        # Determine expected idle set
        expected_idle = {
            iid for iid, (avg, dp) in cpu_map.items()
            if dp > 0 and avg < threshold
        }
        expected_running = set(instance_ids) - expected_idle

        with patch("src.monitor.get_average_cpu", side_effect=_build_cpu_side_effect(cpu_map)):
            result = runner.invoke(monitor_app, [
                "stop-idle",
                "--threshold", str(threshold),
                "--period-hours", "24",
            ])

        # Verify the command succeeded
        assert result.exit_code == 0, f"CLI failed: {result.output}"

        # Check actual instance states
        states = _get_instance_states(client, instance_ids)

        actually_stopped = {iid for iid, st in states.items() if st in ("stopped", "stopping")}
        still_running = {iid for iid, st in states.items() if st == "running"}

        assert actually_stopped == expected_idle, (
            f"Stopped mismatch.\n"
            f"Expected stopped: {expected_idle}\n"
            f"Actually stopped:  {actually_stopped}\n"
            f"Profiles: {cpu_map}\n"
            f"Threshold: {threshold}"
        )
        assert expected_running == still_running, (
            f"Running mismatch.\n"
            f"Expected running: {expected_running}\n"
            f"Still running:    {still_running}\n"
            f"Profiles: {cpu_map}\n"
            f"Threshold: {threshold}"
        )

    @mock_aws
    def test_concrete_mixed_idle_and_active(self):
        """Concrete case: 3 instances — one idle, one active, one with no datapoints."""
        client = boto3.client("ec2", region_name="us-east-1")
        ids = _create_running_instances(client, 3)

        cpu_map = {
            ids[0]: (2.0, 5),    # idle: below threshold, has datapoints → should stop
            ids[1]: (80.0, 10),  # active: above threshold → should NOT stop
            ids[2]: (1.0, 0),    # no datapoints → should NOT stop
        }
        threshold = 5.0

        with patch("src.monitor.get_average_cpu", side_effect=_build_cpu_side_effect(cpu_map)):
            result = runner.invoke(monitor_app, [
                "stop-idle",
                "--threshold", str(threshold),
                "--period-hours", "24",
            ])

        assert result.exit_code == 0

        states = _get_instance_states(client, ids)
        assert states[ids[0]] in ("stopped", "stopping"), "Idle instance should be stopped"
        assert states[ids[1]] == "running", "Active instance should remain running"
        assert states[ids[2]] == "running", "No-datapoint instance should remain running"

    @mock_aws
    def test_no_instances_stopped_when_all_above_threshold(self):
        """When every instance is above the threshold, none should be stopped."""
        client = boto3.client("ec2", region_name="us-east-1")
        ids = _create_running_instances(client, 3)

        cpu_map = {iid: (50.0, 10) for iid in ids}
        threshold = 5.0

        with patch("src.monitor.get_average_cpu", side_effect=_build_cpu_side_effect(cpu_map)):
            result = runner.invoke(monitor_app, [
                "stop-idle",
                "--threshold", str(threshold),
                "--period-hours", "24",
            ])

        assert result.exit_code == 0
        states = _get_instance_states(client, ids)
        for iid in ids:
            assert states[iid] == "running", f"{iid} should still be running"

    @mock_aws
    def test_all_idle_instances_stopped(self):
        """When every instance is idle with datapoints, all should be stopped."""
        client = boto3.client("ec2", region_name="us-east-1")
        ids = _create_running_instances(client, 3)

        cpu_map = {iid: (1.0, 5) for iid in ids}
        threshold = 10.0

        with patch("src.monitor.get_average_cpu", side_effect=_build_cpu_side_effect(cpu_map)):
            result = runner.invoke(monitor_app, [
                "stop-idle",
                "--threshold", str(threshold),
                "--period-hours", "24",
            ])

        assert result.exit_code == 0
        states = _get_instance_states(client, ids)
        for iid in ids:
            assert states[iid] in ("stopped", "stopping"), f"{iid} should be stopped"
