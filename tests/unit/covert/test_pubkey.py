import RNS

from covert.pubkey import identity_from_hex


def test_identity_from_hex_round_trip():
    full = RNS.Identity()
    loaded = identity_from_hex(full.get_public_key().hex())
    assert loaded.get_public_key() == full.get_public_key()
