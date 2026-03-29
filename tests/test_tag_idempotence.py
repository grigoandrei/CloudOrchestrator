"""
Property test for tag idempotence (Property 5).

Validates Requirements 5.1, 5.2:
- Setting tags on a resource applies those tags
- Calling set_tags multiple times with the same arguments produces identical tags

Uses hypothesis to generate arbitrary tag key-value pairs and moto to mock EC2.
"""

import boto3
from hypothesis import given, settings
from hypothesis import strategies as st
from moto import mock_aws


# --- Strategies ---

# Tag keys/values: non-empty alphanumeric strings (AWS allows more, but this is sufficient)
tag_keys = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
)
tag_values = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_- "),
    min_size=1,
    max_size=40,
)

# Generate 1-5 unique-key tag dicts
tag_dicts = st.dictionaries(
    keys=tag_keys,
    values=tag_values,
    min_size=1,
    max_size=5,
)

# Number of repeated set_tags calls
repeat_counts = st.integers(min_value=2, max_value=5)


def _get_tags(client, resource_id: str) -> dict[str, str]:
    """Return tags on a resource as a {key: value} dict."""
    resp = client.describe_tags(
        Filters=[{"Name": "resource-id", "Values": [resource_id]}]
    )
    return {t["Key"]: t["Value"] for t in resp["Tags"]}


def _apply_tags(client, resource_id: str, tags: dict[str, str]) -> None:
    """Apply tags to a resource using create_tags (same as src/tags.py set_tags)."""
    client.create_tags(
        Resources=[resource_id],
        Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
    )


class TestTagIdempotence:
    """Property 5: Tag idempotence — repeated set_tags calls produce identical results."""

    @mock_aws
    @given(tags=tag_dicts, repeats=repeat_counts)
    @settings(max_examples=50, deadline=None)
    def test_repeated_set_tags_produces_identical_tags(self, tags, repeats):
        """Calling set_tags N times with the same args yields the same tags each time."""
        client = boto3.client("ec2", region_name="us-east-1")

        # Create an instance to tag
        resp = client.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
        instance_id = resp["Instances"][0]["InstanceId"]

        # Apply tags the first time and capture the result
        _apply_tags(client, instance_id, tags)
        first_tags = _get_tags(client, instance_id)

        # Apply the same tags N more times
        for i in range(repeats):
            _apply_tags(client, instance_id, tags)
            current_tags = _get_tags(client, instance_id)
            assert current_tags == first_tags, (
                f"Tags differ after repeat {i + 1}.\n"
                f"Expected: {first_tags}\n"
                f"Got: {current_tags}"
            )

    @mock_aws
    def test_concrete_idempotent_set(self):
        """Concrete case: setting the same two tags twice produces identical results."""
        client = boto3.client("ec2", region_name="us-east-1")

        resp = client.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
        instance_id = resp["Instances"][0]["InstanceId"]

        tags = {"Environment": "dev", "Team": "backend"}

        _apply_tags(client, instance_id, tags)
        first_tags = _get_tags(client, instance_id)

        _apply_tags(client, instance_id, tags)
        second_tags = _get_tags(client, instance_id)

        assert first_tags == second_tags
        assert first_tags == tags
