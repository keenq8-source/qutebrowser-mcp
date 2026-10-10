# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Native MCP (Model Context Protocol) server for qutebrowser.

This package is part of the qutebrowser-mcp fork. It exposes the running
browser to AI agents over the Model Context Protocol with typed tools,
per-origin user consent and a JSONL audit log.

Modules:
    bridge:   marshals calls from the server thread onto the Qt main thread.
    token:    bearer-token storage for the local HTTP endpoint.
    audit:    append-only JSONL audit log of agent actions.
    security: per-origin consent policy.
    ops:      Qt-thread browser operations backing the tools.
    tools:    MCP tool definitions (thin wrappers over ops).
    server:   MCP server lifecycle (streamable HTTP on 127.0.0.1).
"""
