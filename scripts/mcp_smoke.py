# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""End-to-end smoke client for the qutebrowser MCP server.

Usage:
    python scripts/mcp_smoke.py <url> <token>

Exercises: handshake, tools/list, tabs_list, navigate, wait_for, read_page.
"""

import sys
import asyncio

import httpx2

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _text(result) -> str:
    """First text chunk of a CallToolResult (or its string form)."""
    try:
        for item in result.content:
            text = getattr(item, 'text', None)
            if text:
                return text
    except (AttributeError, TypeError):
        pass
    return repr(result)


def _is_error(result) -> bool:
    if hasattr(result, 'isError'):
        return bool(result.isError)
    return bool(getattr(result, 'is_error', False))


async def run(url: str, token: str) -> int:
    headers = {'Authorization': f'Bearer {token}'}
    timeout = httpx2.Timeout(60.0, read=300.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as client:
        async with streamable_http_client(
                url, http_client=client) as (read_stream, write_stream):
            session = ClientSession(read_stream, write_stream)
            async with session:
                await session.initialize()
                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                print(f'TOOLS ({len(names)}): {", ".join(names)}')

                result = await session.call_tool('tabs_list', {})
                print('tabs_list isError:', _is_error(result))
                print('  ', _text(result)[:300])

                result = await session.call_tool(
                    'navigate', {'url': 'https://example.com'})
                print('navigate isError:', _is_error(result))
                print('  ', _text(result)[:200])

                result = await session.call_tool('page_state', {})
                print('page_state:', _text(result)[:300].replace('\n', ' '))

                result = await session.call_tool(
                    'wait_for', {'condition': 'load', 'timeout_ms': 15000})
                print('wait_for:', _text(result)[:200])

                result = await session.call_tool(
                    'read_page', {'max_chars': 600})
                print('read_page isError:', _is_error(result))
                print('  ', _text(result)[:500].replace('\n', ' | '))
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    return asyncio.run(run(sys.argv[1], sys.argv[2]))


if __name__ == '__main__':
    sys.exit(main())
