"""Where the server is.

Read once, before the app starts. There is deliberately no way to change it
from inside a running app: pointing a signed-in client at another server
mid-session is not a preference, it is a different installation.
"""

from __future__ import annotations

import os

API_URL_VARIABLE = "NAPM_API_URL"
DEFAULT_API_URL = "http://localhost:8000"


def api_url() -> str:
    configured = os.environ.get(API_URL_VARIABLE, "").strip()

    if not configured:
        return DEFAULT_API_URL

    return configured
