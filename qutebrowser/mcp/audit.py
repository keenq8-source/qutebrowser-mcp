# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Append-only JSONL audit log of MCP tool calls.

One JSON object per line, written to ``<data>/mcp/audit.jsonl``.
Writes are guarded by a lock and never raise on I/O failure (a broken
log must not break the agent's tool call); failures are logged instead.

Secrets (like typed form values) are redacted by the caller before they
reach this module.
"""

import json
import logging
import pathlib
import threading
from datetime import datetime, timezone
from typing import Any

from qutebrowser.utils import standarddir

logger = logging.getLogger('mcp')

_lock = threading.Lock()


def _log_path() -> pathlib.Path:
    """Path of the audit log file (monkeypatched in tests)."""
    return pathlib.Path(standarddir.data()) / 'mcp' / 'audit.jsonl'


def log_event(tool: str, *,
              origin: str | None = None,
              summary: str | None = None,
              decision: str | None = None,
              ok: bool = True,
              high_risk: bool = False,
              error: str | None = None,
              **extra: Any) -> None:
    """Append one audit entry."""
    entry: dict[str, Any] = {
        'ts': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        'tool': tool,
    }
    if origin is not None:
        entry['origin'] = origin
    if summary is not None:
        entry['summary'] = summary
    if decision is not None:
        entry['decision'] = decision
    if not ok:
        entry['ok'] = False
    if error is not None:
        entry['error'] = error
    if high_risk:
        entry['high_risk'] = True
    if extra:
        entry.update(extra)

    try:
        with _lock:
            path = _log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as e:  # noqa: BLE001 - never break a tool call
        logger.warning(f'Failed to write MCP audit log: {e}')
