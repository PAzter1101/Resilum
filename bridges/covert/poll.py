"""Adaptive poll interval: fast under load, exponential backoff when idle."""


class AdaptivePoll:
    def __init__(self, min_interval: float, max_interval: float, factor: float = 2.0):
        self._min = min_interval
        self._max = max_interval
        self._factor = factor
        self._interval = min_interval

    def interval(self) -> float:
        return self._interval

    def observe(self, had_traffic: bool) -> None:
        if had_traffic:
            self._interval = self._min
        else:
            self._interval = min(self._max, self._interval * self._factor)
