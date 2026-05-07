"""Shared logging configuration for the non-RNS-aware Python components
(supervisor, scripts/). Output format mirrors RNS.log so messages from
the supervisor blend with Reticulum's own log lines in `docker logs`.
"""

import logging
import sys

_LEVEL_NAMES = {
    "DEBUG": "Debug",
    "INFO": "Info",
    "WARNING": "Warning",
    "ERROR": "Error",
    "CRITICAL": "Critical",
}


class _RnsStyleFormatter(logging.Formatter):
    def format(self, record):
        record.level_pretty = _LEVEL_NAMES.get(record.levelname, record.levelname)
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            _RnsStyleFormatter(
                "[%(asctime)s] [%(level_pretty)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logging.getLogger(name)
