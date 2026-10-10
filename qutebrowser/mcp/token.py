# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Bearer-token storage for the MCP HTTP endpoint.

The token lives in the qutebrowser config directory as ``mcp-token`` and is
created on first use. It is never printed to logs; ``:mcp-token`` shows it
to the user on request.
"""

import os
import logging
import secrets
import pathlib

from qutebrowser.utils import standarddir

logger = logging.getLogger('mcp')

FILENAME = 'mcp-token'
TOKEN_BYTES = 32


def token_path() -> pathlib.Path:
    """Path of the token file."""
    return pathlib.Path(standarddir.config()) / FILENAME


def get_token() -> str:
    """Return the current token, creating it if needed."""
    path = token_path()
    try:
        token = path.read_text(encoding='utf-8').strip()
    except OSError:
        token = ''
    if token:
        return token
    return rotate_token()


def rotate_token() -> str:
    """Generate and store a fresh token, returning it."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(token + '\n')
    finally:
        try:
            os.chmod(path, 0o600)
        except OSError:
            # Windows ACLs say no; the file is per-user anyway.
            pass
    logger.debug('MCP token rotated')
    return token
