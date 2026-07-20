"""Pick the egress candidate for a new connection: globally lowest
effective_latency among eligible candidates, with hysteresis so the
choice does not flap between near-equal candidates."""

MIN_REL = 0.10  # challenger must be >10% faster ...
MIN_ABS = 0.010  # ... AND >10 ms faster to displace the current best


def choose_best(eligible, current, min_rel=MIN_REL, min_abs=MIN_ABS):
    if not eligible:
        return None
    measured = [c for c in eligible if c.effective_latency is not None]
    if not measured:
        return eligible[0]  # nothing probed yet; use any eligible candidate
    fastest = min(measured, key=lambda c: c.effective_latency)
    if current not in eligible or current.effective_latency is None:
        return fastest
    if fastest is current:
        return current
    cur = current.effective_latency
    gain = cur - fastest.effective_latency
    if gain > min_abs and gain / cur > min_rel:
        return fastest
    return current
