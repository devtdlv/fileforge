"""Frozen Windows entry point for Junction (PyInstaller).

Reuses ``fileforge.main.run`` so high-DPI handling, branding, database
initialization, and exit behavior stay identical to ``python -m fileforge``.
"""

from __future__ import annotations

import sys

from fileforge.main import run


def main() -> int:
    """Launch Junction and return the process exit code."""
    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
