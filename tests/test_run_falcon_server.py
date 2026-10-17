from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import run_falcon_server  # noqa: E402


def test_sqlite_db_defaults_to_prices_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICES_DB_PATH", "/x.db")
    args = run_falcon_server.build_parser().parse_args([])
    assert args.sqlite_db == "/x.db"


def test_sqlite_db_flag_overrides_prices_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICES_DB_PATH", "/x.db")
    args = run_falcon_server.build_parser().parse_args(["--sqlite-db", "/y.db"])
    assert args.sqlite_db == "/y.db"


def test_sqlite_db_falls_back_to_repo_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRICES_DB_PATH", raising=False)
    args = run_falcon_server.build_parser().parse_args([])
    assert Path(args.sqlite_db) == run_falcon_server.DEFAULT_SQLITE_DB
