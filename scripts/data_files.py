#!/usr/bin/env python3
"""Keep committed data files under the repository size limit.

Git hosts reject large blobs, so any file under ``data/`` larger than
``LIMIT_MB`` is committed as numbered ``<name>.partNNN`` chunks while the
original stays local and is listed in the managed block of ``.gitignore``.

    uv run python scripts/data_files.py check   # fail if an unsplit file > limit would be committed
    uv run python scripts/data_files.py split   # split oversized files, update .gitignore
    uv run python scripts/data_files.py join    # rebuild originals from their parts (run by build_database.py)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
GITIGNORE = REPO_ROOT / ".gitignore"
LIMIT_MB = 85
CHUNK_MB = 80
PART_PATTERN = re.compile(r"^(?P<original>.+)\.part(?P<index>\d{3})$")
BLOCK_START = "# >>> split data files (managed by scripts/data_files.py; originals rebuilt by `join`)"
BLOCK_END = "# <<< split data files"


def _oversized(data_dir: Path) -> list[Path]:
    limit = LIMIT_MB * 1024 * 1024
    return sorted(
        path
        for path in data_dir.rglob("*")
        if path.is_file() and not PART_PATTERN.match(path.name) and path.stat().st_size > limit
    )


def _part_groups(data_dir: Path) -> dict[Path, list[Path]]:
    groups: dict[Path, list[Path]] = {}
    for part in data_dir.rglob("*.part[0-9][0-9][0-9]"):
        match = PART_PATTERN.match(part.name)
        if match:
            groups.setdefault(part.with_name(match["original"]), []).append(part)
    return {original: sorted(parts) for original, parts in sorted(groups.items())}


def _ignored_originals() -> list[str]:
    if not GITIGNORE.exists():
        return []
    lines = GITIGNORE.read_text(encoding="utf-8").splitlines()
    if BLOCK_START not in lines:
        return []
    start = lines.index(BLOCK_START) + 1
    end = lines.index(BLOCK_END, start)
    return [line for line in lines[start:end] if line and not line.startswith("#")]


def _write_ignored_originals(entries: list[str]) -> None:
    lines = GITIGNORE.read_text(encoding="utf-8").splitlines() if GITIGNORE.exists() else []
    if BLOCK_START in lines:
        start = lines.index(BLOCK_START)
        end = lines.index(BLOCK_END, start)
        del lines[start : end + 1]
        while lines and not lines[-1]:
            lines.pop()
    lines += ["", BLOCK_START, *sorted(set(entries)), BLOCK_END]
    GITIGNORE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gitignore_entry(path: Path) -> str:
    return "/" + path.relative_to(REPO_ROOT).as_posix()


def split(data_dir: Path) -> int:
    entries = _ignored_originals()
    for original in _oversized(data_dir):
        for stale in original.parent.glob(f"{original.name}.part[0-9][0-9][0-9]"):
            stale.unlink()
        chunk = CHUNK_MB * 1024 * 1024
        with original.open("rb") as handle:
            index = 1
            while block := handle.read(chunk):
                original.with_name(f"{original.name}.part{index:03d}").write_bytes(block)
                index += 1
        entries.append(_gitignore_entry(original))
        print(f"split {original.relative_to(REPO_ROOT)} into {index - 1} parts")
    _write_ignored_originals(entries)
    return 0


def join(data_dir: Path) -> int:
    for original, parts in _part_groups(data_dir).items():
        expected = sum(part.stat().st_size for part in parts)
        if original.exists() and original.stat().st_size == expected:
            continue
        with original.open("wb") as out:
            for part in parts:
                out.write(part.read_bytes())
        print(f"joined {len(parts)} parts into {original.relative_to(REPO_ROOT)}")
    return 0


def _git_ignored(paths: list[Path]) -> set[Path]:
    """Paths Git would not commit; falls back to the managed block when Git is unavailable."""
    if not paths:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--stdin", "-z"],
            cwd=REPO_ROOT,
            input="\0".join(path.relative_to(REPO_ROOT).as_posix() for path in paths).encode("utf-8"),
            capture_output=True,
        )
    except OSError:
        result = None
    if result is None or result.returncode not in (0, 1):
        managed = set(_ignored_originals())
        return {path for path in paths if _gitignore_entry(path) in managed}
    return {(REPO_ROOT / name).resolve() for name in result.stdout.decode("utf-8").split("\0") if name}


def check(data_dir: Path) -> int:
    oversized = _oversized(data_dir)
    ignored = _git_ignored(oversized)
    offenders = [path for path in oversized if path.resolve() not in ignored]
    for path in offenders:
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"too large to commit ({size_mb:.0f} MB > {LIMIT_MB} MB): {path.relative_to(REPO_ROOT)}")
    if offenders:
        print("Run `uv run python scripts/data_files.py split` or add the file to .gitignore.")
        return 1
    print(f"OK: no unsplit data file exceeds {LIMIT_MB} MB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["check", "split", "join"])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    return {"check": check, "split": split, "join": join}[args.command](args.data_dir.resolve())


if __name__ == "__main__":
    sys.exit(main())
