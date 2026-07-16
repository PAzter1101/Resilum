"""Tests for the marker-region engine."""

import pytest
from bind_samples import YGG_SAMPLE

import bind_config as rbc


def test_replace_region_swaps_body_between_markers():
    out = rbc.replace_region(
        YGG_SAMPLE, "ygg-public-listen", ['    "tcp://0.0.0.0:1234"']
    )
    assert '"tcp://0.0.0.0:1234"' in out
    assert '"tcp://[::]:65533"' not in out
    assert '"tcp://127.0.0.1:9000"' in out
    assert "# >>> resilum:managed ygg-public-listen" in out


def test_replace_region_returns_none_when_markers_absent():
    assert rbc.replace_region('{ Listen: [ "x" ] }', "ygg-public-listen", ["y"]) is None


def test_replace_region_raises_on_unterminated():
    opened = (
        "# >>> resilum:managed ygg-public-listen — rendered from X\n"
        '"tcp://[::]:65533"\n'
    )
    with pytest.raises(ValueError):
        rbc.replace_region(opened, "ygg-public-listen", ["y"])
