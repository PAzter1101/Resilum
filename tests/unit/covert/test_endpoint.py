from covert.endpoint import pack_endpoint, parse_endpoint


def test_round_trip():
    assert parse_endpoint(pack_endpoint("icmp", "203.0.113.9")) == (
        "icmp",
        "203.0.113.9",
    )


def test_addr_with_colon_keeps_remainder():
    assert parse_endpoint(pack_endpoint("dns", "t.example.com:53")) == (
        "dns",
        "t.example.com:53",
    )


def test_missing_addr_returns_none():
    assert parse_endpoint(b"icmp") is None


def test_empty_returns_none():
    assert parse_endpoint(b"") is None


def test_non_utf8_returns_none():
    assert parse_endpoint(b"\xff\xfe") is None
