#!/usr/bin/env python3
"""CLI shim: delegates to bind_config.apply.main.

Logic lives in bridges/bind_config/ (importable as bind_config at runtime
because PYTHONPATH=/opt/resilum/bridges is set in the container).
"""

import sys

from bind_config.apply import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
