# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Thread bridge between the MCP server thread and the Qt main thread.

The MCP server runs in its own thread (and asyncio loop). Every browser
operation must execute on the Qt main thread; this module provides the
marshalling:

    result = bridge.call(lambda: some_qt_operation())

The callable runs on the Qt main thread via a queued signal/slot
connection; the calling thread blocks on a ``concurrent.futures.Future``
until the result (or exception) is available. Calls made *from* the Qt
main thread execute directly.

Tools taking async JavaScript results are expected to spin a nested QEventLoop
inside their own callable (see ``qutebrowser.mcp.ops``), so ``call()`` itself
stays simple and synchronous.
"""

import logging
import threading
import concurrent.futures
import dataclasses
from typing import Any, Callable, TypeVar

from qutebrowser.qt.core import QObject, QCoreApplication, QThread, pyqtSignal, Qt

logger = logging.getLogger('mcp')

T = TypeVar('T')

DEFAULT_TIMEOUT = 30.0


class BridgeError(Exception):
    """Base class for bridge errors."""


class BridgeUnavailableError(BridgeError):
    """Raised when the bridge has not been initialized yet."""


class BridgeTimeoutError(BridgeError):
    """Raised when a Qt-thread call did not finish in time."""


@dataclasses.dataclass
class _Job:

    """A callable to run on the Qt main thread."""

    fn: Callable[[], Any]
    future: 'concurrent.futures.Future'


class QtInvoker(QObject):

    """Runs callables on the Qt main thread from other threads.

    Must be created on the Qt main thread.
    """

    _job_requested = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._job_requested.connect(
            self._run_job, Qt.ConnectionType.QueuedConnection)

    def _run_job(self, job: _Job) -> None:
        """Execute a job on the Qt thread (slot, queued connection)."""
        if job.future.done():
            return
        try:
            result = job.fn()
        except BaseException as e:  # noqa: BLE001
            # Propagate *any* failure to the calling thread.
            try:
                job.future.set_exception(e)
            except concurrent.futures.InvalidStateError:
                pass
        else:
            try:
                job.future.set_result(result)
            except concurrent.futures.InvalidStateError:
                pass

    def call(self, fn: Callable[[], T], timeout: float | None = DEFAULT_TIMEOUT) -> T:
        """Run ``fn`` on the Qt thread and return its result.

        Args:
            fn: The callable to execute on the Qt main thread.
            timeout: Seconds to wait; None waits forever.

        Raises:
            BridgeTimeoutError: if the call did not finish in time.
            Exception: whatever ``fn`` raised, re-raised here.
        """
        if on_qt_thread():
            return fn()
        future: 'concurrent.futures.Future[T]' = concurrent.futures.Future()
        self._job_requested.emit(_Job(fn=fn, future=future))
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise BridgeTimeoutError(
                f'Qt-thread call timed out after {timeout}s') from None


_invoker: QtInvoker | None = None
_init_lock = threading.Lock()


def init_invoker() -> QtInvoker:
    """Create the module-level invoker (must run on the Qt main thread)."""
    global _invoker  # pylint: disable=global-statement
    with _init_lock:
        if _invoker is None:
            _invoker = QtInvoker()
            logger.debug('MCP bridge invoker created')
        return _invoker


def shutdown_invoker() -> None:
    """Drop the invoker (used on shutdown/tests)."""
    global _invoker  # pylint: disable=global-statement
    with _init_lock:
        _invoker = None


def on_qt_thread() -> bool:
    """Whether the current thread is the Qt main thread."""
    app = QCoreApplication.instance()
    if app is None:
        return True  # no QApplication (unit tests without Qt) -> direct exec
    return QThread.isMainThread()


def call(fn: Callable[[], T], timeout: float | None = DEFAULT_TIMEOUT) -> T:
    """Run ``fn`` on the Qt main thread, from wherever we are.

    On the Qt thread this is a direct call. From any other thread it is
    marshalled via the invoker created by :func:`init_invoker`.
    """
    if on_qt_thread():
        return fn()
    invoker = _invoker
    if invoker is None:
        raise BridgeUnavailableError(
            'MCP bridge is not initialized yet '
            '(was the mcpbridge component loaded?)')
    return invoker.call(fn, timeout=timeout)
