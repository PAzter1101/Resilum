"""Verify the major-only peer-compatibility predicate behaves the way
the policy declares: same major = compatible, different major =
not, malformed strings always reject."""

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

from rns_tcp_bridge import version as module


@pytest.mark.parametrize(
    "ours,other",
    [
        ("0.5.2", "0.5.3"),
        ("0.5.2", "0.6.0"),
        ("0.0.0", "0.5.2"),
        ("1.0.0", "1.5.2"),
        ("2.4.1", "2.0.0"),
        ("0.5.2", "0.5.2-rc.1"),
        ("0.5.2-rc.1", "0.5.3"),
    ],
)
def test_compatible_when_majors_match(ours, other):
    assert module.is_compatible(other, ours=ours)
    assert module.is_compatible(ours, ours=other)


@pytest.mark.parametrize(
    "ours,other",
    [
        ("0.5.2", "1.0.0"),
        ("1.5.0", "2.0.0"),
        ("1.0.0", "0.99.99"),
    ],
)
def test_incompatible_when_majors_differ(ours, other):
    assert not module.is_compatible(other, ours=ours)
    assert not module.is_compatible(ours, ours=other)


@pytest.mark.parametrize(
    "ours,other",
    [
        ("dev", "0.5.2"),
        ("0.5.2", "dev"),
        ("0.5.2", ""),
        ("", "0.5.2"),
        ("0.5", "0.5.0"),
        ("v0.5.2", "0.5.2"),
        ("0.5.2", "garbage"),
    ],
)
def test_malformed_versions_are_incompatible(ours, other):
    assert not module.is_compatible(other, ours=ours)
