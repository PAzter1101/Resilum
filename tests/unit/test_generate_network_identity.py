"""Verify the network-identity generator writes the identity, locks
down its file mode, and creates the parent directory."""

import importlib.util
import os
from unittest import mock

import pytest

pytest.importorskip("RNS", reason="Reticulum (rns) not installed")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SPEC = importlib.util.spec_from_file_location(
    "generate_network_identity",
    os.path.join(ROOT, "scripts", "generate_network_identity.py"),
)
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)


def test_main_generates_writes_chmods_and_makes_parent():
    fake_identity = mock.MagicMock()
    fake_rns = mock.MagicMock()
    fake_rns.Identity = mock.MagicMock(return_value=fake_identity)

    with (
        mock.patch.object(gen, "RNS", fake_rns),
        mock.patch("os.makedirs") as m_makedirs,
        mock.patch("os.chmod") as m_chmod,
    ):
        rc = gen.main("/var/lib/resilum/storage/identities/resilum")

    assert rc == 0
    fake_rns.Identity.assert_called_once_with()
    fake_identity.to_file.assert_called_once_with(
        "/var/lib/resilum/storage/identities/resilum"
    )
    m_makedirs.assert_called_once_with(
        "/var/lib/resilum/storage/identities", exist_ok=True
    )
    m_chmod.assert_called_once_with(
        "/var/lib/resilum/storage/identities/resilum", 0o600
    )


def test_main_skips_makedirs_when_path_has_no_parent():
    fake_identity = mock.MagicMock()
    fake_rns = mock.MagicMock()
    fake_rns.Identity = mock.MagicMock(return_value=fake_identity)

    with (
        mock.patch.object(gen, "RNS", fake_rns),
        mock.patch("os.makedirs") as m_makedirs,
        mock.patch("os.chmod"),
    ):
        rc = gen.main("identity")

    assert rc == 0
    m_makedirs.assert_not_called()
    fake_identity.to_file.assert_called_once_with("identity")
