"""Unit tests for the bridge-supervisor YAML loader.

Validates the configuration format without actually spawning any
processes. Touches no network, no Reticulum stack, no disk besides
the temporary file pytest creates.
"""

import textwrap

import pytest

from supervisor import load


def write(tmp_path, text):
    path = tmp_path / "bridges.yaml"
    path.write_text(textwrap.dedent(text))
    return str(path)


def test_loads_listen_and_connect(tmp_path):
    path = write(tmp_path, """
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
    """)
    specs = load(path)
    assert len(specs) == 2
    assert specs[0].mode == "listen"  and specs[0].target is None
    assert specs[1].mode == "connect" and specs[1].target == "deadbeef"


def test_empty_or_missing_bridges_section_returns_no_specs(tmp_path):
    assert load(write(tmp_path, "")) == []
    assert load(write(tmp_path, "bridges: []")) == []


def test_unknown_mode_aborts(tmp_path):
    path = write(tmp_path, """
        bridges:
          - mode: bogus
            identity: /tmp/x.id
            tcp: 127.0.0.1:1
    """)
    with pytest.raises(SystemExit, match="must be 'listen' or 'connect'"):
        load(path)


def test_connect_without_target_aborts(tmp_path):
    path = write(tmp_path, """
        bridges:
          - mode: connect
            identity: /tmp/c.id
            tcp: 127.0.0.1:1
    """)
    with pytest.raises(SystemExit, match="no 'target'"):
        load(path)


def test_default_service_when_omitted(tmp_path):
    path = write(tmp_path, """
        bridges:
          - mode: listen
            identity: /tmp/l.id
            tcp: 127.0.0.1:9000
    """)
    [spec] = load(path)
    assert spec.service == "generic"
