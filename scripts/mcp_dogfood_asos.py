# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""ASOS dogfood: drive the qutebrowser MCP server like an agent would.

Scenario (same as the earlier manual Edge run): find the "House of Sunny
faux fur longline coat in brown" on ASOS, open the product page, and
extract price / colour / sizes.

Usage:
    python scripts/mcp_dogfood_asos.py <mcp-url> <token>
"""

import re
import sys
import json
import asyncio

import httpx2

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SEARCH_URL = 'https://www.asos.com/search/?q=house+of+sunny+faux+fur'


def _text(result) -> str:
    for item in result.content or []:
        text = getattr(item, 'text', None)
        if text:
            return text
    return ''


async def _call(session, tool, args, note):
    result = await session.call_tool(tool, args)
    payload = _text(result)
    print(f'\n===== {note} [{tool}] is_error={result.is_error} =====')
    print(payload[:800])
    return result, payload


async def run(url: str, token: str) -> int:
    headers = {'Authorization': f'Bearer {token}'}
    timeout = httpx2.Timeout(60.0, read=300.0)
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as client:
        async with streamable_http_client(
                url, http_client=client) as (read_stream, write_stream):
            session = ClientSession(read_stream, write_stream)
            async with session:
                await session.initialize()

                await _call(session, 'tab_open',
                            {'url': SEARCH_URL, 'background': False},
                            '1) open ASOS search')

                await _call(session, 'wait_for',
                            {'condition': 'text:House of Sunny',
                             'timeout_ms': 60000},
                            '2) wait for results')

                _, payload = await _call(session, 'read_page',
                                         {'max_chars': 6000},
                                         '3) read results page')
                try:
                    page = json.loads(payload)
                except ValueError:
                    page = {'text': '', 'url': ''}
                print('SEARCH URL:', page.get('url'))
                hits = [line for line in page.get('text', '').splitlines()
                        if 'house of sunny' in line.lower()
                        and ('coat' in line.lower() or 'fur' in line.lower())]
                print('RESULT-LINES:', hits[:5])

                _, found = await _call(session, 'find_elements',
                                       {'query': 'faux fur longline coat'},
                                       '4) find the coat tile')
                try:
                    elements = json.loads(found).get('elements', [])
                except ValueError:
                    elements = []
                tile = next((e for e in elements
                             if e.get('text')
                             and 'longline coat' in e['text'].lower()), None)
                print('TILE:', tile)

                if tile is not None:
                    await _call(session, 'click', {'ref': str(tile['ref'])},
                                '5) click the tile')
                    # Wait for hydrated content (size <select> + colour),
                    # not just the title — it renders before the rest.
                    await _call(session, 'wait_for',
                                {'condition': 'selector:select',
                                 'timeout_ms': 60000},
                                '6a) wait for size select')
                    await _call(session, 'wait_for',
                                {'condition': 'text:dark brown',
                                 'timeout_ms': 30000},
                                '6b) wait for colour text')
                    _, pdp = await _call(session, 'read_page',
                                         {'max_chars': 8000},
                                         '7) read product page')
                    try:
                        pdp_page = json.loads(pdp)
                    except ValueError:
                        pdp_page = {'text': '', 'url': ''}
                    print('PDP URL:', pdp_page.get('url'))
                    pdp_text = pdp_page.get('text', '')
                    print('TEXT TAIL:', pdp_text[-600:].replace('\n', ' | '))
                    for label, pat in [
                            ('PRICES', r'£[\d,.]+'),
                            ('SIZES', r'\b(?:UK|EU)\s?\d+\b'),
                            ('COLOUR', r'(?i)dark brown'),
                    ]:
                        print(f'{label}:',
                              re.findall(pat, pdp_text)[:14])
                    await _call(session, 'screenshot', {}, '8) screenshot')

                await _call(session, 'tabs_list', {}, '9) tabs')
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    return asyncio.run(run(sys.argv[1], sys.argv[2]))


if __name__ == '__main__':
    sys.exit(main())
