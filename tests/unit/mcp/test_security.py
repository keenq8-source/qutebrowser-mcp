# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.mcp.security."""

import pytest

from qutebrowser.mcp import audit, security


@pytest.fixture(autouse=True)
def _tmp_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, '_log_path', lambda: tmp_path / 'audit.jsonl')
    security.revoke_session()
    yield
    security.revoke_session()


@pytest.mark.parametrize('url, expected', [
    ('https://Example.COM/path?q=1', 'https://example.com'),
    ('https://example.com:443/x', 'https://example.com'),
    ('http://example.com:80/', 'http://example.com'),
    ('http://example.com:8080/x', 'http://example.com:8080'),
    ('https://sub.example.com/', 'https://sub.example.com'),
    ('file:///tmp/x', None),
    ('about:blank', None),
    ('javascript:alert(1)', None),
    ('not a url', None),
])
def test_origin_of(url, expected):
    assert security.origin_of(url) == expected


def test_matches_config(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns',
                        lambda: ['https://example.com'])
    assert security.matches_config('https://example.com')
    assert not security.matches_config('https://other.example')


def test_matches_config_invalid_pattern_ignored(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns',
                        lambda: ['not a valid pattern!!!', 'https://ok.example'])
    assert security.matches_config('https://ok.example')


def test_request_access_grants_and_caches(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns', lambda: [])
    monkeypatch.setattr(security, '_ask_remember', lambda origin: False)
    asked = []

    def fake_ask(origin):
        asked.append(origin)
        return True

    monkeypatch.setattr(security, '_ask_user', fake_ask)
    assert security.request_access('https://example.com')
    assert security.request_access('https://example.com')  # cached
    assert asked == ['https://example.com']
    assert security.session_allowed() == ['https://example.com']


def test_request_access_denied(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns', lambda: [])
    monkeypatch.setattr(security, '_ask_user', lambda origin: False)
    assert not security.request_access('https://denied.example')
    assert security.session_allowed() == []


def test_request_access_skips_prompt_when_config_matches(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns',
                        lambda: ['https://example.com'])

    def no_prompt(origin):
        raise AssertionError('should not prompt')

    monkeypatch.setattr(security, '_ask_user', no_prompt)
    assert security.request_access('https://example.com')

def test_request_access_remember_persists(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns', lambda: [])
    monkeypatch.setattr(security, '_ask_user', lambda origin: True)
    monkeypatch.setattr(security, '_ask_remember', lambda origin: True)
    saved = []

    class FakeInstance:

        def set_obj(self, name, value, save_yaml=False):
            saved.append((name, value, save_yaml))

    class FakeConfig:
        instance = FakeInstance()

    monkeypatch.setattr(security, 'config', FakeConfig)
    assert security.request_access('https://persist.example')
    assert saved == [('mcp.allow_origins', ['https://persist.example'],
                      True)]


def test_request_access_session_only(monkeypatch):
    monkeypatch.setattr(security, '_config_patterns', lambda: [])
    monkeypatch.setattr(security, '_ask_user', lambda origin: True)
    monkeypatch.setattr(security, '_ask_remember', lambda origin: False)

    def no_persist(origin):
        raise AssertionError('should not persist')

    monkeypatch.setattr(security, '_persist_origin', no_persist)
    assert security.request_access('https://session.example')
    assert security.session_allowed() == ['https://session.example']
