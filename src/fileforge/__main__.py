"""Allow ``python -m fileforge`` to launch the application."""

from fileforge.main import run

if __name__ == "__main__":
    raise SystemExit(run())
