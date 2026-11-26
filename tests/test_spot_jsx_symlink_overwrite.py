"""Failing tests for the spot-to-process temporary script symlink write.

`scripts/convert_spot_to_process.py` writes its generated Illustrator script
to a fixed path, `temp_convert_spot.jsx`, then later unlinks that path.
`Path.write_text` and the progress-log append follow symlinks. A gitignored
name can still be force-added, and checkout recreates the link. These tests
drive that path. They fail while the target file is created, truncated, or
replaced, and they pass once the script stops following the link.

A symlink check that is reused for the later open still fails: lstat, stat
with follow_symlinks false, and readlink report a regular file while the
kernel open still sees the symlink. Unlink is not a safe check either: if
the path is removed, the tests put the symlink back before the next open.

Not covered here, because they are separate entry points:

- scripts/batch_ai_cmyk.py opens temp_run.jsx
- scripts/batch_ai_cmyk_missing.py and batch_ai_cmyk_missing8.py write
  temp_{code}.jsx at import
- scripts/batch_ai_cmyk_update.py, step1_convert_svg_to_cmyk_ai.py, and
  step2_apply_pantone_swatches.py write temp_run.jsx and temp_closeall.jsx
- get_done_codes only reads the progress log
"""

from __future__ import annotations

import errno
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "convert_spot_to_process.py"
ORIGINAL = b"maintainer file original contents\n"


def load_script():
    module_name = f"spot_under_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.time.sleep = lambda *_args, **_kwargs: None
    return module


