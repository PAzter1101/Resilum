from covert.icmpid import tunnel_id


def test_deterministic_for_same_key():
    assert tunnel_id(b"server-pubkey") == tunnel_id(b"server-pubkey")


def test_varies_by_key():
    assert tunnel_id(b"key-a") != tunnel_id(b"key-b")


def test_is_nonzero_16_bit():
    for key in (b"", b"x", b"a-longer-key"):
        assert 1 <= tunnel_id(key) <= 0xFFFF
