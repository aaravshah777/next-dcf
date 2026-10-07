"""Make the `dcf` package importable from the test suite.

pytest's default "prepend" import mode adds each test file's own directory to
sys.path, not the repository root, so `from dcf import ...` inside tests/ would
otherwise fail at collection with ModuleNotFoundError.

The `pythonpath = .` setting in pytest.ini handles this on pytest 7 and later.
This file is the fallback: pytest always inserts the directory containing the
root conftest.py onto sys.path, so the import works on any version. Keeping
both means the suite runs whether or not the installed pytest honours the ini
option.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
