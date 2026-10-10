# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.mcp.server (auth middleware + tool registration)."""

import asyncio

from qutebrowser.mcp import server
from qutebrowser.mcp import tools as tools_module


def _mk_send(store):
    async def send(message):
        store.append(message)
    return send


def _mk_receive():
    async def receive():
        return {'type': 'http.request'}
    return receive


def test_bearer_middleware_rejects_missing_token():
    called = {}

    async def app(scope, receive, send):
        called['app'] = True

    mw = server.BearerAuthMiddleware(app, token='sekrit')
    sent = []
    scope = {'type': 'http', 'headers': []}
    asyncio.run(mw(scope, _mk_receive(), _mk_send(sent)))
    assert sent and sent[0]['status'] == 401
    assert 'app' not in called


def test_bearer_middleware_rejects_wrong_token():
    called = {}

    async def app(scope, receive, send):
        called['app'] = True

    mw = server.BearerAuthMiddleware(app, token='sekrit')
    sent = []
    scope = {'type': 'http',
             'headers': [(b'authorization', b'Bearer nope')]}
    asyncio.run(mw(scope, _mk_receive(), _mk_send(sent)))
    assert sent and sent[0]['status'] == 401
    assert 'app' not in called


def test_bearer_middleware_passes_with_token():
    called = {}

    async def app(scope, receive, send):
        called['app'] = True

    mw = server.BearerAuthMiddleware(app, token='sekrit')
    scope = {'type': 'http',
             'headers': [(b'authorization', b'Bearer sekrit')]}
    asyncio.run(mw(scope, _mk_receive(), _mk_send([])))
    assert called.get('app') is True


def test_build_registers_every_tool(monkeypatch):
    monkeypatch.setattr(server.token_module, 'get_token', lambda: 'tok')
    mcp, app = server.build(8765)
    listed = asyncio.run(mcp.list_tools())
    names = sorted(t.name for t in listed)
    assert names == sorted(fn.__name__ for fn in tools_module.TOOLS)
