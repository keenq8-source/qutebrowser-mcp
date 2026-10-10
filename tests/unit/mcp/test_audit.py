# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.mcp.audit."""

import json

import pytest

from qutebrowser.mcp import audit


@pytest.fixture(autouse=True)
def _tmp_log(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, '_log_path', lambda: tmp_path / 'audit.jsonl')


def _read():
    path = audit._log_path()
    return [json.loads(line) for line in
            path.read_text(encoding='utf-8').splitlines()]


def test_log_basic_fields():
    audit.log_event('fill', summary='fill #2 (value redacted)',
                    decision='ok')
    entries = _read()
    assert len(entries) == 1
    e = entries[0]
    assert e['tool'] == 'fill'
    assert e['decision'] == 'ok'
    assert 'redacted' in e['summary']
    assert 'ts' in e


def test_log_failure_and_high_risk():
    audit.log_event('press_keys', ok=False, error='boom', high_risk=True)
    e = _read()[0]
    assert e['ok'] is False
    assert e['error'] == 'boom'
    assert e['high_risk'] is True


def test_extra_fields_merge():
    audit.log_event('consent', origin='https://example.com',
                    decision='allow-session')
    e = _read()[0]
    assert e['origin'] == 'https://example.com'
