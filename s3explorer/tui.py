"""
Terminal UI for localstack-s3-explorer.

A minimal interactive browser built with only the standard library.
Uses ANSI escape codes for colour and cursor control.
Falls back to a simple numbered-list interface on non-interactive terminals.
"""

from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from s3explorer.client import BucketInfo, LocalS3Client, ObjectInfo
from s3explorer.explorer import Explorer

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[92m"
_CYAN   = "\033[96m"
_YELLOW = "\033[93m"
_BLUE   = "\033[94m"
_BG_SEL = "\033[44m"
_CLEAR  = "\033[2J\033[H"
_HIDE   = "\033[?25l"
_SHOW   = "\033[?25h"


def _ansi() -> bool:
    return sys.stdout.isatty()


def _render(
    items: List[str],
    selected: int,
    title: str,
    breadcrumb: str,
    status: str = "",
) -> None:
    use = _ansi()
    if use:
        sys.stdout.write(_CLEAR)

    b = _BOLD if use else ""
    r = _RESET if use else ""
    d = _DIM if use else ""
    c = _CYAN if use else ""

    print(f"\n  {b}Localstack S3 Explorer{r}  {d}{breadcrumb}{r}\n")
    print(f"  {b}{title}{r}\n")

    if use:
        print(f"  {d}↑↓ navigate   Enter open   b back   d download   p preview   / search   q quit{r}\n")
    else:
        print(f"  Type number + Enter to select, b=back, d=download, q=quit\n")

    for i, item in enumerate(items):
        is_sel = i == selected
        if use:
            prefix = f"  {_BG_SEL} {_RESET} " if is_sel else "    "
            text   = f"{_BOLD}{item}{_RESET}" if is_sel else item
        else:
            prefix = f"  [{i+1}] "
            text   = item
        print(f"{prefix}{text}")

    if status:
        print(f"\n  {_YELLOW if use else ''}{status}{_RESET if use else ''}")
    print()
    sys.stdout.flush()


def _read_key() -> str:
    """Read a single keypress (ANSI mode)."""
    import tty
    import termios
    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return {"A": "UP", "B": "DOWN"}.get(ch3, "")
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def run_tui(client: LocalS3Client, output_dir: str = ".") -> None:
    """Launch the interactive TUI browser.

    Parameters
    ----------
    client:
        A :class:`~s3explorer.client.LocalS3Client` instance.
    output_dir:
        Default directory for downloads.
    """
    explorer = Explorer(client)
    use      = _ansi()

    # Navigation state
    bucket:   Optional[str] = None
    prefix:   str           = ""
    selected: int           = 0
    status:   str           = ""

    if use:
        sys.stdout.write(_HIDE)

    try:
        while True:
            # Build item list for current view
            if bucket is None:
                # Bucket list view
                buckets = explorer.list_buckets()
                items   = [f"🪣  {b.name}" for b in buckets]
                title   = "Buckets"
                crumb   = "/"
            else:
                # Object browser view
                folders, objects = explorer.list_path(bucket, prefix)
                folder_items = [f"📁  {f.rstrip('/').rsplit('/', 1)[-1]}/" for f in folders]
                object_items = [
                    f"{'📄' if not o.is_folder else '📁'}  {o.name:<40} {o.size_human():>8}"
                    for o in objects
                ]
                items  = folder_items + object_items
                title  = f"s3://{bucket}/{prefix}"
                crumb  = f"/{bucket}/{prefix}"
                # Keep references for actions
                all_folders = folders
                all_objects = objects

            if not items:
                items = ["  (empty)"]

            selected = min(selected, len(items) - 1)

            if use:
                _render(items, selected, title, crumb, status)
                status = ""
                key    = _read_key()
            else:
                _render(items, -1, title, crumb, status)
                status = ""
                try:
                    raw = input("  > ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    break
                if raw == "q":
                    break
                if raw == "b":
                    key = "b"
                elif raw == "d":
                    key = "d"
                elif raw.isdigit():
                    idx = int(raw) - 1
                    if 0 <= idx < len(items):
                        selected = idx
                        key = "\r"
                    else:
                        continue
                else:
                    continue

            # Handle key
            if key in ("q", "\x03"):
                break

            elif key == "UP":
                selected = max(0, selected - 1)

            elif key == "DOWN":
                selected = min(len(items) - 1, selected + 1)

            elif key in ("\r", "\n"):
                if bucket is None:
                    # Enter a bucket
                    if selected < len(explorer.list_buckets()):
                        bucket   = explorer.list_buckets()[selected].name
                        prefix   = ""
                        selected = 0
                else:
                    n_folders = len(all_folders)
                    if selected < n_folders:
                        # Enter a folder
                        prefix   = all_folders[selected]
                        selected = 0
                    else:
                        # Select an object — show info
                        obj = all_objects[selected - n_folders]
                        status = f"{obj.key}  {obj.size_human()}  {obj.last_modified}"

            elif key == "b":
                if bucket is not None:
                    if prefix:
                        # Go up one level
                        parts  = prefix.rstrip("/").rsplit("/", 1)
                        prefix = parts[0] + "/" if len(parts) > 1 else ""
                    else:
                        bucket   = None
                        prefix   = ""
                    selected = 0

            elif key == "d":
                if bucket is not None:
                    n_folders = len(all_folders)
                    if selected >= n_folders:
                        obj  = all_objects[selected - n_folders]
                        path = explorer.download(bucket, obj.key, output_dir=output_dir)
                        status = f"Downloaded: {path}"
                    else:
                        status = "Select a file (not a folder) to download"

            elif key == "p":
                if bucket is not None:
                    n_folders = len(all_folders)
                    if selected >= n_folders:
                        obj     = all_objects[selected - n_folders]
                        preview = explorer.preview(bucket, obj.key)
                        if use:
                            sys.stdout.write(_CLEAR)
                        print(f"\n  Preview: {obj.key}\n")
                        print(preview)
                        print("\n  Press any key to continue...")
                        sys.stdout.flush()
                        if use:
                            _read_key()
                        else:
                            input()

            elif key == "/":
                if use:
                    sys.stdout.write(_SHOW)
                try:
                    query = input("\n  Search: ").strip()
                except (EOFError, KeyboardInterrupt):
                    query = ""
                if use:
                    sys.stdout.write(_HIDE)
                if query and bucket:
                    results = explorer.search(bucket, query, prefix=prefix)
                    if results:
                        status = f"Found {len(results)} result(s) for '{query}'"
                    else:
                        status = f"No results for '{query}'"

    finally:
        if use:
            sys.stdout.write(_SHOW)
        print()
