"""Compatibility entry point for platforms expecting an app.py module."""

from delibra.main import app, run

__all__ = ["app", "run"]


if __name__ == "__main__":
    run()
