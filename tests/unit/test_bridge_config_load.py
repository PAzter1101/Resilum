"""Bridge-supervisor YAML loading and validation (no processes spawned)."""

import textwrap

import pytest

from bridge_config import load


def write(tmp_path, text):
    path = tmp_path / "bridges.yaml"
    path.write_text(textwrap.dedent(text))
    return str(path)


def test_loads_listen_and_connect(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: listen
            service: yggdrasil
            identity: /tmp/listen.id
            tcp: 127.0.0.1:9000
          - mode: connect
            service: yggdrasil
            identity: /tmp/connect.id
            tcp: 127.0.0.1:9001
            target: deadbeef
    """,
    )
    specs = load(path)
    assert len(specs) == 2
    assert specs[0].mode == "listen" and specs[0].target is None
    assert specs[1].mode == "connect" and specs[1].target == "deadbeef"


def test_empty_or_missing_bridges_section_returns_no_specs(tmp_path):
    assert load(write(tmp_path, "")) == []
    assert load(write(tmp_path, "bridges: []")) == []


def test_unknown_mode_aborts(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: bogus
            identity: /tmp/x.id
            tcp: 127.0.0.1:1
    """,
    )
    with pytest.raises(SystemExit, match="'listen' or 'connect'"):
        load(path)


def test_connect_without_target_is_allowed(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: connect
            identity: /tmp/c.id
            tcp: 127.0.0.1:1
    """,
    )
    [spec] = load(path)
    assert spec.mode == "connect" and spec.target is None


def test_default_service_when_omitted(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: listen
            identity: /tmp/l.id
            tcp: 127.0.0.1:9000
    """,
    )
    [spec] = load(path)
    assert spec.services == ["generic"]


def test_single_service_field_becomes_singleton_list(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: listen
            service: tor
            identity: /tmp/l.id
            tcp: 127.0.0.1:9050
    """,
    )
    [spec] = load(path)
    assert spec.services == ["tor"]


def test_services_list_preserves_priority_order(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: connect
            services: [socks-egress, tor, generic]
            identity: /tmp/c.id
            tcp: 127.0.0.1:10808
    """,
    )
    [spec] = load(path)
    assert spec.services == ["socks-egress", "tor", "generic"]


def test_listen_mode_rejects_multi_service(tmp_path):
    path = write(
        tmp_path,
        """
        bridges:
          - mode: listen
            services: [a, b]
            identity: /tmp/l.id
            tcp: 127.0.0.1:9000
    """,
    )
    with pytest.raises(SystemExit, match="listen-mode wraps exactly one service"):
        load(path)


def test_env_var_expansion_with_default(tmp_path, monkeypatch):
    monkeypatch.delenv("RESILUM_TEST_PORT", raising=False)
    path = write(
        tmp_path,
        """
        bridges:
          - mode: listen
            service: socks-egress
            identity: /tmp/x.id
            tcp: 127.0.0.1:${RESILUM_TEST_PORT:-10808}
    """,
    )
    [spec] = load(path)
    assert spec.tcp == "127.0.0.1:10808"


def test_env_var_expansion_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv("RESILUM_TEST_PORT", "10807")
    path = write(
        tmp_path,
        """
        bridges:
          - mode: listen
            service: socks-egress
            identity: /tmp/x.id
            tcp: 127.0.0.1:${RESILUM_TEST_PORT:-10808}
    """,
    )
    [spec] = load(path)
    assert spec.tcp == "127.0.0.1:10807"
