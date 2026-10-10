# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""MCP bridge component (see the qutebrowser.mcp package).

Responsibilities:

- create the Qt-thread bridge invoker on startup,
- start the native MCP server when ``mcp.enabled`` is true,
- react to ``mcp.enabled`` / ``mcp.port`` config changes,
- provide the ``:mcp-*`` commands.

The heavy lifting lives in :mod:`qutebrowser.mcp`; this module is only
wiring.
"""

import logging

from qutebrowser.api import cmdutils, config, hook, message, apitypes

from qutebrowser.mcp import bridge, security, token

logger = logging.getLogger('mcp')


def _server():
    """The MCP server module (imported lazily)."""
    from qutebrowser.mcp import server
    return server


def _maybe_start() -> None:
    """Start the MCP server if enabled (never aborts startup on failure)."""
    if not config.val.mcp.enabled:
        return
    try:
        info = _server().start(config.val.mcp.port)
        logger.info(f'MCP server running on {info["url"]}')
    except Exception as e:  # noqa: BLE001
        logger.exception('MCP server failed to start')
        message.error(f'MCP: failed to start server: {e}')


@hook.init()
def init(context: apitypes.InitContext) -> None:
    """Create the bridge and optionally start the server."""
    bridge.init_invoker()
    _maybe_start()


@hook.config_changed('mcp.enabled')
def on_enabled_changed() -> None:
    """Start/stop the server when mcp.enabled changes."""
    if config.val.mcp.enabled:
        _maybe_start()
    else:
        _server().stop()


@hook.config_changed('mcp.port')
def on_port_changed() -> None:
    """Restart the server on a port change (when enabled)."""
    if config.val.mcp.enabled:
        _server().stop()
        _maybe_start()


@cmdutils.register(name='mcp-start')
def mcp_start() -> None:
    """Start the MCP server (enables it in the config as well)."""
    if not config.val.mcp.enabled:
        config.instance.set_obj('mcp.enabled', True, save_yaml=True)
    _maybe_start()
    info = _server().status()
    if info['running']:
        message.info(f'MCP: listening on {info["url"]} '
                     '(see :mcp-token for the token)')


@cmdutils.register(name='mcp-stop')
def mcp_stop() -> None:
    """Stop the MCP server for this session (config stays enabled)."""
    _server().stop()
    message.info('MCP: server stopped')


@cmdutils.register(name='mcp-status')
def mcp_status() -> None:
    """Show the MCP server status and session permissions."""
    info = _server().status()
    if info['running']:
        parts = [f'MCP: listening on {info["url"]}']
    else:
        parts = [f'MCP: stopped (mcp.enabled={config.val.mcp.enabled})']
    allowed = security.session_allowed()
    if allowed:
        parts.append('session-approved origins: ' + ', '.join(allowed))
    else:
        parts.append('no session-approved origins yet')
    message.info(' | '.join(parts))


@cmdutils.register(name='mcp-token')
def mcp_token() -> None:
    """Show the MCP bearer token."""
    message.info(f'MCP token: {token.get_token()}')


@cmdutils.register(name='mcp-revoke')
def mcp_revoke() -> None:
    """Revoke all session permissions granted to the MCP agent."""
    security.revoke_session()
    message.info('MCP: revoked all session permissions')

@cmdutils.register(name='mcp-log')
def mcp_log(count: int = 10) -> None:
    """Show the most recent MCP audit entries (default: last 10)."""
    import json as _json

    from qutebrowser.mcp import audit as mcp_audit

    path = mcp_audit._log_path()
    if not path.exists():
        message.info(f'MCP: no audit log yet ({path})')
        return
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    count = max(1, min(count, 50))
    parts = []
    for line in lines[-count:]:
        try:
            entry = _json.loads(line)
        except ValueError:
            continue
        ts = str(entry.get('ts', ''))[11:19]
        tool = str(entry.get('tool', '?'))
        decision = str(entry.get('decision') or '')
        flag = '!' if entry.get('high_risk') else ''
        parts.append(f'{ts} {tool}{flag} {decision}'.strip())
    if not parts:
        message.info(f'MCP: audit log empty ({path})')
        return
    message.info(' | '.join(parts) + f' - log: {path}')
