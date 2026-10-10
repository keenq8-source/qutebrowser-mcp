"""Repro: call save_pdf on a live instance; print result + audit tail.

Usage: python scripts/repro_save_pdf.py <mcp-url> <token> <basedir>
"""

import asyncio
import pathlib
import sys

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    url, token, basedir = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    headers = {'Authorization': f'Bearer {token}'}
    timeout = httpx2.Timeout(60.0, read=300.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as client:
        async with streamable_http_client(url, http_client=client) as (r, w):
            session = ClientSession(r, w)
            async with session:
                await session.initialize()
                res = await session.call_tool(
                    'navigate',
                    {'url': 'https://www.asos.com/search/'
                            '?q=house+of+sunny+faux+fur'})
                print('navigate isError:', res.is_error)
                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                print('tool_count:', len(names),
                      'has_save_pdf:', 'save_pdf' in names)
                res = await session.call_tool(
                    'wait_for', {'condition': 'text:faux',
                                 'timeout_ms': 20000})
                print('wait:', (res.content[0].text or '')[:110])
                res = await session.call_tool('save_pdf', {})
                print('save_pdf isError:', res.is_error)
                for item in (res.content or []):
                    print('payload:', (getattr(item, 'text', None)
                                       or '')[:300])
                res = await session.call_tool('screenshot', {})
                print('screenshot isError:', res.is_error)
    audit = basedir / 'data' / 'mcp' / 'audit.jsonl'
    print('--- audit tail ---')
    if audit.exists():
        for line in audit.read_text(encoding='utf-8').splitlines()[-6:]:
            print(line[:320])


asyncio.run(main())
