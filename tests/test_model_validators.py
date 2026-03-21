"""
Property tests for data model validators (Property 11).

Validates Requirements 9.1, 9.2, 9.3:
- Instance ID must match pattern i-[0-9a-f]+
- Instance state must be one of the six valid states
- Volume type must be one of: gp3, gp2, io1, st1, sc1

Uses hypothesis to generate arbitrary strings and verify validators
accept valid inputs and reject invalid ones.
"""

import re
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src.models import InstanceInfo, VolumeInfo


# --- Strategies for generating valid inputs ---

VALID_STATES = ["pending", "running", "shutting-down", "terminated", "stopping", "stopped"]
VALID_VOLUME_TYPES = ["gp3", "gp2", "io1", "st1", "sc1"]

# Generate valid instance IDs: "i-" followed by 1+ hex chars
valid_instance_ids = st.from_regex(r"i-[0-9a-f]{1,17}", fullmatch=True)

# Generate valid instance types like t2.micro, m5.xlarge, c6g.2xlarge
valid_instance_types = st.sampled_from([
    "t2.micro", "t2.small", "t2.medium", "t2.large", "t2.xlarge",
    "m5.large", "m5.xlarge", "m5.2xlarge", "c6g.metal",
    "r5.nano", "t3.medium",
])

valid_states = st.sampled_from(VALID_STATES)
valid_volume_types = st.sampled_from(VALID_VOLUME_TYPES)


def _make_instance(instance_id: str, state: str = "running", instance_type: str = "t2.micro"):
    """Helper to build an InstanceInfo with minimal required fields."""
    from datetime import datetime, timezone
    return InstanceInfo(
        instance_id=instance_id,
        instance_type=instance_type,
        state=state,
        private_ip="10.0.0.1",
        launch_time=datetime.now(timezone.utc),
        tags={"Name": "test"},
    )


def _make_volume(volume_type: str):
    """Helper to build a VolumeInfo with minimal required fields."""
    return VolumeInfo(
        volume_id="vol-abc123",
        size_gib=10,
        volume_type=volume_type,
        state="available",
        availability_zone="us-east-1a",
    )

class TestInstanceIdValidator:
    """Instance ID must match pattern i-[0-9a-f]+."""

    @given(instance_id=valid_instance_ids)
    @settings(max_examples=100)
    def test_valid_instance_ids_accepted(self, instance_id: str):
        """Valid IDs (i- followed by hex chars) are always accepted."""
        inst = _make_instance(instance_id=instance_id)
        assert inst.instance_id == instance_id

    @given(text=st.text(min_size=1, max_size=30))
    @settings(max_examples=200)
    def test_arbitrary_strings_rejected_unless_valid(self, text: str):
        """Arbitrary strings are rejected unless they match i-[0-9a-f]+."""
        is_valid = bool(re.fullmatch(r"i-[0-9a-f]+", text))
        if is_valid:
            inst = _make_instance(instance_id=text)
            assert inst.instance_id == text
        else:
            with pytest.raises(ValidationError):
                _make_instance(instance_id=text)

    @given(suffix=st.text(alphabet="ghijklmnopqrstuvwxyzGHIJKLMNOPQRSTUVWXYZ!@#$%", min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_non_hex_suffixes_rejected(self, suffix: str):
        """i- followed by non-hex characters is always rejected."""
        assume(not re.fullmatch(r"[0-9a-f]+", suffix))
        with pytest.raises(ValidationError):
            _make_instance(instance_id=f"i-{suffix}")

class TestInstanceStateValidator:
    """Instance state must be one of the six valid EC2 states."""

    @given(state=valid_states)
    @settings(max_examples=50)
    def test_valid_states_accepted(self, state: str):
        """All six valid states are accepted."""
        inst = _make_instance(instance_id="i-abc123", state=state)
        assert inst.state == state

    @given(text=st.text(min_size=1, max_size=30))
    @settings(max_examples=200)
    def test_arbitrary_strings_rejected_unless_valid_state(self, text: str):
        """Arbitrary strings are rejected unless they are a valid state."""
        if text in VALID_STATES:
            inst = _make_instance(instance_id="i-abc123", state=text)
            assert inst.state == text
        else:
            with pytest.raises(ValidationError):
                _make_instance(instance_id="i-abc123", state=text)

class TestVolumeTypeValidator:
    """Volume type must be one of: gp3, gp2, io1, st1, sc1."""

    @given(vol_type=valid_volume_types)
    @settings(max_examples=50)
    def test_valid_volume_types_accepted(self, vol_type: str):
        """All five valid volume types are accepted."""
        vol = _make_volume(volume_type=vol_type)
        assert vol.volume_type == vol_type

    @given(text=st.text(min_size=1, max_size=20))
    @settings(max_examples=200)
    def test_arbitrary_strings_rejected_unless_valid_type(self, text: str):
        """Arbitrary strings are rejected unless they are a valid volume type."""
        if text in VALID_VOLUME_TYPES:
            vol = _make_volume(volume_type=text)
            assert vol.volume_type == text
        else:
            with pytest.raises(ValidationError):
                _make_volume(volume_type=text)
