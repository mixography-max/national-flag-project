#!/usr/bin/env python3
"""Symlink overwrite regressions for generated Illustrator scripts.

These tests are expected to fail while the batch scripts write fixed paths
(temp_run.jsx, temp_closeall.jsx, temp_convert_spot.jsx, temp_<code>.jsx, and
the gitignored progress logs) with open() or Path.write_text(). Both follow
symlinks, so a checked-out link replaces the target file.

They pass once each of those writes goes to a private temporary file, or the
fixed path is opened with O_NOFOLLOW and a symlink is refused before any
truncate. A check that the path is not a symlink, followed by a later open of
the same path, still fails the swapped_after_lstat tests: those tests report a
regular file to lstat and put the symlink back if it is removed.
"""

import importlib.util
import os
import runpy
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SENTINEL = b"ORIGINAL_SECRET_DO_NOT_OVERWRITE\n"
SIX_CODES = ["CC", "CC", "CC", "CC", "CC", "CC"]


def load_script(filename):
    path = REPO / "scripts" / filename
    module_name = "under_test_" + filename.replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class JsxSymlinkOverwriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_script("batch_ai_cmyk_update.py")
        cls.step1 = load_script("step1_convert_svg_to_cmyk_ai.py")
        cls.step2 = load_script("step2_apply_pantone_swatches.py")
        cls.convert = load_script("convert_spot_to_process.py")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jsx-symlink-"))
        self.planted = []
        self._plant_seq = 0
        self.logs = REPO / "04_ai_cmyk" / "logs"
        self.logs_existed = self.logs.exists()
        self.log_names_before = (
            {p.name for p in self.logs.iterdir()} if self.logs_existed else set()
        )
        self.jsx_before = {p.name for p in REPO.glob("temp_*.jsx")}
        self.flag = Path("/tmp/flag_project")
        self.flag_link = os.readlink(self.flag) if self.flag.is_symlink() else None
        self.flag_was_nonsymlink = self.flag.exists() and not self.flag.is_symlink()
        self._stat = os.stat
        self._lstat = os.lstat
        self._unlink = os.unlink
        self._remove = os.remove

    def tearDown(self):
        os.stat = self._stat
        os.lstat = self._lstat
        os.unlink = self._unlink
        os.remove = self._remove
        try:
            for path, displaced in reversed(self.planted):
                if path.is_symlink() or (path.exists() and not path.is_dir()):
                    path.unlink()
                if displaced is not None and os.path.lexists(displaced) and not os.path.lexists(path):
                    os.rename(displaced, path)
                elif displaced is not None and displaced.is_symlink():
                    displaced.unlink()
            for path in REPO.glob("temp_*.jsx"):
                if path.name not in self.jsx_before and (path.is_symlink() or path.is_file()):
                    path.unlink()
            if self.logs.exists():
                for path in list(self.logs.iterdir()):
                    if path.name not in self.log_names_before and (
                        path.is_symlink() or path.is_file()
                    ):
                        path.unlink()
                if not self.logs_existed and not any(self.logs.iterdir()):
                    self.logs.rmdir()
        finally:
            self._restore_flag_project()
            if self.tmp.exists():
                shutil.rmtree(self.tmp, ignore_errors=True)

    def _restore_flag_project(self):
        if self.flag_was_nonsymlink:
            return
        if self.flag.is_symlink() or (self.flag.exists() and not self.flag.is_dir()):
            self.flag.unlink()
        if self.flag_link is not None and not self.flag.exists():
            os.symlink(self.flag_link, self.flag)

    def new_victim(self):
        handle, name = tempfile.mkstemp(prefix="victim-", dir=self.tmp)
        os.write(handle, SENTINEL)
        os.close(handle)
        return Path(name)

    def plant(self, path: Path, victim: Path, relative=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        displaced = None
        if path.is_symlink() or path.exists():
            self._plant_seq += 1
            displaced = self.tmp / f"displaced-{self._plant_seq}-{path.name}"
            os.rename(path, displaced)
        target = os.path.relpath(victim, path.parent) if relative else os.fspath(victim)
        path.symlink_to(target)
        self.planted.append((path, displaced))
        return path

    def assert_intact(self, victim: Path):
        raw = victim.read_bytes()
        self.assertEqual(
            raw,
            SENTINEL,
            f"{victim} was modified ({len(raw)} bytes, starts {raw[:48]!r})",
        )

    def invoke(self, fn):
        try:
            return fn()
        except Exception:
            return None

    def conceal_symlink(self, links):
        """Lie to lstat about links, and replace any of them if removed.

        Models a symlink that appears after a 'not a symlink' check and before
        open(). The real open() syscall still follows the directory entry.
        """
        targets = {}
        for link in links:
            targets[os.path.abspath(link)] = os.readlink(link)
        dummy = self.tmp / "regular-stand-in"
        if not dummy.exists():
            dummy.write_text("regular")
        real_stat = os.stat
        real_lstat = os.lstat
        real_unlink = os.unlink
        real_symlink = os.symlink

        def same(path):
            try:
                return os.path.abspath(os.fspath(path)) in targets
            except (TypeError, ValueError):
                return False

        def stat(path, *, dir_fd=None, follow_symlinks=True):
            if same(path) and not follow_symlinks:
                return real_stat(dummy)
            return real_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

        def lstat(path, *, dir_fd=None):
            if same(path):
                return real_lstat(dummy)
            return real_lstat(path, dir_fd=dir_fd)

        def unlink(path, *, dir_fd=None):
            matched = same(path)
            key = os.path.abspath(os.fspath(path)) if matched else None
            if dir_fd is None:
                real_unlink(path)
            else:
                real_unlink(path, dir_fd=dir_fd)
            if matched:
                try:
                    real_lstat(path)
                except OSError:
                    real_symlink(targets[key], path)

        os.stat = stat
        os.lstat = lstat
        os.unlink = unlink
        os.remove = unlink
        return self._Conceal(self)

    class _Conceal:
        def __init__(self, test):
            self.test = test

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.test._restore_os()
            return False

    def _restore_os(self):
        os.stat = self._stat
        os.lstat = self._lstat
        os.unlink = self._unlink
        os.remove = self._remove

    def fake_osascript(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir(exist_ok=True)
        exe = bin_dir / "osascript"
        exe.write_text("#!/bin/sh\nexit 1\n")
        exe.chmod(0o755)
        return bin_dir

    def call_main(self, module, argv, fake_osascript=False):
        saved_argv = sys.argv
        saved_sleep = module.time.sleep
        saved_path = os.environ.get("PATH")
        sys.argv = argv
        module.time.sleep = lambda *_args, **_kwargs: None
        if fake_osascript:
            os.environ["PATH"] = str(self.fake_osascript()) + os.pathsep + (
                saved_path or ""
            )
        try:
            self.invoke(module.main)
        finally:
            sys.argv = saved_argv
            module.time.sleep = saved_sleep
            if saved_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = saved_path

    def test_cli_all_does_not_follow_temp_run_symlink(self):
        victim = self.new_victim()
        self.plant(REPO / "temp_run.jsx", victim)
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "batch_ai_cmyk_update.py"), "--all"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw = victim.read_bytes()
        self.assertEqual(
            raw,
            SENTINEL,
            f"cli --all followed temp_run.jsx ({len(raw)} bytes, starts {raw[:48]!r}); "
            f"stderr={proc.stderr[-300:]!r}",
        )

    def test_relative_symlink_outside_repo_is_not_followed(self):
        victim = self.new_victim()
        link = self.plant(REPO / "temp_run.jsx", victim, relative=True)
        self.assertTrue(os.path.islink(link))
        self.assertFalse(Path(os.path.realpath(link)).is_relative_to(REPO))
        self.invoke(lambda: self.update.process_country("CC"))
        self.assert_intact(victim)

    def test_direct_writes_do_not_follow_symlink(self):
        cases = [
            ("update.process_country", REPO / "temp_run.jsx", lambda: self.update.process_country("CC")),
            ("update.close_all_documents", REPO / "temp_closeall.jsx", self.update.close_all_documents),
            ("update.mark_done", self.update.PROGRESS_LOG, lambda: self.update.mark_done("CC")),
            ("step1.process_country", REPO / "temp_run.jsx", lambda: self.step1.process_country("CC")),
            ("step1.close_all_documents", REPO / "temp_closeall.jsx", self.step1.close_all_documents),
            ("step1.mark_done", self.step1.PROGRESS_LOG, lambda: self.step1.mark_done("CC")),
            ("step2.process_country", REPO / "temp_run.jsx", lambda: self.step2.process_country("CC")),
            ("step2.close_all_documents", REPO / "temp_closeall.jsx", self.step2.close_all_documents),
            ("step2.mark_done", self.step2.PROGRESS_LOG, lambda: self.step2.mark_done("CC")),
            ("convert.process_one", self.convert.JSX_PATH, lambda: self.convert.process_one("CC")),
            ("convert.mark_done", self.convert.PROGRESS_LOG, lambda: self.convert.mark_done("CC")),
        ]
        for name, path, fn in cases:
            with self.subTest(name=name):
                victim = self.new_victim()
                self.plant(path, victim)
                try:
                    self.invoke(fn)
                    self.assert_intact(victim)
                finally:
                    self._unplant(path)

    def test_direct_writes_do_not_follow_symlink_swapped_after_lstat(self):
        cases = [
            ("update.process_country", REPO / "temp_run.jsx", lambda: self.update.process_country("CC")),
            ("update.close_all_documents", REPO / "temp_closeall.jsx", self.update.close_all_documents),
            ("update.mark_done", self.update.PROGRESS_LOG, lambda: self.update.mark_done("CC")),
            ("step1.process_country", REPO / "temp_run.jsx", lambda: self.step1.process_country("CC")),
            ("step1.close_all_documents", REPO / "temp_closeall.jsx", self.step1.close_all_documents),
            ("step1.mark_done", self.step1.PROGRESS_LOG, lambda: self.step1.mark_done("CC")),
            ("step2.process_country", REPO / "temp_run.jsx", lambda: self.step2.process_country("CC")),
            ("step2.close_all_documents", REPO / "temp_closeall.jsx", self.step2.close_all_documents),
            ("step2.mark_done", self.step2.PROGRESS_LOG, lambda: self.step2.mark_done("CC")),
            ("convert.process_one", self.convert.JSX_PATH, lambda: self.convert.process_one("CC")),
            ("convert.mark_done", self.convert.PROGRESS_LOG, lambda: self.convert.mark_done("CC")),
        ]
        for name, path, fn in cases:
            with self.subTest(name=name):
                victim = self.new_victim()
                link = self.plant(path, victim)
                try:
                    with self.conceal_symlink([link]):
                        # lstat is told this is a regular file; the directory entry is still a symlink.
                        self.assertFalse(stat.S_ISLNK(os.lstat(link).st_mode))
                        self.assertTrue(stat.S_ISLNK(self._lstat(link).st_mode))
                        self.invoke(fn)
                    self.assert_intact(victim)
                finally:
                    self._unplant(path)

    def test_main_every_five_and_final_close_do_not_follow_symlinks(self):
        modules = [
            ("update", self.update),
            ("step1", self.step1),
            ("step2", self.step2),
        ]
        for name, module in modules:
            with self.subTest(script=name):
                run = self.new_victim()
                close = self.new_victim()
                progress = self.new_victim()
                self.plant(REPO / "temp_run.jsx", run)
                self.plant(REPO / "temp_closeall.jsx", close)
                self.plant(module.PROGRESS_LOG, progress)
                try:
                    self.call_main(
                        module,
                        [name + ".py", "--codes", *SIX_CODES],
                        fake_osascript=True,
                    )
                    with self.subTest(script=name, path="temp_run.jsx"):
                        self.assert_intact(run)
                    with self.subTest(script=name, path="temp_closeall.jsx"):
                        self.assert_intact(close)
                    with self.subTest(script=name, path="progress"):
                        self.assert_intact(progress)
                finally:
                    self._unplant(REPO / "temp_run.jsx")
                    self._unplant(REPO / "temp_closeall.jsx")
                    self._unplant(module.PROGRESS_LOG)

    def test_main_symlinks_swapped_after_lstat(self):
        modules = [
            ("update", self.update),
            ("step1", self.step1),
            ("step2", self.step2),
        ]
        for name, module in modules:
            with self.subTest(script=name):
                run = self.new_victim()
                close = self.new_victim()
                progress = self.new_victim()
                links = [
                    self.plant(REPO / "temp_run.jsx", run),
                    self.plant(REPO / "temp_closeall.jsx", close),
                    self.plant(module.PROGRESS_LOG, progress),
                ]
                try:
                    with self.conceal_symlink(links):
                        self.call_main(
                            module,
                            [name + ".py", "--codes", *SIX_CODES],
                            fake_osascript=True,
                        )
                    with self.subTest(script=name, path="temp_run.jsx"):
                        self.assert_intact(run)
                    with self.subTest(script=name, path="temp_closeall.jsx"):
                        self.assert_intact(close)
                    with self.subTest(script=name, path="progress"):
                        self.assert_intact(progress)
                finally:
                    for link in links:
                        self._unplant(link)

    def test_import_scripts_do_not_follow_temp_code_symlink(self):
        for filename in ("batch_ai_cmyk_missing.py", "batch_ai_cmyk_missing8.py"):
            with self.subTest(script=filename):
                victim = self.new_victim()
                self.plant(REPO / "temp_CC.jsx", victim)
                try:
                    subprocess.run(
                        [sys.executable, str(REPO / "scripts" / filename)],
                        cwd=REPO,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assert_intact(victim)
                finally:
                    self._unplant(REPO / "temp_CC.jsx")

    def test_import_scripts_do_not_follow_symlink_swapped_after_lstat(self):
        for filename in ("batch_ai_cmyk_missing.py", "batch_ai_cmyk_missing8.py"):
            with self.subTest(script=filename):
                victim = self.new_victim()
                link = self.plant(REPO / "temp_CC.jsx", victim)
                try:
                    with self.conceal_symlink([link]):
                        try:
                            runpy.run_path(
                                str(REPO / "scripts" / filename), run_name="__not_main__"
                            )
                        except SystemExit:
                            pass
                        except Exception:
                            pass
                    self.assert_intact(victim)
                finally:
                    self._unplant(link)

    def _unplant(self, path: Path):
        path = Path(path)
        kept = []
        for planted, displaced in self.planted:
            if os.path.abspath(planted) == os.path.abspath(path):
                if path.is_symlink() or (path.exists() and not path.is_dir()):
                    path.unlink()
                if (
                    displaced is not None
                    and os.path.lexists(displaced)
                    and not os.path.lexists(path)
                ):
                    os.rename(displaced, path)
            else:
                kept.append((planted, displaced))
        self.planted = kept


if __name__ == "__main__":
    unittest.main()
