"""Symlinked Illustrator script paths must not truncate the link target.

The CMYK batch scripts write generated JSX to fixed names in the repository
root (temp_run.jsx, temp_closeall.jsx, temp_convert_spot.jsx, temp_<code>.jsx).
Those names are gitignored, but a tracked symlink checked out at the same path
is followed by open() and Path.write_text().

These tests fail while that write follows a symlink. They pass when the script
text is written only inside a private temporary directory, or the fixed path is
opened with O_NOFOLLOW and a symlink is refused without creating, deleting, or
truncating anything. Looking the path up again with lstat or islink before the
write still has to fail these tests: the symlink is planted after every such
lookup and before the write.

scripts/batch_ai_cmyk.py has the same temp_run.jsx write, but the file does
not parse (unterminated string in generate_jsx), so these tests never start it.
"""

import builtins
import importlib.util
import io
import os
import runpy
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COUNTRY = "AD"
SENTINEL = b"VICTIM-SENTINEL-DO-NOT-OVERWRITE\n" * 8

def _load_script(filename):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(f"flag_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _writing_mode(mode):
    return any(flag in str(mode) for flag in ("w", "a", "x", "+"))


def _writing_flags(flags):
    return bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))


class _SwapBeforeWrite:
    """Plant a symlink after any number of stat lookups and before the write.

    Checks such as os.path.islink and Path.is_symlink see the regular file that
    was there when they ran. The symlink exists only for the write that follows.
    """

    def __init__(self, link, victim):
        self.link = os.path.abspath(link)
        self.victim = os.path.abspath(victim)
        self._busy = False
        self._real_open = builtins.open
        self._real_io_open = io.open
        self._real_os_open = os.open
        self._real_islink = os.path.islink

    def matches(self, path):
        try:
            return os.path.abspath(os.fspath(path)) == self.link
        except (TypeError, ValueError, OSError):
            return False

    def plant(self):
        if self._busy:
            return
        self._busy = True
        try:
            if self._real_islink(self.link):
                return
            if os.path.lexists(self.link):
                os.unlink(self.link)
            os.symlink(self.victim, self.link)
        finally:
            self._busy = False

    def install(self):
        swap = self

        def wrapped_open(file, mode="r", *args, **kwargs):
            if _writing_mode(mode) and swap.matches(file):
                swap.plant()
            return swap._real_open(file, mode, *args, **kwargs)

        def wrapped_io_open(file, mode="r", *args, **kwargs):
            if _writing_mode(mode) and swap.matches(file):
                swap.plant()
            return swap._real_io_open(file, mode, *args, **kwargs)

        def wrapped_os_open(path, flags, mode=0o777, *, dir_fd=None):
            if _writing_flags(flags) and swap.matches(path):
                swap.plant()
            if dir_fd is None:
                return swap._real_os_open(path, flags, mode)
            return swap._real_os_open(path, flags, mode, dir_fd=dir_fd)

        builtins.open = wrapped_open
        io.open = wrapped_io_open if io.open is not self._real_open else wrapped_open
        os.open = wrapped_os_open

    def uninstall(self):
        builtins.open = self._real_open
        io.open = self._real_io_open
        os.open = self._real_os_open


class SymlinkedTempJsxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.step1 = _load_script("step1_convert_svg_to_cmyk_ai.py")
        cls.step2 = _load_script("step2_apply_pantone_swatches.py")
        cls.update = _load_script("batch_ai_cmyk_update.py")
        cls.spot = _load_script("convert_spot_to_process.py")
        for relative in (
            f"03_svg_verified/{COUNTRY}.svg",
            f"02_official_specs/{COUNTRY}.json",
            f"04_ai_cmyk/{COUNTRY}.ai",
            "03_svg_verified/CC.svg",
        ):
            if not (ROOT / relative).exists():
                raise AssertionError(f"missing fixture {relative}")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._owned_links = []

    def tearDown(self):
        for link in self._owned_links:
            if os.path.lexists(link):
                os.unlink(link)

    def _victim(self, name):
        path = Path(self._tmp.name) / name
        path.write_bytes(SENTINEL)
        return path

    def _claim(self, name):
        link = ROOT / name
        if os.path.lexists(link):
            self.fail(f"{name} already exists in the worktree; refusing to replace it")
        self._owned_links.append(link)
        return link

    def _assert_intact(self, victim, inode, label):
        if not victim.exists() or victim.is_symlink():
            self.fail(f"{label} removed the target file")
        current = victim.stat()
        if current.st_ino != inode or not stat.S_ISREG(current.st_mode):
            self.fail(f"{label} replaced the target file")
        got = victim.read_bytes()
        if got != SENTINEL:
            self.fail(
                f"{label} wrote through the symlink "
                f"(target size {len(SENTINEL)} -> {len(got)})"
            )

    def _assert_link_kept(self, link, victim, label):
        if not os.path.islink(link):
            self.fail(f"{label} removed the symlink {link.name}")
        if os.readlink(link) != str(victim):
            self.fail(f"{label} retargeted the symlink {link.name}")

    def _plant(self, name):
        victim = self._victim(name + ".target")
        link = self._claim(name)
        os.symlink(str(victim), link)
        return link, victim, victim.stat().st_ino

    def _call(self, fn):
        try:
            fn()
        except Exception:
            return

    def _run_script(self, filename, args, fake_osascript):
        env = os.environ.copy()
        if fake_osascript:
            bindir = Path(self._tmp.name) / "bin"
            bindir.mkdir(exist_ok=True)
            exe = bindir / "osascript"
            exe.write_text("#!/bin/sh\nexit 0\n")
            exe.chmod(0o755)
            env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / filename), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def _preserved(self, paths):
        saved = []
        for path in paths:
            path = Path(path)
            saved.append((path, path.read_bytes() if path.exists() else None))
        return saved

    def _restore(self, saved):
        for path, data in saved:
            if data is None:
                if path.is_symlink() or path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

    def _preserved_ascii_root(self):
        path = Path("/tmp/flag_project")
        if path.is_symlink():
            return ("link", os.readlink(path))
        if path.exists():
            return ("keep", None)
        return ("absent", None)

    def _restore_ascii_root(self, saved):
        path = Path("/tmp/flag_project")
        kind, value = saved
        if kind == "keep":
            return
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            path.unlink()
        elif path.is_dir():
            return
        if kind == "link":
            os.symlink(value, path)

    def _direct(self, label, name, fn):
        link, victim, inode = self._plant(name)
        try:
            self._call(fn)
            self._assert_intact(victim, inode, label)
            self._assert_link_kept(link, victim, label)
        finally:
            if os.path.lexists(link):
                os.unlink(link)
            self._owned_links.remove(link)

    def _raced(self, label, name, fn):
        victim = self._victim(name + ".target")
        inode = victim.stat().st_ino
        link = self._claim(name)
        link.write_text("regular-file-seen-by-stat", encoding="utf-8")
        swap = _SwapBeforeWrite(link, victim)
        swap.install()
        try:
            self._call(fn)
        finally:
            swap.uninstall()
            if os.path.lexists(link):
                os.unlink(link)
            self._owned_links.remove(link)
        self._assert_intact(victim, inode, label)

    def _function_cases(self):
        return (
            (
                "step1.process_country",
                "temp_run.jsx",
                lambda: self.step1.process_country(COUNTRY),
            ),
            (
                "step1.close_all_documents",
                "temp_closeall.jsx",
                self.step1.close_all_documents,
            ),
            (
                "step2.process_country",
                "temp_run.jsx",
                lambda: self.step2.process_country(COUNTRY),
            ),
            (
                "step2.close_all_documents",
                "temp_closeall.jsx",
                self.step2.close_all_documents,
            ),
            (
                "batch_ai_cmyk_update.process_country",
                "temp_run.jsx",
                lambda: self.update.process_country(COUNTRY),
            ),
            (
                "batch_ai_cmyk_update.close_all_documents",
                "temp_closeall.jsx",
                self.update.close_all_documents,
            ),
            (
                "convert_spot_to_process.process_one",
                "temp_convert_spot.jsx",
                lambda: self.spot.process_one(COUNTRY),
            ),
        )

    def _script_cases(self):
        # First country in each module-level list. The write uses that name.
        return (
            ("batch_ai_cmyk_missing.py", "temp_CC.jsx"),
            ("batch_ai_cmyk_missing8.py", "temp_CC.jsx"),
        )

    def test_step1_command_does_not_overwrite_symlink_targets(self):
        """python3 scripts/step1_convert_svg_to_cmyk_ai.py --codes AD"""
        logs = self._preserved(
            (
                ROOT / "04_ai_cmyk" / "logs" / "progress_step1.txt",
            )
        )
        ascii_root = self._preserved_ascii_root()
        run_link, run_victim, run_inode = self._plant("temp_run.jsx")
        close_link, close_victim, close_inode = self._plant("temp_closeall.jsx")
        try:
            completed = self._run_script(
                "step1_convert_svg_to_cmyk_ai.py",
                ["--codes", COUNTRY],
                fake_osascript=True,
            )
            self._assert_intact(run_victim, run_inode, "step1 CLI temp_run.jsx")
            self._assert_link_kept(run_link, run_victim, "step1 CLI temp_run.jsx")
            self._assert_intact(close_victim, close_inode, "step1 CLI temp_closeall.jsx")
            self._assert_link_kept(close_link, close_victim, "step1 CLI temp_closeall.jsx")
            if completed.returncode not in (0, None) and "Traceback" in completed.stderr:
                # A refused symlink may abort the command. The targets must
                # already be unchanged above; the abort itself is not the bug.
                pass
        finally:
            self._restore(logs)
            self._restore_ascii_root(ascii_root)

    def test_step2_command_does_not_overwrite_symlink_targets(self):
        """python3 scripts/step2_apply_pantone_swatches.py --codes AD"""
        logs = self._preserved(
            (
                ROOT / "04_ai_cmyk" / "logs" / "progress_step2.txt",
            )
        )
        ascii_root = self._preserved_ascii_root()
        run_link, run_victim, run_inode = self._plant("temp_run.jsx")
        close_link, close_victim, close_inode = self._plant("temp_closeall.jsx")
        try:
            self._run_script(
                "step2_apply_pantone_swatches.py",
                ["--codes", COUNTRY],
                fake_osascript=True,
            )
            self._assert_intact(run_victim, run_inode, "step2 CLI temp_run.jsx")
            self._assert_link_kept(run_link, run_victim, "step2 CLI temp_run.jsx")
            self._assert_intact(close_victim, close_inode, "step2 CLI temp_closeall.jsx")
            self._assert_link_kept(close_link, close_victim, "step2 CLI temp_closeall.jsx")
        finally:
            self._restore(logs)
            self._restore_ascii_root(ascii_root)

    def test_shared_writers_do_not_overwrite_symlink_targets(self):
        for label, name, fn in self._function_cases():
            with self.subTest(operation=label):
                self._direct(label, name, fn)
        for filename, name in self._script_cases():
            with self.subTest(operation=filename):
                self._direct(
                    filename,
                    name,
                    lambda filename=filename: self._run_script(
                        filename, [], fake_osascript=False
                    ),
                )

    def test_writers_do_not_follow_symlink_planted_after_lookup(self):
        for label, name, fn in self._function_cases():
            with self.subTest(operation=label):
                self._raced(label + " after lookup", name, fn)
        for filename, name in self._script_cases():
            with self.subTest(operation=filename):
                script = str(ROOT / "scripts" / filename)
                self._raced(
                    filename + " after lookup",
                    name,
                    lambda script=script: runpy.run_path(script, run_name="__main__"),
                )


if __name__ == "__main__":
    unittest.main()
