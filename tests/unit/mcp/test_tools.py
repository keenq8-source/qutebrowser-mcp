# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.mcp.tools (with a fake ops backend)."""

import pytest

from qutebrowser.mcp import audit, bridge, ops as ops_module, tools


class FakeOps:

    """Records calls and returns canned results."""

    def __init__(self):
        self.calls = []

    def tabs_list(self):
        self.calls.append(('tabs_list',))
        return [{'tab_id': '0:0', 'title': 't', 'url': 'https://x.example'}]

    def tab_open(self, url, background=True):
        self.calls.append(('tab_open', url, background))
        return {'tab_id': '0:1', 'url': url}

    def tab_close(self, tab_id):
        self.calls.append(('tab_close', tab_id))
        return {'closed': tab_id}

    def tab_focus(self, tab_id):
        self.calls.append(('tab_focus', tab_id))
        return {'focused': tab_id}

    def navigate(self, url, tab_id=None):
        self.calls.append(('navigate', url, tab_id))
        return {'url': url}

    def read_page(self, tab_id=None, max_chars=8000):
        self.calls.append(('read_page', tab_id, max_chars))
        return {'title': 't', 'url': 'https://x.example', 'text': 'hello',
                'note': ops_module.UNTRUSTED_NOTE}

    def find_elements(self, query=None, tab_id=None):
        self.calls.append(('find_elements', query, tab_id))
        return {'count': 0, 'elements': []}

    def click(self, ref, tab_id=None):
        self.calls.append(('click', ref, tab_id))
        return {'ok': True, 'label': 'x'}

    def fill(self, ref, value, submit=False, tab_id=None):
        self.calls.append(('fill', ref, value, submit, tab_id))
        return {'ok': True}

    def press_keys(self, keys, tab_id=None):
        self.calls.append(('press_keys', keys, tab_id))
        return {'pressed': keys}

    def screenshot(self, tab_id=None):
        self.calls.append(('screenshot', tab_id))
        return {'path': 'C:/tmp/shot.png'}

    def wait_for(self, condition, timeout_ms=10000, tab_id=None):
        self.calls.append(('wait_for', condition, timeout_ms, tab_id))
        return {'satisfied': True}

    def scroll(self, direction, amount=1.0, tab_id=None):
        self.calls.append(('scroll', direction, amount, tab_id))
        return {'scrollY': 0, 'scrollHeight': 100}

    def select_option(self, ref, value, tab_id=None):
        self.calls.append(('select_option', ref, value, tab_id))
        return {'ok': True, 'chosen': value}

    def save_pdf(self, tab_id=None):
        self.calls.append(('save_pdf', tab_id))
        return {'path': 'C:/tmp/page.pdf'}

    def history_search(self, query, limit=20):
        self.calls.append(('history_search', query, limit))
        return {'query': query, 'results': []}

    def bookmarks_list(self, query=None):
        self.calls.append(('bookmarks_list', query))
        return {'bookmarks': [], 'quickmarks': []}


@pytest.fixture
def fake(monkeypatch):
    """Fake ops + inline bridge + captured audit events."""
    ops = FakeOps()
    events = []
    monkeypatch.setattr(ops_module, 'get', lambda: ops)
    monkeypatch.setattr(bridge, 'call', lambda fn, timeout=None: fn())
    monkeypatch.setattr(
        audit, 'log_event',
        lambda tool, **kw: events.append({'tool': tool, **kw}))
    return ops, events


def test_tool_registry_names():
    names = sorted(fn.__name__ for fn in tools.TOOLS)
    assert names == sorted([
        'tabs_list', 'tab_open', 'tab_close', 'tab_focus', 'navigate',
        'page_state', 'read_page', 'find_elements', 'click', 'fill',
        'press_keys', 'screenshot', 'wait_for', 'scroll', 'select_option',
        'save_pdf', 'history_search', 'bookmarks_list',
    ])


def test_tabs_list(fake):
    ops, events = fake
    assert tools.tabs_list()[0]['tab_id'] == '0:0'
    assert ops.calls == [('tabs_list',)]
    assert events[0]['tool'] == 'tabs_list'
    assert events[0]['decision'] == 'ok'


def test_read_page_carries_untrusted_note(fake):
    ops, _ = fake
    res = tools.read_page(tab_id='0:0', max_chars=500)
    assert res['note'] == ops_module.UNTRUSTED_NOTE
    assert ops.calls == [('read_page', '0:0', 500)]


def test_fill_redacts_value_in_audit(fake):
    ops, events = fake
    tools.fill(ref='3', value='super-secret', submit=True)
    assert ops.calls == [('fill', '3', 'super-secret', True, None)]
    summary = events[0]['summary']
    assert 'redacted' in summary
    assert 'super-secret' not in str(events)


def test_high_risk_tools_flagged(fake):
    ops, events = fake
    tools.press_keys('enter')
    tools.screenshot()
    flags = {e['tool']: e['high_risk'] for e in events}
    assert flags['press_keys'] is True
    assert flags['screenshot'] is True

def test_scroll_dispatches(fake):
    ops, events = fake
    tools.scroll('down', 2.0, tab_id='0:0')
    assert ops.calls == [('scroll', 'down', 2.0, '0:0')]
    assert events[0]['tool'] == 'scroll'


def test_select_option_dispatches(fake):
    ops, events = fake
    res = tools.select_option('7', 'UK 10', tab_id='0:0')
    assert ops.calls == [('select_option', '7', 'UK 10', '0:0')]
    assert res == {'ok': True, 'chosen': 'UK 10'}
    assert events[0]['tool'] == 'select_option'


def test_save_pdf_flag_and_dispatch(fake):
    ops, events = fake
    tools.save_pdf()
    assert ops.calls == [('save_pdf', None)]
    assert events[0]['high_risk'] is True


def test_history_and_bookmarks_dispatch(fake):
    ops, events = fake
    tools.history_search('asos', limit=5)
    tools.bookmarks_list('coat')
    assert ops.calls == [('history_search', 'asos', 5),
                         ('bookmarks_list', 'coat')]
    assert [e['tool'] for e in events] == ['history_search',
                                           'bookmarks_list']


def test_errors_are_audited(monkeypatch, fake):
    ops, events = fake

    def busy(url, tab_id=None):
        raise RuntimeError('denied by the user')

    monkeypatch.setattr(ops, 'navigate', busy)
    with pytest.raises(RuntimeError, match='denied'):
        tools.navigate('https://x.example')
    assert events[-1]['ok'] is False
    assert 'denied' in events[-1]['error']
