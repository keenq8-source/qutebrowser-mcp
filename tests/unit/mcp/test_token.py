# SPDX-FileCopyrightText: qutebrowser-mcp contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.mcp.token."""

import pytest

from qutebrowser.mcp import token as token_module


@pytest.fixture(autouse=True)
def _tmp_standarddir(monkeypatch, tmp_path):
    monkeypatch.setattr(token_module.standarddir, 'config',
                        lambda: str(tmp_path))


def test_creates_and_persists(tmp_path):
    t1 = token_module.get_token()
    assert t1
    assert (tmp_path / token_module.FILENAME).exists()
    assert token_module.get_token() == t1


def test_rotate_changes_token():
    t1 = token_module.get_token()
    t2 = token_module.rotate_token()
    assert t2 and t2 != t1
    assert token_module.get_token() == t2


def test_empty_file_is_replaced(tmp_path):
    path = tmp_path / token_module.FILENAME
    path.write_text('   \n', encoding='utf-8')
    t = token_module.get_token()
    assert t.strip()
    assert path.read_text(encoding='utf-8').strip() == t
