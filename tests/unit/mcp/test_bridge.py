# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.mcp.bridge."""

import threading

import pytest

from qutebrowser.mcp import bridge


@pytest.fixture(autouse=True)
def _reset_invoker():
    yield
    bridge.shutdown_invoker()


def run_offthread(qtbot, fn):
    """Run ``fn`` in a worker thread; spin the Qt loop until it returns."""
    out = {}

    def worker():
        try:
            out['res'] = fn()
        except BaseException as e:  # noqa: BLE001
            out['exc'] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    qtbot.waitUntil(lambda: 'res' in out or 'exc' in out, timeout=15000)
    if 'exc' in out:
        raise out['exc']
    return out['res']


def test_direct_call_on_qt_thread(qtbot):
    bridge.init_invoker()
    assert bridge.call(lambda: 40 + 2) == 42


def test_call_from_worker_thread_runs_on_main(qtbot):
    bridge.init_invoker()
    name = run_offthread(
        qtbot, lambda: bridge.call(lambda: threading.current_thread().name))
    assert name == 'MainThread'


def test_exception_propagates_to_caller(qtbot):
    bridge.init_invoker()

    def boom():
        raise ValueError('nope')

    with pytest.raises(ValueError, match='nope'):
        run_offthread(qtbot, lambda: bridge.call(boom))


def test_timeout_raises(qtbot):
    bridge.init_invoker()

    def slow():
        import time
        time.sleep(2)

    with pytest.raises(bridge.BridgeTimeoutError):
        run_offthread(
            qtbot, lambda: bridge.call(slow, timeout=0.05))


def test_uninitialized_offthread_raises(qtbot):
    bridge.shutdown_invoker()
    with pytest.raises(bridge.BridgeUnavailableError):
        run_offthread(qtbot, lambda: bridge.call(lambda: 1))
