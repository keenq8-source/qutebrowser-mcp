# qutebrowser + native MCP server (fork: `mcp-feature`)

This fork adds a **native, in-process MCP (Model Context Protocol) server** to qutebrowser,
turning the browser into a first-class tool for AI agents: an agent connects over streamable
HTTP (localhost), and drives the browser through **typed tool calls** — no pixel scraping, no
external CDP shims, no separate automation browser.

Verified live against ASOS (search → product page → price/colour/size readback → PDF archive),
which bot-walls ordinary automation.

## What you get

18 MCP tools:

| area | tools |
| --- | --- |
| tabs | `tabs_list`, `tab_open`, `tab_close`, `tab_focus` |
| navigation | `navigate`, `page_state`, `wait_for` (`load` / `selector:<css>` / `text:<s>`, case-insensitive) |
| reading | `read_page` (incl. `[select options]` for dropdowns), `find_elements`, `screenshot`, `save_pdf` |
| interaction | `click`, `fill`, `press_keys`, `scroll`, `select_option` |
| browser data | `history_search`, `bookmarks_list` |

Plus user-facing commands: `:mcp-start`, `:mcp-stop`, `:mcp-status`, `:mcp-token`, `:mcp-revoke`,
`:mcp-log [n]`. Config options: `mcp.enabled`, `mcp.port` (default 8765), `mcp.allow_origins`.

## Security model

- Server binds to `127.0.0.1` only, bearer-token auth (token at `<basedir>/config/mcp-token`),
  DNS-rebinding protection.
- **Per-origin consent**: the first tool call that touches a new site origin pops a blocking
  yes/no prompt (default: deny). A "yes" is followed by a second question — “remember
  permanently?” — which persists the origin into `mcp.allow_origins`.
- **Audit log** (JSONL, `<basedir>/data/mcp/audit.jsonl`): every tool call with origin, summary,
  decision, errors; high-risk calls (screenshot, save_pdf, press_keys) are flagged. `:mcp-log`
  shows the most recent entries in the UI.
- Page content returned by `read_page`/`find_elements` is wrapped in an UNTRUSTED-content
  envelope — agents are instructed never to follow instructions found inside pages.

## Run it (dev / headless)

```bash
cd qutebrowser
QT_QPA_PLATFORM=offscreen ./.venv/Scripts/python.exe -m qutebrowser --basedir <DIR> \
  -s mcp.enabled true -s mcp.port 18765 -s "qt.force_software_rendering" "chromium" \
  -s "mcp.allow_origins" '["https://www.asos.com"]' --json-logging --debug about:blank
```

Without a real display the consent prompt cannot be answered — pre-approve origins via
`mcp.allow_origins` (urlmatch patterns) or run a visible instance and answer the prompt.

## Daily driver (real profile)

- `%APPDATA%\qutebrowser\config\autoconfig.yml` — `mcp.enabled: true` makes every launch of the
  real profile start the server (default port 8765).
- Launcher: `Desktop\511\browser-mcp\launch-agent-browser.cmd`; “qutebrowser (Agent)” shortcuts
  are installed on the desktop and Start Menu.

## Client scripts

- `scripts/mcp_smoke.py <url> <token>` — handshake/tabs/navigate/read smoke test.
- `scripts/mcp_dogfood_asos.py <search-url> <token>` — full ASOS hunt replay (search → PDP →
  price/size → screenshot).
- `scripts/repro_save_pdf.py <mcp-url> <token> <basedir>` — save_pdf repro + audit tail.

SDK note: MCP SDK v2 (`mcp>=2.3`) — `from mcp.client.streamable_http import streamable_http_client`
(returns a `(read, write)` tuple); give httpx a generous timeout (>60 s) or long tool calls abort.

## Tests

```bash
./.venv/Scripts/python.exe -m pytest tests/unit/mcp tests/unit/components/test_mcpbridge.py \
  tests/end2end/test_mcp_e2e.py -q
```

- 40 unit tests (bridge/token/audit/security/tools/server/component) + 1 hermetic end-to-end test
  (offscreen qutebrowser + local site + real MCP client) — 47 total with the extended suite.
- The end-to-end test covers navigate/wait/read/find/click/screenshot **and**
  scroll/select_option/save_pdf/bookmarks/history.

## Implementation map

- `qutebrowser/mcp/` — `bridge.py` (Qt-thread marshalling), `token.py`, `audit.py`, `security.py`
  (origins/consent), `ops.py` (browser operations), `tools.py` (MCP tool registration), `server.py`
  (streamable-HTTP server).
- `qutebrowser/components/mcpbridge.py` — component wiring config changes + `:mcp-*` commands.
- `qutebrowser/config/configdata.yml` — `mcp.*` options.

## Backlog (ideas, not promises)

- Firefox track: same tool surface as a privileged extension (v2).
- Downloads tools (`downloads_list`, `download`) — deliberately omitted for now (writes to disk).
- Optional: publish this fork; upstream discussion with the qutebrowser project.


---

## Upstream qutebrowser README

