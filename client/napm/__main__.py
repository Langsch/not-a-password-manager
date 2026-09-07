"""Entry point: `napm`, or `python -m napm`."""

from __future__ import annotations

import argparse

from napm.app import NapmApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="napm",
        description="Terminal client for not-a-password-manager.",
    )

    parser.add_argument(
        "--base-url",
        default=None,
        help="Address of the API, e.g. http://localhost:8000. Remembered after signing in.",
    )

    arguments = parser.parse_args()

    app = NapmApp(base_url=arguments.base_url)

    app.run()


if __name__ == "__main__":
    main()
