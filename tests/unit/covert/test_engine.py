import RNS
from fake_carrier import FakeClientCarrier, FakeServerCarrier, _Link

from covert.client import ClientEngine
from covert.server import ServerEngine
from covert.session import SessionTable


def _feed(engine, carrier, now):
    carrier.sniff(lambda raw: engine.on_received(raw, now), stop=None)


def _pump(client, cc, server, sc, rounds=25):
    for i in range(rounds):
        now = float(i)
        client.poll(now)
        _feed(server, sc, now)
        server.poll(now)
        _feed(client, cc, now)


def test_uplink_bytes_reach_server():
    server_id = RNS.Identity()
    link = _Link()
    got = []
    cc, sc = FakeClientCarrier(link), FakeServerCarrier(link)
    client = ClientEngine(cc, server_id, session_id=1)
    server = ServerEngine(sc, server_id, on_output=lambda p, b: got.append((p, b)))
    client.write(b"hello world")
    _pump(client, cc, server, sc)
    assert b"".join(b for _, b in got) == b"hello world"


def test_downlink_reaches_client_via_broadcast():
    server_id = RNS.Identity()
    link = _Link()
    got = []
    cc, sc = FakeClientCarrier(link), FakeServerCarrier(link)
    client = ClientEngine(
        cc, server_id, session_id=1, on_output=got.append, max_poll=4.0
    )
    server = ServerEngine(sc, server_id)
    for i in range(3):
        now = float(i)
        client.poll(now)
        _feed(server, sc, now)
        _feed(client, cc, now)
    server.broadcast(b"downstream")
    _pump(client, cc, server, sc)
    assert b"".join(got) == b"downstream"


def test_recovers_from_dropped_handshake():
    server_id = RNS.Identity()
    link = _Link()
    got = []
    cc, sc = FakeClientCarrier(link, drop={1}), FakeServerCarrier(link)
    client = ClientEngine(cc, server_id, session_id=1)
    server = ServerEngine(sc, server_id, on_output=lambda p, b: got.append((p, b)))
    client.write(b"reliable")
    _pump(client, cc, server, sc, rounds=40)
    assert b"".join(b for _, b in got) == b"reliable"


def test_wrong_server_identity_never_establishes():
    link = _Link()
    got = []
    cc, sc = FakeClientCarrier(link), FakeServerCarrier(link)
    client = ClientEngine(cc, RNS.Identity(), session_id=1)
    server = ServerEngine(sc, RNS.Identity(), on_output=lambda p, b: got.append(b))
    client.write(b"secret")
    _pump(client, cc, server, sc, rounds=30)
    assert got == []


def test_two_clients_demuxed():
    server_id = RNS.Identity()
    la, lb = _Link(), _Link()
    got = []
    table = SessionTable(lambda _reply_to: 43, window=8)
    cca, ccb = FakeClientCarrier(la, peer="A"), FakeClientCarrier(lb, peer="B")
    sca, scb = FakeServerCarrier(la), FakeServerCarrier(lb)
    ca = ClientEngine(cca, server_id, session_id=10)
    cb = ClientEngine(ccb, server_id, session_id=20)
    sa = ServerEngine(sca, server_id, table=table, on_output=lambda p, b: got.append(b))
    sb = ServerEngine(scb, server_id, table=table, on_output=lambda p, b: got.append(b))
    ca.write(b"aaa")
    cb.write(b"bbb")
    for i in range(25):
        now = float(i)
        ca.poll(now)
        cb.poll(now)
        _feed(sa, sca, now)
        _feed(sb, scb, now)
        _feed(ca, cca, now)
        _feed(cb, ccb, now)
    joined = b"".join(got)
    assert b"aaa" in joined and b"bbb" in joined


def test_idle_link_backs_off_and_traffic_resets_poll():
    server_id = RNS.Identity()
    link = _Link()
    cc, sc = FakeClientCarrier(link), FakeServerCarrier(link)
    client = ClientEngine(cc, server_id, session_id=1, min_poll=0.2, max_poll=8.0)
    server = ServerEngine(sc, server_id)
    for i in range(20):  # establish, then poll idle with no traffic
        now = float(i)
        client.poll(now)
        _feed(server, sc, now)
        server.poll(now)
        _feed(client, cc, now)
    assert client._poll.interval() == 8.0  # dormant link backed off to max
    client.write(b"x")  # uplink from RNS
    client.poll(20.0)
    assert client._poll.interval() == 0.2  # traffic snapped it back to min
