"""
safe_write.py – 作業ツリー内のシンボリックリンクを辿らない書き込みヘルパー

Illustrator 用に生成する JSX は、tempfile.mkdtemp で作るプライベートな
ディレクトリ内の新規ファイルに書き出す。リポジトリ内の固定パス
（temp_run.jsx など）は使わないため、コミットされたシンボリックリンクで
書き込み先をすり替えられない。

進捗ログなどプロジェクト内に残すファイルは、プロジェクトルートから
1階層ずつ O_NOFOLLOW で開いた親ディレクトリを基準に開く。途中や末端に
シンボリックリンクがあれば、辿らずにエラーにする。
"""

import errno
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

UTF8_BOM = b"\xef\xbb\xbf"

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@contextmanager
def private_dir(prefix: str = "flag_jsx_"):
    """所有者のみアクセス可能な一時ディレクトリを作り、終了時に削除する。"""
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def write_private_jsx(directory: Path, content: str, bom: bool = False) -> Path:
    """directory 内に新規の .jsx ファイルを排他的に作成して content を書き込む。"""
    with tempfile.NamedTemporaryFile(
        "wb", suffix=".jsx", dir=directory, delete=False
    ) as f:
        if bom:
            f.write(UTF8_BOM)
        f.write(content.encode("utf-8"))
    return Path(f.name)


def open_in_project(root: Path, path: Path, mode: str, encoding: str = "utf-8"):
    """root 配下の path を、シンボリックリンクを一切辿らずに書き込み用に開く。

    mode は "w"（切り詰め）または "a"（追記）。存在しない親ディレクトリは作成する。
    """
    if mode not in ("w", "a"):
        raise ValueError(f"unsupported mode: {mode!r}")
    parts = Path(path).relative_to(root).parts
    if not parts or any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"invalid project path: {path}")

    file_flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    file_flags |= os.O_APPEND if mode == "a" else os.O_TRUNC

    dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for name in parts[:-1]:
            try:
                os.mkdir(name, 0o755, dir_fd=dir_fd)
            except FileExistsError:
                pass
            next_fd = _open_nofollow(name, _DIR_FLAGS, root, path, dir_fd)
            os.close(dir_fd)
            dir_fd = next_fd
        fd = _open_nofollow(parts[-1], file_flags, root, path, dir_fd, 0o644)
    finally:
        os.close(dir_fd)
    return os.fdopen(fd, mode, encoding=encoding)


def _open_nofollow(name, flags, root, path, dir_fd, perm=0o777):
    try:
        return os.open(name, flags, perm, dir_fd=dir_fd)
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.ENOTDIR, errno.EMLINK):
            raise OSError(
                e.errno,
                f"refusing to write through a symlink or non-directory under {root}",
                str(path),
            ) from None
        raise


def copy_into_project(src: Path, root: Path, dest: Path, mode: str) -> None:
    """src が存在すれば、その内容を root 配下の dest に書き込む（"w" または "a"）。"""
    try:
        data = src.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return
    with open_in_project(root, dest, mode) as f:
        f.write(data)
