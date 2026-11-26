"""Write scratch files inside the project without following symlinks.

Progress logs, JSX error logs and temporary JSX files live at git-ignored
paths in the working tree, but a commit can still force-add a symlink at
any of those paths. Every write here opens the parent directory and the
file itself with O_NOFOLLOW, so a symlink at either place raises OSError
instead of redirecting the write, and all later reads and writes go
through the descriptor that was opened.
"""

import errno
import os
import re
import stat
from pathlib import Path

CODE_RE = re.compile(r"[A-Z]{2}(?:_[A-Za-z0-9]+)?")


def is_valid_code(code: str) -> bool:
    return CODE_RE.fullmatch(code) is not None


def filter_codes(codes):
    """Drop names that are not ISO-style codes such as ``JP`` or ``PY_reverse``."""
    valid = []
    for code in codes:
        if is_valid_code(code):
            valid.append(code)
        else:
            print(f"⚠️ 不正なコード名をスキップ: {code!r}")
    return valid


def open_no_follow(path, flags: int, mode: int = 0o644) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as e:
        raise _refusal(e, path.parent) from e
    try:
        fd = os.open(path.name, flags | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=dir_fd)
    except OSError as e:
        raise _refusal(e, path) from e
    finally:
        os.close(dir_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(errno.EINVAL, "not a regular file", str(path))
    return fd


def _refusal(error: OSError, path: Path) -> OSError:
    if error.errno in (errno.ELOOP, errno.EMLINK, errno.ENOTDIR):
        return OSError(error.errno, "refusing to write through a symlink", str(path))
    return error


def write_bytes_no_follow(path, data: bytes, *, append: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    fd = open_no_follow(path, flags)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def write_text_no_follow(path, text: str, *, append: bool = False) -> None:
    write_bytes_no_follow(path, text.encode("utf-8"), append=append)


class ProgressLog:
    """A progress log of processed codes, bound to one open file."""

    def __init__(self, path):
        fd = open_no_follow(path, os.O_RDWR | os.O_CREAT | os.O_APPEND)
        self._file = os.fdopen(fd, "a+", encoding="utf-8")

    def done_codes(self) -> set:
        self._file.seek(0)
        return {line for line in self._file.read().splitlines() if line}

    def reset(self) -> None:
        self._file.seek(0)
        self._file.truncate(0)

    def mark_done(self, code: str) -> None:
        self._file.write(f"{code}\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
