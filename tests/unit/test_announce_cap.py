from types import SimpleNamespace

from rns_tcp_bridge.announce_cap import CAP_BUSY, CAP_IDLE, CapController


def _iface(rxb=0, txb=0):
    return SimpleNamespace(rxb=rxb, txb=txb, announce_cap=0.02)


def test_attach_sets_idle_cap():
    ifc = _iface()
    CapController().attach(ifc)
    assert ifc.announce_cap == CAP_IDLE


def test_traffic_drops_cap_then_recovers_after_cooldown():
    ctl = CapController()
    ifc = _iface()
    ctl.attach(ifc)
    ifc.txb = 4000  # ~2000 B/s over the 2s window → busy
    ctl.tick(now=10.0)
    assert ifc.announce_cap == CAP_BUSY
    ctl.tick(now=12.0)  # no new traffic but within cooldown → stays busy
    assert ifc.announce_cap == CAP_BUSY
    ctl.tick(now=20.0)  # cooldown elapsed, still idle → back to idle
    assert ifc.announce_cap == CAP_IDLE


def test_light_traffic_stays_idle():
    ctl = CapController()
    ifc = _iface()
    ctl.attach(ifc)
    ifc.txb = 100  # 50 B/s → below the busy threshold
    ctl.tick(now=10.0)
    assert ifc.announce_cap == CAP_IDLE
