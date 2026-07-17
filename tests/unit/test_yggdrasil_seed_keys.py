"""Unit tests for the Yggdrasil keypair-splicing helper.

Verifies that the regex-based replacement preserves comments and
formatting around the keys, and that already-populated configs are
left alone.
"""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPEC = importlib.util.spec_from_file_location(
    "yggdrasil_seed_keys",
    os.path.join(ROOT, "scripts", "yggdrasil_seed_keys.py"),
)
seed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seed)


SAMPLE_CONFIG = """\
# Header comment
{
  PrivateKey: ""

  Listen: [
    "tcp://127.0.0.1:9000"
  ]
}
"""


def test_splice_replaces_empty_private_key():
    out = seed.splice(SAMPLE_CONFIG, {"PrivateKey": "deadbeef"})
    assert "PrivateKey: deadbeef" in out
    assert "Listen:" in out  # rest of file untouched
    assert "# Header comment" in out  # comments preserved


def test_splice_only_runs_once_per_key():
    text = """
    PrivateKey: ""
    PrivateKey: ""
    """
    out = seed.splice(text, {"PrivateKey": "aaaa"})
    assert out.count("PrivateKey: aaaa") == 1
    assert out.count('PrivateKey: ""') == 1