def read_nofollow(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        return os.read(fd, 1_000_000)
    finally:
        os.close(fd)


def run_main(module, argv: list[str]):
    old_argv = sys.argv
    sys.argv = argv
    try:
        module.main()
    finally:
        sys.argv = old_argv


@contextmanager
def pretend_path_is_regular(path: Path):
    """Lie to userspace symlink checks for one path.

    lstat, non-following stat, and readlink report a regular file. The
    kernel open of that path is left alone, so O_NOFOLLOW still sees the
    symlink and an open that follows one still writes the target.
    """
    wanted = os.path.abspath(path)
    real_stat = os.stat
    real_lstat = os.lstat
    real_readlink = os.readlink

    def same(candidate) -> bool:
        try:
            return os.path.abspath(os.fspath(candidate)) == wanted
        except (TypeError, ValueError):
            return False

    def fake_stat(candidate, *args, follow_symlinks=True, **kwargs):
        if same(candidate) and not follow_symlinks:
            return real_stat(candidate, *args, follow_symlinks=True, **kwargs)
        return real_stat(candidate, *args, follow_symlinks=follow_symlinks, **kwargs)

    def fake_lstat(candidate, *args, **kwargs):
        if same(candidate):
            return real_stat(candidate)
        return real_lstat(candidate, *args, **kwargs)

    def fake_readlink(candidate, *args, **kwargs):
        if same(candidate):
            raise OSError(errno.EINVAL, "Invalid argument")
        return real_readlink(candidate, *args, **kwargs)

    os.stat = fake_stat
    os.lstat = fake_lstat
    os.readlink = fake_readlink
    try:
        yield
    finally:
        os.stat = real_stat
        os.lstat = real_lstat
        os.readlink = real_readlink


@contextmanager
def replant_symlink_after_unlink(link: Path, victim: Path):
    """Win the race between unlink and the next open of the same path."""
    wanted = os.path.abspath(link)
    real_unlink = os.unlink
    real_remove = os.remove

    def same(candidate) -> bool:
        try:
            return os.path.abspath(os.fspath(candidate)) == wanted
        except (TypeError, ValueError):
            return False

    def wrapped_unlink(candidate, *args, **kwargs):
        real_unlink(candidate, *args, **kwargs)
        if same(candidate):
            os.symlink(victim, candidate)

    def wrapped_remove(candidate, *args, **kwargs):
        real_remove(candidate, *args, **kwargs)
        if same(candidate):
            os.symlink(victim, candidate)

    os.unlink = wrapped_unlink
    os.remove = wrapped_remove
    try:
        yield
    finally:
        os.unlink = real_unlink
        os.remove = real_remove


class SpotJsxSymlinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_script()

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="spot-jsx-"))
        self._cleanup_paths = []
        self._real_jsx = REPO / "temp_convert_spot.jsx"
        self._real_jsx_existed = self._real_jsx.is_symlink() or self._real_jsx.exists()

    def tearDown(self):
        for path in self._cleanup_paths:
            if path.is_symlink() or path.exists():
                path.unlink()
        if not self._real_jsx_existed and (
            self._real_jsx.is_symlink() or self._real_jsx.exists()
        ):
            self._real_jsx.unlink()
        shutil.rmtree(self._tmp, ignore_errors=True)
        module = self.module
        module.JSX_PATH = module.PROJECT_ROOT / "temp_convert_spot.jsx"
        module.AI_DIR = module.PROJECT_ROOT / "04_ai_cmyk"
        module.PROGRESS_LOG = (
            module.PROJECT_ROOT / "04_ai_cmyk" / "logs" / "spot_to_process_done.txt"
        )
        module.subprocess.run = subprocess.run

    def _victim(self, name: str, *, create: bool) -> tuple[Path, int | None]:
        path = self._tmp / name
        if create:
            path.write_bytes(ORIGINAL)
            return path, path.stat().st_ino
        return path, None

    def _plant(self, link: Path, victim: Path):
        if link.is_symlink() or link.exists():
            raise AssertionError(f"refusing to replace existing path {link}")
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(victim)
        self._cleanup_paths.append(link)

    def _one_ai_dir(self) -> Path:
        ai_dir = self._tmp / "ai"
        ai_dir.mkdir()
        (ai_dir / "ZZ.ai").write_bytes(b"placeholder ai")
        return ai_dir

    def _bind_single_file(self, *, jsx: Path | None = None, log: Path | None = None):
        module = self.module
        module.AI_DIR = self._one_ai_dir()
        if jsx is not None:
            module.JSX_PATH = jsx
        if log is not None:
            module.PROGRESS_LOG = log

    def _allow(self, fn):
        try:
            fn()
        except Exception:
            return

    def assert_victim_unchanged(self, victim: Path, inode: int):
        self.assertTrue(victim.exists(), "symlink target was deleted")
        self.assertFalse(victim.is_symlink())
        self.assertEqual(victim.stat().st_ino, inode, "symlink target was replaced")
        self.assertEqual(read_nofollow(victim), ORIGINAL)

    def test_cli_codes_does_not_overwrite_checked_in_symlink_shape(self):
        victim, inode = self._victim("maintainer-file", create=True)
        self._plant(self.module.JSX_PATH, victim)
        subprocess.run(
            [sys.executable, str(SCRIPT), "--codes", "AD"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        self.assert_victim_unchanged(victim, inode)

    def test_checked_out_force_added_symlink_is_not_overwritten(self):
        victim, inode = self._victim("maintainer-file", create=True)
        origin = self._tmp / "origin"
        origin.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=origin, check=True)
        subprocess.run(
            ["git", "config", "user.email", "tests@example.com"],
            cwd=origin,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Symlink Tests"],
            cwd=origin,
            check=True,
        )
        subprocess.run(
            ["git", "config", "core.symlinks", "true"],
            cwd=origin,
            check=True,
        )
        (origin / ".gitignore").write_text("temp_*.jsx\n", encoding="utf-8")
        script_dir = origin / "scripts"
        script_dir.mkdir()
        shutil.copy(SCRIPT, script_dir / "convert_spot_to_process.py")
        ai_dir = origin / "04_ai_cmyk"
        ai_dir.mkdir()
        (ai_dir / "ZZ.ai").write_bytes(b"placeholder ai")
        subprocess.run(["git", "add", ".gitignore", "scripts", "04_ai_cmyk"], cwd=origin, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=origin, check=True)
        link = origin / "temp_convert_spot.jsx"
        link.symlink_to(victim)
        subprocess.run(["git", "add", "-f", "temp_convert_spot.jsx"], cwd=origin, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "force-add symlink"], cwd=origin, check=True)
        clone = self._tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "-c", "core.symlinks=true", str(origin), str(clone)],
            check=True,
        )
        checked_out = clone / "temp_convert_spot.jsx"
        self.assertTrue(checked_out.is_symlink(), "checkout did not materialize the symlink")
        self.assertEqual(os.path.realpath(checked_out), os.path.realpath(victim))
        subprocess.run(
            [sys.executable, str(clone / "scripts" / "convert_spot_to_process.py"), "--codes", "ZZ"],
            cwd=clone,
            capture_output=True,
            text=True,
        )
        self.assert_victim_unchanged(victim, inode)

    def test_process_one_does_not_overwrite_absolute_symlink(self):
        victim, inode = self._victim("maintainer-file", create=True)
        link = self._tmp / "temp_convert_spot.jsx"
        self._plant(link, victim)
        self._bind_single_file(jsx=link)
        self._allow(lambda: self.module.process_one("ZZ", dry_run=False))
        self.assert_victim_unchanged(victim, inode)

    def test_resume_mode_does_not_overwrite_absolute_symlink(self):
        victim, inode = self._victim("maintainer-file", create=True)
        self._plant(self.module.JSX_PATH, victim)
        log = self._tmp / "spot_to_process_done.txt"
        log.write_text("OTHER\n", encoding="utf-8")
        self._bind_single_file(log=log)
        self._allow(
            lambda: run_main(
                self.module,
                ["convert_spot_to_process.py", "--resume", "--codes", "ZZ"],
            )
        )
        self.assert_victim_unchanged(victim, inode)

    def test_default_mode_does_not_overwrite_absolute_symlink(self):
        victim, inode = self._victim("maintainer-file", create=True)
        self._plant(self.module.JSX_PATH, victim)
        log = self._tmp / "spot_to_process_done.txt"
        log.write_bytes(ORIGINAL)
        self._bind_single_file(log=log)
        # osascript is not installed here. A failing Illustrator result lets
        # main() reach the final unlink without skipping the earlier write.
        self.module.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0] if args else [], 1, stdout="", stderr="illustrator unavailable"
        )
        self._allow(lambda: run_main(self.module, ["convert_spot_to_process.py"]))
        self.assert_victim_unchanged(victim, inode)

    def test_broken_symlink_does_not_create_target(self):
        victim, _inode = self._victim("new-maintainer-file", create=False)
        self._plant(self.module.JSX_PATH, victim)
        self._bind_single_file()
        self._allow(lambda: self.module.process_one("ZZ", dry_run=False))
        self.assertFalse(victim.exists(), "open created the symlink target")

    def test_dry_run_does_not_touch_symlink_target(self):
        victim, inode = self._victim("maintainer-file", create=True)
        self._plant(self.module.JSX_PATH, victim)
        self._bind_single_file()
        run_main(
            self.module,
            ["convert_spot_to_process.py", "--dry-run", "--codes", "ZZ"],
        )
        self.assert_victim_unchanged(victim, inode)
        self.assertTrue(self.module.JSX_PATH.is_symlink())

    def test_jsx_symlink_checks_cannot_be_reused_before_write(self):
        victim, inode = self._victim("maintainer-file", create=True)
        link = self.module.JSX_PATH
        self._plant(link, victim)
        self._bind_single_file()
        with pretend_path_is_regular(link):
            self._allow(lambda: self.module.process_one("ZZ", dry_run=False))
        self.assert_victim_unchanged(victim, inode)

    def test_jsx_symlink_replanted_after_unlink_is_not_followed(self):
        victim, inode = self._victim("maintainer-file", create=True)
        link = self.module.JSX_PATH
        self._plant(link, victim)
        self._bind_single_file()
        with replant_symlink_after_unlink(link, victim):
            self._allow(lambda: self.module.process_one("ZZ", dry_run=False))
        self.assert_victim_unchanged(victim, inode)

    def test_success_records_code_in_regular_progress_log(self):
        log = self._tmp / "logs" / "spot_to_process_done.txt"
        log.parent.mkdir()
        jsx = self._tmp / "temp_convert_spot.jsx"
        self._bind_single_file(jsx=jsx, log=log)
        self.module.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0] if args else [], 0, stdout="2", stderr=""
        )
        run_main(self.module, ["convert_spot_to_process.py", "--codes", "ZZ"])
        self.assertIn("ZZ", log.read_text(encoding="utf-8").splitlines())

    def test_success_does_not_append_through_progress_symlink(self):
        victim, inode = self._victim("maintainer-file", create=True)
        log = self._tmp / "logs" / "spot_to_process_done.txt"
        self._plant(log, victim)
        jsx = self._tmp / "temp_convert_spot.jsx"
        self._bind_single_file(jsx=jsx, log=log)
        self.module.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0] if args else [], 0, stdout="2", stderr=""
        )
        self._allow(
            lambda: run_main(
                self.module, ["convert_spot_to_process.py", "--codes", "ZZ"]
            )
        )
        self.assert_victim_unchanged(victim, inode)

    def test_progress_symlink_checks_cannot_be_reused_before_append(self):
        victim, inode = self._victim("maintainer-file", create=True)
        log = self._tmp / "logs" / "spot_to_process_done.txt"
        self._plant(log, victim)
        jsx = self._tmp / "temp_convert_spot.jsx"
        self._bind_single_file(jsx=jsx, log=log)
        self.module.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0] if args else [], 0, stdout="2", stderr=""
        )
        with pretend_path_is_regular(log):
            self._allow(
                lambda: run_main(
                    self.module, ["convert_spot_to_process.py", "--codes", "ZZ"]
                )
            )
        self.assert_victim_unchanged(victim, inode)

    def test_progress_symlink_replanted_after_unlink_is_not_followed(self):
        victim, inode = self._victim("maintainer-file", create=True)
        log = self._tmp / "logs" / "spot_to_process_done.txt"
        self._plant(log, victim)
        jsx = self._tmp / "temp_convert_spot.jsx"
        self._bind_single_file(jsx=jsx, log=log)
        self.module.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0] if args else [], 0, stdout="2", stderr=""
        )
        with replant_symlink_after_unlink(log, victim):
            self._allow(
                lambda: run_main(
                    self.module, ["convert_spot_to_process.py", "--codes", "ZZ"]
                )
            )
        self.assert_victim_unchanged(victim, inode)

    def test_fresh_run_does_not_delete_progress_symlink_target(self):
        victim, inode = self._victim("maintainer-file", create=True)
        log = self._tmp / "logs" / "spot_to_process_done.txt"
        self._plant(log, victim)
        self._bind_single_file(log=log)
        self.module.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0] if args else [], 1, stdout="", stderr="illustrator unavailable"
        )
        self._allow(lambda: run_main(self.module, ["convert_spot_to_process.py"]))
        self.assert_victim_unchanged(victim, inode)


if __name__ == "__main__":
    unittest.main()
