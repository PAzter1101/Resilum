import RNS

from covert import keyx


def _public_view(full):
    view = RNS.Identity(create_keys=False)
    view.load_public_key(full.get_public_key())
    return view


def test_seal_unseal_round_trip():
    server = RNS.Identity()
    k = keyx.new_session_key()
    token = keyx.seal(_public_view(server), k)
    assert keyx.unseal(server, token) == k


def test_wrong_identity_cannot_unseal():
    server = RNS.Identity()
    other = RNS.Identity()
    token = keyx.seal(_public_view(server), keyx.new_session_key())
    assert keyx.unseal(other, token) is None


def test_garbage_token_returns_none():
    server = RNS.Identity()
    assert keyx.unseal(server, b"not-a-valid-token") is None


def test_new_session_key_length():
    assert len(keyx.new_session_key()) == keyx.SESSION_KEY_LEN
