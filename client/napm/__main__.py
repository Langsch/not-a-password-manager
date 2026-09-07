"""Entry point: `napm`, or `python -m napm`."""

from __future__ import annotations

from napm.app import NapmApp
from napm.config import api_url


def main() -> None:
    app = NapmApp(base_url=api_url())

    app.run()


if __name__ == "__main__":
    main()
