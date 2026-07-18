from covert.poll import AdaptivePoll


def test_starts_at_min_interval():
    p = AdaptivePoll(min_interval=0.1, max_interval=4.0)
    assert p.interval() == 0.1


def test_backs_off_when_idle():
    p = AdaptivePoll(min_interval=0.1, max_interval=4.0)
    p.observe(had_traffic=False)
    p.observe(had_traffic=False)
    assert p.interval() > 0.1


def test_caps_at_max():
    p = AdaptivePoll(min_interval=0.1, max_interval=0.4)
    for _ in range(20):
        p.observe(had_traffic=False)
    assert p.interval() == 0.4


def test_resets_on_traffic():
    p = AdaptivePoll(min_interval=0.1, max_interval=4.0)
    for _ in range(5):
        p.observe(had_traffic=False)
    p.observe(had_traffic=True)
    assert p.interval() == 0.1
