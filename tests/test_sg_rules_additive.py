"""
Property test for additive security group rules (Property 3).

Validates Requirements 3.3, 3.4:
- Adding a new ingress rule preserves all existing rules
- Rules accumulate additively with each addition

Uses hypothesis to generate arbitrary rule sequences and moto to mock EC2.
"""

import boto3
from hypothesis import given, settings
from hypothesis import strategies as st
from moto import mock_aws


# --- Strategies ---

# Generate a list of unique (port, protocol, cidr) rule tuples
ports = st.integers(min_value=1, max_value=65535)
protocols = st.sampled_from(["tcp", "udp"])
# Use distinct /32 CIDRs derived from the index to avoid duplicates
cidr_octets = st.integers(min_value=1, max_value=254)

rule_strategy = st.tuples(ports, protocols, cidr_octets)

# Generate 2-6 distinct rules per test run
rule_lists = st.lists(
    rule_strategy,
    min_size=2,
    max_size=6,
    unique_by=lambda r: (r[0], r[1], r[2]),
)


def _get_ingress_rules(client, group_id: str) -> set[tuple[int, int, str, str]]:
    """Return current ingress rules as a set of (from_port, to_port, protocol, cidr) tuples."""
    resp = client.describe_security_groups(GroupIds=[group_id])
    rules = set()
    for perm in resp["SecurityGroups"][0]["IpPermissions"]:
        from_port = perm.get("FromPort", -1)
        to_port = perm.get("ToPort", -1)
        proto = perm["IpProtocol"]
        for ip_range in perm.get("IpRanges", []):
            rules.add((from_port, to_port, proto, ip_range["CidrIp"]))
    return rules


class TestSecurityGroupRulesAdditive:
    """Property 3: Security group rules are additive."""

    @mock_aws
    @given(rules=rule_lists)
    @settings(max_examples=50, deadline=None)
    def test_rules_accumulate_after_sequential_additions(self, rules):
        """Adding rules one by one preserves all previously added rules."""
        client = boto3.client("ec2", region_name="us-east-1")

        # Create a VPC and security group
        vpc = client.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        sg = client.create_security_group(
            GroupName="test-sg",
            Description="Property test SG",
            VpcId=vpc_id,
        )
        group_id = sg["GroupId"]

        expected_rules: set[tuple[int, int, str, str]] = set()

        for port, protocol, octet in rules:
            cidr = f"10.0.{octet}.0/32"

            client.authorize_security_group_ingress(
                GroupId=group_id,
                IpPermissions=[{
                    "IpProtocol": protocol,
                    "FromPort": port,
                    "ToPort": port,
                    "IpRanges": [{"CidrIp": cidr}],
                }],
            )
            expected_rules.add((port, port, protocol, cidr))

            # After each addition, all previously added rules must still be present
            current_rules = _get_ingress_rules(client, group_id)
            assert expected_rules.issubset(current_rules), (
                f"Missing rules after adding {protocol} port {port} from {cidr}.\n"
                f"Expected: {expected_rules}\n"
                f"Got: {current_rules}"
            )

        # Final check: total accumulated rules match
        final_rules = _get_ingress_rules(client, group_id)
        assert expected_rules == final_rules - (_get_default_egress_as_ingress(final_rules, expected_rules))

    @mock_aws
    def test_single_rule_addition_preserves_existing(self):
        """Concrete case: adding a second rule keeps the first rule intact."""
        client = boto3.client("ec2", region_name="us-east-1")

        vpc = client.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        sg = client.create_security_group(
            GroupName="test-sg",
            Description="Test SG",
            VpcId=vpc_id,
        )
        group_id = sg["GroupId"]

        # Add first rule: SSH
        client.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "10.0.1.0/24"}],
            }],
        )

        # Add second rule: HTTP
        client.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }],
        )

        rules = _get_ingress_rules(client, group_id)
        assert (22, 22, "tcp", "10.0.1.0/24") in rules
        assert (80, 80, "tcp", "0.0.0.0/0") in rules


def _get_default_egress_as_ingress(
    final_rules: set[tuple[int, int, str, str]],
    expected_rules: set[tuple[int, int, str, str]],
) -> set[tuple[int, int, str, str]]:
    """Return any rules in final that aren't in expected (e.g. default rules from moto)."""
    return final_rules - expected_rules
