# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the mcpbridge component."""

import logging
from types import SimpleNamespace

import pytest

from qutebrowser.components import mcpbridge
from qutebrowser.mcp import bridge


class FakeConfig:

    """Minimal config double (val.mcp.*, instance.set_obj)."""

    def __init__(self, enabled=False, port=8765):
        self.val = SimpleNamespace(
            mcp=SimpleNamespace(enabled=enabled, port=port))
        self.saved = []
        self.instance = SimpleNamespace(set_obj=self._set_obj)

    def _set_obj(self, name, value, **kwargs):
        self.saved.append((name, value))
        if name == 'mcp.enabled':
            self.val.mcp.enabled = value


class FakeServerModule:

    """Records start/stop calls."""

    def __init__(self):
        self.started = []
        self.stop_calls = 0
        self._running = False

    def start(self, port):
        self.started.append(port)
        self._running = True
        return {'running': True, 'port': port,
                'url': f'http://127.0.0.1:{port}/mcp'}

    def stop(self):
        self.stop_calls += 1
        self._running = False
        return {'running': False}

    def status(self):
        return {'running': self._running,
                'url': f'http://127.0.0.1:8765/mcp'}


@pytest.fixture
def fakes(monkeypatch):
    fk = FakeServerModule()
    monkeypatch.setattr(mcpbridge, '_server', lambda: fk)
    return fk


@pytest.fixture(autouse=True)
def _reset_bridge():
    yield
    bridge.shutdown_invoker()


def test_init_starts_when_enabled(qtbot, fakes, monkeypatch):
    monkeypatch.setattr(mcpbridge, 'config', FakeConfig(enabled=True,
                                                        port=9123))
    messages = []
    monkeypatch.setattr(mcpbridge, 'message',
                        SimpleNamespace(info=messages.append,
                                        error=messages.append))
    mcpbridge.init(None)
    assert fakes.started == [9123]


def test_init_does_nothing_when_disabled(qtbot, fakes, monkeypatch):
    monkeypatch.setattr(mcpbridge, 'config', FakeConfig(enabled=False))
    mcpbridge.init(None)
    assert fakes.started == []


def test_init_survives_start_failure(qtbot, fakes, monkeypatch, caplog):
    monkeypatch.setattr(mcpbridge, 'config', FakeConfig(enabled=True))
    errors = []
    monkeypatch.setattr(mcpbridge, 'message',
                        SimpleNamespace(info=lambda m: None,
                                        error=errors.append))

    def boom(port):
        raise RuntimeError('port in use')

    monkeypatch.setattr(fakes, 'start', boom)
    with caplog.at_level(logging.ERROR, logger='mcp'):  # expected log
        mcpbridge.init(None)  # must not raise
    assert errors and 'port in use' in errors[0]


def test_enabled_changed_stops(qtbot, fakes, monkeypatch):
    monkeypatch.setattr(mcpbridge, 'config', FakeConfig(enabled=False))
    mcpbridge.on_enabled_changed()
    assert fakes.stop_calls == 1


def test_start_command_enables_and_starts(qtbot, fakes, monkeypatch):
    fake_config = FakeConfig(enabled=False, port=9001)
    monkeypatch.setattr(mcpbridge, 'config', fake_config)
    messages = []
    monkeypatch.setattr(mcpbridge, 'message',
                        SimpleNamespace(info=messages.append,
                                        error=messages.append))
    mcpbridge.mcp_start()
    assert fake_config.saved == [('mcp.enabled', True)]
    assert fakes.started == [9001]
    assert any('listening' in m for m in messages)
