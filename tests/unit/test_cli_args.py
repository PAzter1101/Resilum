from rns_tcp_bridge.cli import _build_parser


def test_connect_parses_new_flags():
    args = _build_parser().parse_args(
        [
            "connect",
            "--identity",
            "x",
            "--tcp",
            "127.0.0.1:1",
            "--service",
            "tor",
            "--use-own",
            "false",
            "--allow-country",
            "NL",
            "--allow-country",
            "DE",
            "--deny-country",
            "CN",
        ]
    )
    assert args.use_own == "false"
    assert args.allow_country == ["NL", "DE"]
    assert args.deny_country == ["CN"]


def test_connect_defaults():
    args = _build_parser().parse_args(
        ["connect", "--identity", "x", "--tcp", "y", "--service", "tor"]
    )
    assert args.use_own == "smart"
    assert args.allow_country == [] and args.deny_country == []


def test_listen_parses_exit_country():
    args = _build_parser().parse_args(
        [
            "listen",
            "--identity",
            "x",
            "--tcp",
            "127.0.0.1:9050",
            "--service",
            "socks-egress",
            "--exit-country",
            "DE",
        ]
    )
    assert args.exit_country == "DE"
