"""Filter egress candidates by the own/others policy and country rules.

own/others `use_own`:
  "true"  -> own candidates allowed everywhere
  "false" -> own candidates never used (others only)
  "smart" -> own allowed for every service EXCEPT socks-egress, where using
             your own exit would expose your real public IP with no benefit.
Others are never excluded by this filter — only own candidates can be.
"""

_SMART_OWN_EXCLUDED = {"socks-egress"}


def _own_allowed(service: str, use_own: str) -> bool:
    if use_own == "true":
        return True
    if use_own == "false":
        return False
    return service not in _SMART_OWN_EXCLUDED


def _country_allowed(country: str, allow: list, deny: list) -> bool:
    filter_active = bool(allow) or bool(deny)
    if filter_active and country == "*":
        return False  # cannot guarantee an unknown exit avoids a forbidden country
    if deny and country in deny:
        return False
    if allow and country not in allow:
        return False
    return True


def eligible(candidates, use_own, allow_countries, deny_countries, skip_hashes):
    out = []
    for cand in candidates:
        if not cand.healthy:
            continue
        is_own = cand.dest_hash in skip_hashes.get(cand.service, set())
        if is_own and not _own_allowed(cand.service, use_own):
            continue
        if not _country_allowed(cand.exit_country, allow_countries, deny_countries):
            continue
        out.append(cand)
    return out
