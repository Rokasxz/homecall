"""Finding files by date or by what's written inside them.  (Owner: Hands)

Both only look inside Desktop, Documents, Downloads and Pictures (basic.ALLOWED_ROOTS),
at most 3 folders deep, and skip hidden folders, Office lock files (~$...) and program folders.
"""
import os
import time
from pathlib import Path

import pc.actions as actions  # for actions.current_session
from pc.actions import basic

MAX_DEPTH = 3
SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", "site-packages", ".git", "$recycle.bin"}
MAX_LIST = 20


def _session():
    return actions.current_session


def _walk_files():
    """Every normal file in the allowed folders (not too deep, no hidden or program folders)."""
    for root in basic.ALLOWED_ROOTS:
        if not root.exists():
            continue
        base_depth = str(root).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in SKIP_DIRS][:50]
            if dirpath.count(os.sep) - base_depth >= MAX_DEPTH:
                dirnames[:] = []
            for f in filenames:
                if f.startswith(("~$", ".")) or f.lower() == "desktop.ini":
                    continue
                yield Path(dirpath) / f


def _ago(seconds: float) -> str:
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    days = int(seconds // 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def find_recent_files(days: int = 7, name: str = "") -> str:
    """List the files changed most recently in Desktop, Documents, Downloads and Pictures, newest first. Use it for "the file I worked on yesterday".

    Args:
        days: How many days back to look, 1 to 365. Default 7.
        name: Optional: only files whose name contains this, e.g. "pdf" or "report". Default: all files.
    """
    try:
        days = int(days)
    except (TypeError, ValueError):
        return "Error: days must be a whole number from 1 to 365."
    if not 1 <= days <= 365:
        return "Error: days must be from 1 to 365."
    wanted = basic._plain(str(name or "").strip())
    if _session():
        _session().status("Looking for recent files")
    now, since = time.time(), time.time() - days * 86400
    found = []
    for p in _walk_files():
        if wanted and wanted not in basic._plain(p.name):
            continue
        try:
            modified = p.stat().st_mtime
        except OSError:
            continue
        if modified >= since:
            found.append((modified, p))
    if not found:
        extra = f" with '{name}' in the name" if wanted else ""
        return f"No files{extra} changed in the last {days} day(s)."
    found.sort(reverse=True)
    lines = [f"{p}  ({_ago(now - m)})" for m, p in found[:MAX_LIST]]
    more = f", showing the newest {MAX_LIST}" if len(found) > MAX_LIST else ""
    return f"{len(found)} file(s) changed in the last {days} day(s){more}, newest first:\n" + "\n".join(lines)


SEARCHABLE = basic.TEXT_TYPES | {".docx", ".pdf", ".pptx", ".xlsx"}
# Text already read, so the next search is instant: path -> (size, modified time, text). Re-read if the file changed.
_TEXT_CACHE: dict[str, tuple[int, float, str]] = {}
MAX_CACHED = 2000


def _text_of(p: Path, size: int, modified: float) -> str:
    key = str(p)
    hit = _TEXT_CACHE.get(key)
    if hit and hit[0] == size and hit[1] == modified:
        return hit[2]
    text = " ".join((basic._extract_text(p, max_chars=200_000, max_pdf_pages=3) or "").split())  # PDFs: first 3 pages
    if len(_TEXT_CACHE) >= MAX_CACHED:
        _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))  # forget the oldest entry
    _TEXT_CACHE[key] = (size, modified, text)
    return text
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_READ = 1000
TIME_LIMIT = 15  # seconds: stop and say so, rather than make the user wait on the phone
SNIPPET = 60


def search_in_files(text: str) -> str:
    """Find documents whose CONTENT contains some words (not the file name): .txt, .md, .csv, .docx, .pdf, .pptx, .xlsx in Desktop, Documents, Downloads and Pictures. Shows a short piece around each match.

    Args:
        text: The words to look for, e.g. "cabin wifi" or "invoice 2024". Not case sensitive; accents don't matter.
    """
    words = basic._plain(" ".join(str(text or "").split()))
    if len(words) < 3:
        return "Error: give me at least 3 letters to look for."
    if _session():
        first_time = " (the first search takes a few seconds)" if not _TEXT_CACHE else ""
        _session().status(f"Searching inside files for '{text}'{first_time}")
    candidates = []
    for p in _walk_files():
        if p.suffix.lower() in SEARCHABLE:
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size <= MAX_FILE_BYTES:
                candidates.append((st.st_mtime, st.st_size, p))
    candidates.sort(reverse=True)  # newest first: the likely ones are read before any time limit
    started, hits, read = time.time(), [], 0
    stopped_early = False
    for modified, size, p in candidates:
        if read >= MAX_FILES_READ or time.time() - started > TIME_LIMIT:
            stopped_early = True
            break
        read += 1
        try:
            flat = _text_of(p, size, modified)
        except Exception:  # noqa: BLE001  (a broken or locked file: skip it)
            continue
        at = basic._plain(flat).find(words)
        if at >= 0:
            start = max(0, at - SNIPPET)
            piece = flat[start:at + len(words) + SNIPPET]
            hits.append(f"{p}\n   ...{piece}...")
            if len(hits) >= MAX_LIST:
                break
    note = f" (stopped after {read} files to keep it quick; there may be more)" if stopped_early else ""
    if not hits:
        return f"No document mentions '{text}' (looked inside {read} files){note}."
    return f"{len(hits)} document(s) mention '{text}'{note}:\n" + "\n".join(hits)


TOOLS = [find_recent_files, search_in_files]
