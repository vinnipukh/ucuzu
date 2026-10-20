from __future__ import annotations

import os
import subprocess
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


class FakeProcess:
    """Stands in for ``subprocess.Popen``; ``wait`` replays the given results in order."""

    def __init__(self, *results: int | BaseException) -> None:
        self.results = list(results)
        self.timeouts: list[float | None] = []

    def wait(self, timeout: float | None = None) -> int:
        self.timeouts.append(timeout)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def patch_windows(monkeypatch: pytest.MonkeyPatch, proc: FakeProcess) -> list[str]:
    """Pretend to be on Windows; returns the order of job setup and process start."""
    calls: list[str] = []
    monkeypatch.setattr(run_falcon_server.os, "name", "nt")
    monkeypatch.setattr(run_falcon_server, "kill_children_on_exit", lambda: calls.append("job"))
    monkeypatch.setattr(run_falcon_server.subprocess, "Popen", lambda cmd: calls.append("popen") or proc)
    monkeypatch.setattr(run_falcon_server.os, "execvp", lambda *a: pytest.fail("execvp used on Windows"))
    return calls


def test_run_server_execs_on_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    execs: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(run_falcon_server.os, "name", "posix")
    monkeypatch.setattr(run_falcon_server.os, "execvp", lambda f, args: execs.append((f, args)))
    monkeypatch.setattr(run_falcon_server.subprocess, "Popen", lambda cmd: pytest.fail("Popen used on POSIX"))
    run_falcon_server.run_server(["server", "--port", "8000"])
    assert execs == [("server", ["server", "--port", "8000"])]


def test_run_server_reports_exec_failure_on_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object) -> None:
        raise OSError("not found")

    monkeypatch.setattr(run_falcon_server.os, "name", "posix")
    monkeypatch.setattr(run_falcon_server.os, "execvp", fail)
    assert run_falcon_server.run_server(["server"]) == 1


def test_run_server_waits_for_child_in_job_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProcess(3)
    calls = patch_windows(monkeypatch, proc)
    assert run_falcon_server.run_server(["server"]) == 3
    assert calls == ["job", "popen"]  # the job must exist before the server starts


def test_run_server_waits_for_shutdown_after_ctrl_c_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProcess(KeyboardInterrupt(), 0)
    patch_windows(monkeypatch, proc)
    assert run_falcon_server.run_server(["server"]) == 0
    assert proc.timeouts == [None, 10]


def test_run_server_gives_up_on_hung_shutdown_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = FakeProcess(KeyboardInterrupt(), subprocess.TimeoutExpired("server", 10))
    patch_windows(monkeypatch, proc)
    assert run_falcon_server.run_server(["server"]) == 130


@pytest.mark.skipif(os.name != "nt", reason="Windows job objects")
def test_killing_launcher_kills_its_grandchildren_on_windows() -> None:
    import ctypes

    launcher = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess, sys, time\n"
            "import run_falcon_server\n"
            "run_falcon_server.kill_children_on_exit()\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(60)\n",
        ],
        cwd=SCRIPTS_DIR,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        child_pid = int(launcher.stdout.readline())
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        synchronize = 0x00100000
        handle = kernel32.OpenProcess(synchronize, False, child_pid)
        assert handle, "child process not found"
        try:
            launcher.kill()  # TerminateProcess: no cleanup code runs in the launcher
            launcher.wait(timeout=10)
            assert kernel32.WaitForSingleObject(handle, 10_000) == 0, "child outlived the launcher"
        finally:
            kernel32.CloseHandle(handle)
    finally:
        launcher.kill()
        launcher.stdout.close()
