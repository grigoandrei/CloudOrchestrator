"""
Property test for tag removal preserving unrelated tags (Property 6).

Validates Requirements 5.3, 5.4:
- Removing a subset of tag keys deletes only those keys
- All other tags remain unchanged after removal

Uses hypothesis to generate arbitrary tag sets and removal subsets, moto to mock EC2.
"""

import boto3
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from moto import mock_aws


# --- Strategies ---

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

# Generate 2-6 unique-key tags so we always have keys to remove AND keys to keep
tag_dicts = st.dictionaries(
    keys=tag_keys,
    values=tag_values,
    min_size=2,
    max_size=6,
)


def _get_tags(client, resource_id: str) -> dict[str, str]:
    resp = client.describe_tags(
        Filters=[{"Name": "resource-id", "Values": [resource_id]}]
    )
    return {t["Key"]: t["Value"] for t in resp["Tags"]}


def _apply_tags(client, resource_id: str, tags: dict[str, str]) -> None:
    client.create_tags(
        Resources=[resource_id],
        Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
    )


class TestTagRemovalPreservesUnrelated:
    """Property 6: Removing a subset of tag keys leaves all other tags unchanged."""

    @mock_aws
    @given(data=st.data())
    @settings(max_examples=50, deadline=None)
    def test_removal_preserves_remaining_tags(self, data):
        """Remove a random non-empty proper subset of keys; remaining tags stay intact."""
        tags = data.draw(tag_dicts)
        all_keys = list(tags.keys())
        assume(len(all_keys) >= 2)

        # Pick a non-empty proper subset to remove (at least 1, at most len-1)
        keys_to_remove = data.draw(
            st.lists(
                st.sampled_from(all_keys),
                min_size=1,
                max_size=len(all_keys) - 1,
                unique=True,
            )
        )

        client = boto3.client("ec2", region_name="us-east-1")
        resp = client.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
        instance_id = resp["Instances"][0]["InstanceId"]

        # Set all tags
        _apply_tags(client, instance_id, tags)

        # Remove the subset
        client.delete_tags(
            Resources=[instance_id],
            Tags=[{"Key": k} for k in keys_to_remove],
        )

        remaining = _get_tags(client, instance_id)

        # Removed keys should be gone
        for k in keys_to_remove:
            assert k not in remaining, f"Key '{k}' should have been removed"

        # Surviving keys should be unchanged
        expected = {k: v for k, v in tags.items() if k not in keys_to_remove}
        assert remaining == expected, (
            f"Remaining tags differ.\nExpected: {expected}\nGot: {remaining}"
        )

    @mock_aws
    def test_concrete_removal_preserves_other_tags(self):
        """Concrete case: remove one tag, verify the others are untouched."""
        client = boto3.client("ec2", region_name="us-east-1")
        resp = client.run_instances(ImageId="ami-12345678", MinCount=1, MaxCount=1)
        instance_id = resp["Instances"][0]["InstanceId"]

        tags = {"Environment": "dev", "Team": "backend", "Owner": "alice"}
        _apply_tags(client, instance_id, tags)

        # Remove only "Team"
        client.delete_tags(
            Resources=[instance_id],
            Tags=[{"Key": "Team"}],
        )

        remaining = _get_tags(client, instance_id)
        assert remaining == {"Environment": "dev", "Owner": "alice"}
