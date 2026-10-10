# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end test: real qutebrowser + MCP client over streamable HTTP.

Spawns qutebrowser (offscreen) with ``mcp.enabled=true`` on a free port,
serves a tiny local website, and drives the browser through the official
MCP client: navigate, wait, read, find, click, screenshot.
"""

import os
import sys
import json
import time
import socket
import asyncio
import pathlib
import threading
import subprocess
import http.server

import pytest

httpx2 = pytest.importorskip('httpx2')
pytest.importorskip('mcp')

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402

pytestmark = [
    pytest.mark.end2end,
    # The pytest-qt teardown hook converts GC-time socket warnings (from the
    # asyncio client under a foreign loop) into errors; ignore that one.
    pytest.mark.filterwarnings(
        'ignore:Exception ignored while finalizing socket'),
]

TOKEN_WAIT_S = 60.0

INDEX_HTML = """<!DOCTYPE html>
<html><head><title>MCP E2E</title></head>
<body><h1 id="headline">hello from the fixture</h1>
<p><a id="nav-link" href="/two.html">go to page two</a></p>
<select id="size">
<option>Choose</option><option>UK 8</option><option>UK 10</option>
<option>UK 12</option>
</select>
<div style="height: 3000px">spacer</div>
<p id="bottom">bottom marker</p>
</body></html>
"""

TWO_HTML = """<!DOCTYPE html>
<html><head><title>MCP E2E two</title></head>
<body><h1>second page reached</h1></body></html>
"""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class _Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        body = TWO_HTML if 'two' in self.path else INDEX_HTML
        payload = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def website():
    """A tiny local HTTP site on 127.0.0.1."""
    port = _free_port()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port),
                                             _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{port}'
    server.shutdown()


@pytest.fixture
def browser(tmp_path, website):
    """A running qutebrowser with the MCP server enabled."""
    assert website
    port = _free_port()
    basedir = tmp_path / 'basedir'
    basedir.mkdir()
    env = dict(os.environ)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    args = [
        sys.executable, '-m', 'qutebrowser', '--no-err-windows',
        '--basedir', str(basedir),
        '-s', 'mcp.enabled', 'true',
        '-s', 'mcp.port', str(port),
        '-s', 'qt.force_software_rendering', 'chromium',
        '-s', 'mcp.allow_origins', json.dumps([website]),
        'about:blank',
    ]
    proc = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    token_path = basedir / 'config' / 'mcp-token'

    deadline = time.monotonic() + TOKEN_WAIT_S
    token = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(
                f'qutebrowser exited early (code {proc.returncode})')
        try:
            token = token_path.read_text(encoding='utf-8').strip()
            if token:
                break
        except OSError:
            pass
        time.sleep(0.5)
    if not token:
        proc.terminate()
        raise AssertionError('MCP token file never appeared')

    try:
        yield {'url': f'http://127.0.0.1:{port}/mcp', 'token': token,
               'website': website}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def _text(result) -> str:
    for item in result.content or []:
        text = getattr(item, 'text', None)
        if text:
            return text
    return ''


def _items(result) -> list:
    """All JSON payloads of a CallToolResult (one per content item)."""
    out = []
    for item in result.content or []:
        text = getattr(item, 'text', None)
        if text:
            out.append(json.loads(text))
    return out


async def _drive(browser) -> None:
    headers = {'Authorization': f'Bearer {browser["token"]}'}
    timeout = httpx2.Timeout(60.0, read=300.0)
    index_url = browser['website'] + '/index.html'

    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as client:
        async with streamable_http_client(
                browser['url'],
                http_client=client) as (read_stream, write_stream):
            session = ClientSession(read_stream, write_stream)
            async with session:
                await session.initialize()
                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                assert 'read_page' in names
                assert 'scroll' in names and 'select_option' in names
                assert len(names) >= 17

                tabs = _items(await session.call_tool('tabs_list', {}))
                assert any('about:blank' in t['url'] or t['url'] == ''
                           for t in tabs)

                result = await session.call_tool(
                    'navigate', {'url': index_url})
                assert not result.is_error, _text(result)

                result = await session.call_tool('wait_for', {
                    'condition': 'text:hello from the fixture',
                    'timeout_ms': 30000})
                payload = json.loads(_text(result))
                assert payload['satisfied'], _text(result)

                state = json.loads(_text(await session.call_tool(
                    'page_state', {})))
                assert state['ready_state'] == 'complete'
                assert '127.0.0.1' in state['url']

                page = json.loads(_text(await session.call_tool(
                    'read_page', {'max_chars': 2000})))
                assert 'hello from the fixture' in page['text']
                assert page['note'].startswith('[UNTRUSTED PAGE CONTENT')

                scrolled = json.loads(_text(await session.call_tool(
                    'scroll', {'direction': 'down', 'amount': 1.0})))
                assert scrolled['scrollY'] > 0, scrolled

                chosen = json.loads(_text(await session.call_tool(
                    'select_option', {'ref': '#size', 'value': 'UK 10'})))
                assert chosen.get('ok') and chosen['chosen'] == 'UK 10', \
                    chosen

                marks = json.loads(_text(await session.call_tool(
                    'bookmarks_list', {})))
                assert isinstance(marks['bookmarks'], list)
                assert isinstance(marks['quickmarks'], list)

                hist = json.loads(_text(await session.call_tool(
                    'history_search', {'query': 'fixture'})))
                assert isinstance(hist['results'], list)

                found = json.loads(_text(await session.call_tool(
                    'find_elements', {'query': 'page two'})))
                link = [e for e in found['elements']
                        if e['text'] and 'page two' in e['text']]
                assert link, _text(await session.call_tool(
                    'find_elements', {'query': 'page two'}))

                result = await session.call_tool(
                    'click', {'ref': str(link[0]['ref'])})
                assert not result.is_error, _text(result)

                result = await session.call_tool('wait_for', {
                    'condition': 'text:second page reached',
                    'timeout_ms': 30000})
                assert json.loads(_text(result))['satisfied']

                shot = json.loads(_text(await session.call_tool(
                    'screenshot', {})))
                assert pathlib.Path(shot['path']).exists()

                pdf = json.loads(_text(await session.call_tool(
                    'save_pdf', {})))
                pdf_path = pathlib.Path(pdf['path'])
                assert pdf_path.exists() and pdf_path.stat().st_size > 500


def test_mcp_end_to_end(browser):
    asyncio.run(_drive(browser))
