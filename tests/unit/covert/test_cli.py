import pytest

from covert.cli import build_parser


def test_parser_parses_client_args():
    args = build_parser().parse_args(
        ["icmp", "client", "--dst", "203.0.113.9", "--server-identity", "/id.pub"]
    )
    assert args.carrier == "icmp"
    assert args.role == "client"
    assert args.dst == "203.0.113.9"
    assert args.server_identity == "/id.pub"


def test_parser_rejects_bad_role():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["icmp", "bogus"])
