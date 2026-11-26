"""
project_fs.py – 作業ツリー内のファイルをシンボリックリンクを辿らずに読み書きする

temp_*.jsx や 04_ai_cmyk/logs/ のような git 管理外のパスにも、強制追加された
シンボリックリンクがチェックアウトされ得る。ここでの関数はプロジェクトルート
配下の各パス要素を O_NOFOLLOW で開き、リンク先のファイルを書き換えない。

Illustrator に渡す JSX・保存先・エラーログは private_workdir() が新規作成する
本人専用 (0700) の一時ディレクトリに置き、結果だけを install_file() で
作業ツリーに反映する。
"""

import errno
import os
import secrets
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class SymlinkRefused(OSError):
    pass


def _relative_parts(path):
    rel = Path(path).absolute().relative_to(PROJECT_ROOT)
    parts = rel.parts
    if not parts or any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"not a file path inside the project: {path}")
    return parts


def _refuse_if_symlink(exc, path):
    if exc.errno in (errno.ELOOP, errno.EMLINK):
        raise SymlinkRefused(exc.errno, f"refusing to follow symlink in {path}") from exc
    raise exc


def _open_parent(path, create):
    """Return (dir_fd, name) for path, opening every directory without following links."""
    parts = _relative_parts(path)
    fd = os.open(PROJECT_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for depth, part in enumerate(parts[:-1], 1):
            if create:
                try:
                    os.mkdir(part, 0o777, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            except OSError as exc:
                # Linux reports ENOTDIR for a symlink opened with O_DIRECTORY | O_NOFOLLOW.
                if exc.errno == errno.ENOTDIR and os.path.islink(os.path.join(PROJECT_ROOT, *parts[:depth])):
                    raise SymlinkRefused(errno.ELOOP, f"refusing to follow symlink in {path}") from exc
                _refuse_if_symlink(exc, path)
            os.close(fd)
            fd = next_fd
    except BaseException:
        os.close(fd)
        raise
    return fd, parts[-1]


def open_project_file(path, flags, mode=0o666):
    dir_fd, name = _open_parent(path, create=bool(flags & os.O_CREAT))
    try:
        return os.open(name, flags | os.O_NOFOLLOW, mode, dir_fd=dir_fd)
    except OSError as exc:
        _refuse_if_symlink(exc, path)
    finally:
        os.close(dir_fd)


def write_text(path, text):
    fd = open_project_file(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def append_text(path, text):
    fd = open_project_file(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(text)


def copy_out(path, dest):
    """Copy a project file to dest (normally inside private_workdir), keeping its mtime."""
    fd = open_project_file(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as src:
        st = os.fstat(src.fileno())
        with open(dest, "xb") as out:
            shutil.copyfileobj(src, out)
    os.utime(dest, ns=(st.st_atime_ns, st.st_mtime_ns))


def install_file(src, path):
    """Atomically replace the directory entry at path with a copy of src.

    The rename replaces whatever entry is there, including a symlink, and
    never writes to the file a symlink points at.
    """
    dir_fd, name = _open_parent(path, create=True)
    try:
        tmp_name = f".{name}.{secrets.token_hex(8)}.tmp"
        fd = os.open(
            tmp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o666,
            dir_fd=dir_fd,
        )
        try:
            with os.fdopen(fd, "wb") as out, open(src, "rb") as f:
                shutil.copyfileobj(f, out)
            os.replace(tmp_name, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        except BaseException:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except FileNotFoundError:
                pass
            raise
    finally:
        os.close(dir_fd)


@contextmanager
def private_workdir():
    with tempfile.TemporaryDirectory(prefix="flag_project_") as d:
        yield Path(d)


def write_new(path, data: bytes):
    """Create path, which must not exist yet, and write data to it."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
