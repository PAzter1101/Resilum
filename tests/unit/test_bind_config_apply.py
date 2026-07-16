"""Tests for applying renders to files: env handling and the fatal path."""

import pytest
from bind_samples import YGG_SAMPLE

import bind_config as rbc


def test_render_file_unset_env_leaves_file(tmp_path):
    p = tmp_path / "yggdrasil.conf"
    p.write_text(YGG_SAMPLE)
    rbc.render_file(
        str(p), "ygg-public-listen", "RESILUM_YGG_PUBLIC_LISTEN", rbc.render_ygg
    )
    assert p.read_text() == YGG_SAMPLE


def test_render_file_applies_when_env_set(tmp_path, monkeypatch):
    p = tmp_path / "yggdrasil.conf"
    p.write_text(YGG_SAMPLE)
    monkeypatch.setenv("RESILUM_YGG_PUBLIC_LISTEN", "tcp://203.0.113.10:65533")
    rbc.render_file(
        str(p), "ygg-public-listen", "RESILUM_YGG_PUBLIC_LISTEN", rbc.render_ygg
    )
    assert '"tcp://203.0.113.10:65533"' in p.read_text()


def test_render_file_malformed_env_is_fatal(tmp_path, monkeypatch):
    p = tmp_path / "yggdrasil.conf"
    p.write_text(YGG_SAMPLE)
    monkeypatch.setenv("RESILUM_YGG_PUBLIC_LISTEN", "not-a-uri")
    with pytest.raises(SystemExit) as exc:
        rbc.render_file(
            str(p), "ygg-public-listen", "RESILUM_YGG_PUBLIC_LISTEN", rbc.render_ygg
        )
    assert exc.value.code == 2
    assert p.read_text() == YGG_SAMPLE


def test_render_file_markers_absent_is_noop_warning(tmp_path, monkeypatch):
    p = tmp_path / "old.conf"
    legacy = '{ Listen: [ "tcp://0.0.0.0:65533" ] }\n'
    p.write_text(legacy)
    monkeypatch.setenv("RESILUM_YGG_PUBLIC_LISTEN", "tcp://203.0.113.10:65533")
    rbc.render_file(
        str(p), "ygg-public-listen", "RESILUM_YGG_PUBLIC_LISTEN", rbc.render_ygg
    )
    assert p.read_text() == legacy
