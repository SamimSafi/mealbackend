"""
WSGI entrypoint disabled.

This file is intentionally left as a no-op to prevent the webserver from
automatically importing `main` during startup. If you need a WSGI entrypoint
again, configure your server to import `main:app` directly or restore this file.
"""

application = None
