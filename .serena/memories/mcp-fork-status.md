# qutebrowser MCP fork — state & hard-won lessons (2026-10-10)

## What exists now
- Fork at Desktop\\511\\browser-mcp\\qutebrowser (branch mcp-feature, base commit 2bd75916a).
- `qutebrowser/mcp/` package: bridge (Qt-thread marshalling), token, audit (JSONL), security
  (origin consent), ops (Qt-thread browser ops, nested QEventLoop for JS), tools (13 MCP tools),
  server (mcp SDK v2 streamable HTTP + bearer + DNS-rebinding).
- Component `qutebrowser/components/mcpbridge.py` auto-loaded via components walk; config options
  mcp.enabled / mcp.port / mcp.allow_origins (configdata.yml, section before ## messages).
- Tests: tests/unit/mcp (bridge/token/audit/security/tools/server), tests/unit/components/test_mcpbridge.py,
  tests/end2end/test_mcp_e2e.py (spawns offscreen qutebrowser + local webserver + real MCP client).
- Smoke client: scripts/mcp_smoke.py. All 41 tests green.

## Runbook (dev)
- Run: `.venv/Scripts/python.exe -m qutebrowser --basedir <dir> -s mcp.enabled true -s mcp.port 18765 --no-err-windows` (add QT_QPA_PLATFORM=offscreen for headless).
- Token: `<basedir>/config/mcp-token`; audit: `<basedir>/data/mcp/audit.jsonl`.
- Client: official `mcp` SDK v2 — `from mcp.client.streamable_http import streamable_http_client`
  (v2 renamed; returns a TUPLE (read, write)); auth via httpx2 client headers; set httpx timeouts
  generously (default 5s aborts long tool calls mid-flight → "SSE stream ended without a response").

## Gotchas that cost time
- qutebrowser's `tab.load_status` is a METHOD (`tab.load_status()`), not a property.
- `load_status` can stick at 'loading' while the page is fully loaded — use document.readyState
  for 'wait_for load' (qutebrowser status OR readyState=='complete').
- mcp SDK v2: tool results with list returns emit ONE content item PER element; `is_error`
  (snake_case), not isError. FastMCP is gone → `from mcp.server.mcpserver import MCPServer`.
- Test package named `tests/unit/mcp` must NOT have __init__.py: pytest inserts its basedir,
  and a package literally named 'mcp' shadows the SDK on sys.path.
- qutebrowser test harness fails tests on WARNING+ log messages unless `with caplog.at_level(...)`
  declares them expected (helpers/logfail.py).
- pytest-qt teardown turns GC socket warnings into errors → filterwarnings marker in e2e test.
- Windows: uv venv python 3.14 works (PyQt6 6.11 wheels fine); curl -o /dev/null exits 23 here —
  don't chain commands with `&&` after it.
- Consent prompt uses blocking `message.ask` (PromptMode.yesno, default=False) — only works with a
  window present; offscreen/e2e tests pre-allow via mcp.allow_origins config.

## Next (plan: Desktop\\511\\browser-mcp\\Browser-MCP-Plan.md)
- Dogfood: register in Hermes (check `hermes mcp add` HTTP transport support; stdio shim if needed).
- v1.1: persist 'always allow' to mcp.allow_origins from the consent prompt; README.mcp.md.
- v2 track: Firefox privileged system-extension port.