"""Pytest configuration shared across the suite.

The smoke tests need to import the in-repo `bridges/` packages without
the operator having to set PYTHONPATH manually. Add the directory once,
here, so every test module sees it.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGES = os.path.join(ROOT, "bridges")
if BRIDGES not in sys.path:
    sys.path.insert(0, BRIDGES)
