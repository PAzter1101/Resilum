import inspect

from covert.rendezvous import endpoint_responder


def test_responder_returns_endpoint():
    respond = endpoint_responder(b"icmp:203.0.113.9")
    assert respond("endpoint", None, b"rid", None, 0.0) == b"icmp:203.0.113.9"


def test_responder_has_the_signature_rns_dispatches_on():
    # RNS calls request handlers only when the signature has 5 or 6 params;
    # a *args callable (len==1) is rejected and the request silently hangs.
    assert len(inspect.signature(endpoint_responder(b"x")).parameters) == 5
