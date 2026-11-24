"""
progress_log.py – CMYK変換スクリプト共通の進捗・エラーログ読み書き

コードはファイル名由来のため、短い安全な文字集合に一致するものだけを扱う。
ログファイルとその親ディレクトリはシンボリックリンクを辿らずに開き、
開いたファイル自体が通常ファイルかを確認してから書き込む。
"""

import errno
import os
import re
import stat
from pathlib import Path

SAFE_CODE = re.compile(r"[A-Za-z0-9_]{1,32}")

_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


def is_safe_code(code: str) -> bool:
    return SAFE_CODE.fullmatch(code) is not None


def filter_safe_codes(codes: list) -> list:
    safe = []
    for code in codes:
        if is_safe_code(code):
            safe.append(code)
        else:
            print(f"⚠️ Skipping unsafe code: {code!r}")
    return safe


def _open_log(path: Path, flags: int) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dir_fd = os.open(
            path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | _CLOEXEC
        )
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RuntimeError(
                f"progress log directory must not be a symlink: {path.parent}"
            ) from e
        raise
    try:
        fd = os.open(
            path.name, flags | os.O_NOFOLLOW | _CLOEXEC, 0o644, dir_fd=dir_fd
        )
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise RuntimeError(f"progress log must not be a symlink: {path}") from e
        raise
    finally:
        os.close(dir_fd)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        os.close(fd)
        raise RuntimeError(f"progress log must be a regular, unlinked file: {path}")
    return fd


def reset_progress_log(path: Path):
    fd = _open_log(path, os.O_WRONLY | os.O_CREAT)
    try:
        os.ftruncate(fd, 0)
    finally:
        os.close(fd)


def append_progress_code(path: Path, code: str):
    if not is_safe_code(code):
        raise ValueError(f"refusing to record unsafe code: {code!r}")
    fd = _open_log(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, f"{code}\n".encode("ascii"))
    finally:
        os.close(fd)


def write_log_text(path: Path, text: str, append: bool = False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else 0)
    fd = _open_log(path, flags)
    try:
        if not append:
            os.ftruncate(fd, 0)
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def read_progress_codes(path: Path) -> set:
    try:
        fd = _open_log(path, os.O_RDONLY)
    except FileNotFoundError:
        return set()
    with os.fdopen(fd, "r", encoding="utf-8", errors="replace") as f:
        return {line for line in f.read().splitlines() if is_safe_code(line)}
