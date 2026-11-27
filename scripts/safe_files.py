"""
safe_files.py – Illustrator バッチ用の一時ファイル・出力ファイルを安全に扱う

作業ツリー内のパスは git 管理下のシンボリックリンクに差し替えられ得るため:
- 生成JSXや Illustrator の作業ファイルは、呼び出しごとに tempfile.mkdtemp() で
  作る本人専用ディレクトリ（0700）内にだけ作る。
- プロジェクト内のファイルは PROJECT_ROOT から1階層ずつ O_NOFOLLOW で開き、
  途中や末端がシンボリックリンクなら OSError (ELOOP) で中止する。
- 出力は同じディレクトリ内の新規一時名に書いてから rename で差し替える。
  既存のシンボリックリンクはリンク先ではなくリンク自体が置き換わる。
"""

import contextlib
import os
import secrets
import shutil
import stat
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextlib.contextmanager
def private_dir():
    """本人専用の一時ディレクトリを yield し、終了時に中身ごと削除する。"""
    path = tempfile.mkdtemp(prefix="flag_jsx_")
    try:
        yield Path(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def write_private(path, content, bom=False):
    """private_dir() 内に新規ファイルを作成して content を書く。"""
    data = content.encode("utf-8") if isinstance(content, str) else content
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        if bom:
            f.write(b"\xef\xbb\xbf")
        f.write(data)


@contextlib.contextmanager
def temp_jsx(content, bom=False):
    """content を書いた一時 .jsx のパスを yield し、終了時に削除する。"""
    with private_dir() as d:
        path = d / "script.jsx"
        write_private(path, content, bom=bom)
        yield str(path)


def _split(path):
    rel = Path(path).relative_to(PROJECT_ROOT)
    parts = rel.parts
    if not parts or any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"invalid project path: {path}")
    return parts[:-1], parts[-1]


def _open_project_dir(parts, create=False):
    fd = os.open(PROJECT_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o777, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
    except BaseException:
        os.close(fd)
        raise
    return fd


def make_project_dirs(path):
    """PROJECT_ROOT 配下のディレクトリを作成する（シンボリックリンクは辿らない）。"""
    parents, name = _split(path)
    os.close(_open_project_dir(parents + (name,), create=True))


def open_project_file(path, mode):
    """PROJECT_ROOT 配下のファイルを "w"（切り詰め）または "a"（追記）で開く。"""
    flags = {"w": os.O_TRUNC, "a": os.O_APPEND}[mode]
    parents, name = _split(path)
    dfd = _open_project_dir(parents, create=True)
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | flags, 0o666, dir_fd=dfd)
    finally:
        os.close(dfd)
    return os.fdopen(fd, mode, encoding="utf-8")


def copy_project_file(src, dest):
    """PROJECT_ROOT 配下の通常ファイル src を private_dir() 内の dest に複製する。"""
    parents, name = _split(src)
    dfd = _open_project_dir(parents)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
    finally:
        os.close(dfd)
    with os.fdopen(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise OSError(f"not a regular file: {src}")
        write_private(dest, f.read())


def install_project_file(src, dest):
    """private_dir() 内の src の内容で PROJECT_ROOT 配下の dest を置き換える。"""
    parents, name = _split(dest)
    dfd = _open_project_dir(parents, create=True)
    staging = f".{name}.{secrets.token_hex(8)}.tmp"
    try:
        out = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o666, dir_fd=dfd)
        try:
            with os.fdopen(out, "wb") as fout, open(src, "rb") as fin:
                shutil.copyfileobj(fin, fout)
            os.replace(staging, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(staging, dir_fd=dfd)
            raise
    finally:
        os.close(dfd)
