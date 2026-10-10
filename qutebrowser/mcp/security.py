# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Per-origin consent and policy for MCP-driven browsing.

Policy model (v1):

- An *origin* is ``scheme://host[:port]`` with default ports stripped.
- An origin is allowed if it matches one of the urlmatch patterns in the
  ``mcp.allow_origins`` setting, or if the user granted it for this
  session through the consent prompt.
- The consent prompt is a blocking, modal-style question shown in the
  status bar (``message.ask``); the safe default is *deny*.
- Everything (grant and deny) is recorded in the audit log.

All functions in this module are intended to run on the Qt main thread
(``ops`` calls them from its Qt-thread jobs).
"""

import html
import logging
from urllib.parse import urlsplit

from qutebrowser.config import config
from qutebrowser.qt.core import QUrl
from qutebrowser.utils import message, usertypes, urlmatch

from qutebrowser.mcp import audit

logger = logging.getLogger('mcp')

# Origins allowed for this session ("Allow once/for now" answers).
_session_allowed: set[str] = set()


def origin_of(url: str) -> str | None:
    """Return the normalized origin for a URL, or None for non-web URLs.

    Normalization: lowercase scheme/host, default ports (80/443) stripped.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return None
    host = parts.hostname.lower()
    try:
        port = parts.port
    except ValueError:
        return None
    if port is not None and not (
            (parts.scheme == 'http' and port == 80) or
            (parts.scheme == 'https' and port == 443)):
        host = f'{host}:{port}'
    return f'{parts.scheme}://{host}'


def _config_patterns() -> list[str]:
    """The configured allow-origin patterns (monkeypatched in tests)."""
    try:
        patterns = config.val.mcp.allow_origins
    except Exception:  # noqa: BLE001 - config may not be initialized in tests
        return []
    return list(patterns or [])


def matches_config(origin: str) -> bool:
    """Whether ``origin`` matches a pattern in ``mcp.allow_origins``."""
    url = QUrl(origin)
    for pattern in _config_patterns():
        try:
            if urlmatch.UrlPattern(pattern).matches(url):
                return True
        except ValueError as e:
            logger.warning(f'Ignoring invalid mcp.allow_origins pattern '
                           f'{pattern!r}: {e}')
    return False


def is_allowed(origin: str) -> bool:
    """Whether the origin is allowed (without prompting)."""
    return origin in _session_allowed or matches_config(origin)


def _ask_user(origin: str) -> bool | None:
    """Ask the user to grant/deny access (blocking; Qt thread only).

    Split out so tests can monkeypatch it.
    """
    text = ('An AI agent (MCP) is requesting control of '
            f'<b>{html.escape(origin)}</b>.<br/>Allow it for this session?')
    answer = message.ask(
        title='Agent access request',
        text=text,
        mode=usertypes.PromptMode.yesno,
        default=False,
    )
    return answer


def request_access(origin: str) -> bool:
    """Ensure access to ``origin``; prompt the user if needed.

    Returns True when allowed. Records the decision in the audit log.
    """
    if is_allowed(origin):
        return True
    answer = _ask_user(origin)
    if answer:
        _session_allowed.add(origin)
        audit.log_event('consent', origin=origin, decision='allow-session')
        logger.info(f'MCP access to {origin} allowed for this session')
        return True
    audit.log_event('consent', origin=origin, decision='deny')
    logger.info(f'MCP access to {origin} denied')
    return False


def session_allowed() -> list[str]:
    """Sorted list of session-allowed origins (for status output)."""
    return sorted(_session_allowed)


def revoke_session() -> None:
    """Drop all session grants."""
    _session_allowed.clear()
    audit.log_event('consent-revoke', decision='cleared')
