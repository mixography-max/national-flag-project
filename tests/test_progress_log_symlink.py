"""Security tests for progress-log writes that follow symlinks.

The spot-to-process converter, and the other Illustrator batch scripts that
share its progress log, append or truncate
``04_ai_cmyk/logs/<name>`` with the normal open() that follows symlinks.
Resume mode (and ``--codes`` on the spot converter) never removes an
existing log first. A log path that is a symlink therefore turns the
converted file's code into bytes appended to whatever file the symlink
points at. Codes taken from AI/SVG/JSON file names are not restricted, so
a file whose name is a shell command becomes a new line in that file.

These tests exercise the real ``main`` functions. They fail while that
write follows a symlink, including when the path is replaced with a
symlink after a stat and before the open. They pass once a write refuses
to follow a symlink (open the final path with ``O_NOFOLLOW`` / ``openat``,
not a check that looks the path up again) and the spot converter records
only codes shaped like two uppercase letters with an optional underscore
suffix.

Adobe Illustrator is not invoked. The spot converter reaches its log write
only after ``osascript`` returns success, so these tests place a local
``osascript`` on ``PATH`` that implements the success contract in
``convert_spot_to_process.process_one``: exit 0 and a stdout count, and
only when the JSX this process wrote contains the AI path inside one
double-quoted ``File("...")`` string that names an existing file. The
sibling scripts call ``mark_done`` on ``SKIP_*`` before Illustrator, so
those tests need no stand-in.

Not covered here, because the write runs inside Illustrator rather than in
Python:
``scripts/batch_ai_cmyk_missing.py`` (JSX ``log.open("a")`` on ``error.log``),
and the JSX error logs in ``step1_convert_svg_to_cmyk_ai.py``,
``step2_apply_pantone_swatches.py``, and ``batch_ai_cmyk_update.py``.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
CODE_PATTERN_SAMPLE = "US"
UNDERSCORE_CODE = "PY_reverse"
# A single path component: no slash, no quote, no brace. It is a shell
# command when a startup file sources the line.
SHELL_STEM = "echo spotlog-poc | tee spotlog-out"
SENTINEL = b"ORIGINAL\n"


def _load(module_name: str, filename: str):
    path = REPO / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _same(path, log: Path) -> bool:
    try:
        return os.path.abspath(os.fspath(path)) == os.path.abspath(os.fspath(log))
    except (TypeError, ValueError):
        return False


@contextmanager
def swap_log_to_symlink_on_open(log: Path, target: Path):
    """Replace ``log`` with a symlink to ``target`` at the moment it is opened.

    A check that only stats the path still sees a regular file. The
    following open by path then follows the symlink. ``O_NOFOLLOW`` /
    ``openat`` fails instead of writing ``target``.
    """
    state = {"done": False}
    real_open = open
    real_os_open = os.open
    real_path_open = Path.open

    def swap() -> None:
        if state["done"]:
            return
        state["done"] = True
        if stat.S_ISLNK(os.lstat(log).st_mode):
            return
        os.unlink(log)
        os.symlink(target, log)

    def open_hook(file, mode="r", *args, **kwargs):
        text_mode = mode if isinstance(mode, str) else ""
        if any(flag in text_mode for flag in ("a", "w", "x")) and _same(file, log):
            swap()
        return real_open(file, mode, *args, **kwargs)

    def path_open(self, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("a", "w", "x")) and _same(self, log):
            swap()
        return real_path_open(self, mode, *args, **kwargs)

    def os_open_hook(path, flags, mode=0o777, *, dir_fd=None):
        if dir_fd is not None:
            if os.path.basename(os.fspath(path)) == log.name:
                swap()
        elif _same(path, log):
            swap()
        if dir_fd is None:
            return real_os_open(path, flags, mode)
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    Path.open = path_open
    os.open = os_open_hook
    try:
        yield open_hook
    finally:
        Path.open = real_path_open
        os.open = real_os_open


class ProgressLogSymlinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spot = _load("convert_spot_to_process_under_test", "convert_spot_to_process.py")
        cls.step1 = _load("step1_under_test", "step1_convert_svg_to_cmyk_ai.py")
        cls.step2 = _load("step2_under_test", "step2_apply_pantone_swatches.py")
        cls.batch = _load("batch_update_under_test", "batch_ai_cmyk_update.py")
        for module in (cls.spot, cls.step1, cls.step2, cls.batch):
            module.time.sleep = lambda *args, **kwargs: None
        for module in (cls.step1, cls.step2, cls.batch):
            module.close_all_documents = lambda: None

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._old_argv = sys.argv
        self._old_path = os.environ.get("PATH", "")
        self._old_flag_project = Path("/tmp/flag_project")
        self._flag_existed = self._old_flag_project.exists() or self._old_flag_project.is_symlink()
        if self._flag_existed:
            raise unittest.SkipTest("/tmp/flag_project already exists")

    def tearDown(self):
        sys.argv = self._old_argv
        os.environ["PATH"] = self._old_path
        os.environ.pop("OSASCRIPT_COUNTER", None)
        flag = Path("/tmp/flag_project")
        if not self._flag_existed and (flag.is_symlink() or flag.exists()):
            if flag.is_dir() and not flag.is_symlink():
                shutil.rmtree(flag)
            else:
                flag.unlink()
        for name in ("temp_convert_spot.jsx", "temp_run.jsx", "temp_closeall.jsx"):
            leftover = REPO / name
            if leftover.exists() and not leftover.is_symlink():
                leftover.unlink()
        self._tmp.cleanup()

    def _run(self, module, argv):
        sys.argv = argv
        try:
            module.main()
        except OSError:
            # A non-following open raises instead of writing. The file
            # assertions below decide whether that happened in time.
            return

    def _plant(self, log_name: str, *, dangling: bool = False, regular: bool = False):
        target = self.tmp / "startup-file"
        log = self.tmp / "logs" / log_name
        log.parent.mkdir(parents=True)
        if dangling:
            if target.exists():
                target.unlink()
            log.symlink_to(target)
            return log, target, b""
        target.write_bytes(SENTINEL)
        if regular:
            log.write_bytes(SENTINEL)
        else:
            log.symlink_to(target)
        return log, target, SENTINEL

    def _assert_untouched(self, log: Path, target: Path, original: bytes, *, symlink: bool):
        if original:
            self.assertTrue(target.exists(), "refusing the log must not delete the target file")
            self.assertEqual(target.read_bytes(), original)
        else:
            self.assertFalse(
                target.exists(),
                "opening a dangling progress-log symlink must not create the target",
            )
        if symlink:
            self.assertTrue(log.is_symlink(), "the progress log symlink must still be a symlink")
            self.assertEqual(os.readlink(log), str(target))

    def _install_osascript(self) -> Path:
        bindir = self.tmp / "bin"
        bindir.mkdir()
        script = bindir / "osascript"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import os, re, sys\n"
            "from pathlib import Path\n"
            "text = ' '.join(sys.argv[1:])\n"
            "match = re.search(r'POSIX file \"([^\"]+)\"', text)\n"
            "if not match:\n"
            "    print('ERROR:no-jsx')\n"
            "    sys.exit(1)\n"
            "jsx = Path(match.group(1)).read_text(encoding='utf-8')\n"
            "file_match = re.search(r'var aiFile = new File\\(\"([^\"]*)\"\\);', jsx)\n"
            "if file_match is None or 'convertedCount.toString()' not in jsx:\n"
            "    print('ERROR:jsx')\n"
            "    sys.exit(1)\n"
            "ai_path = Path(file_match.group(1))\n"
            "if not ai_path.is_file():\n"
            "    print('ERROR:missing-ai')\n"
            "    sys.exit(1)\n"
            "counter = os.environ.get('OSASCRIPT_COUNTER')\n"
            "if counter:\n"
            "    path = Path(counter)\n"
            "    previous = int(path.read_text() or '0') if path.exists() else 0\n"
            "    path.write_text(str(previous + 1))\n"
            "print('1')\n"
        )
        script.chmod(0o755)
        os.environ["PATH"] = str(bindir) + os.pathsep + self._old_path
        return self.tmp / "osascript-count"

    def _prepare_spot(self, log: Path, names: list[str]):
        ai_dir = self.tmp / "ai"
        ai_dir.mkdir()
        source = REPO / "04_ai_cmyk" / "AD.ai"
        for name in names:
            shutil.copy(source, ai_dir / f"{name}.ai")
        jsx = self.tmp / "temp_convert_spot.jsx"
        self.spot.AI_DIR = ai_dir
        self.spot.PROGRESS_LOG = log
        self.spot.JSX_PATH = jsx
        self._install_osascript()

    def test_resume_does_not_append_valid_code_through_symlink(self):
        log, target, original = self._plant("spot_to_process_done.txt")
        self._prepare_spot(log, [CODE_PATTERN_SAMPLE])
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_resume_does_not_append_shell_command_filename_through_symlink(self):
        log, target, original = self._plant("spot_to_process_done.txt")
        self._prepare_spot(log, [SHELL_STEM])
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)
        self.assertNotIn(SHELL_STEM.encode(), target.read_bytes())

    def test_codes_mode_does_not_append_through_symlink(self):
        log, target, original = self._plant("spot_to_process_done.txt")
        self._prepare_spot(log, [CODE_PATTERN_SAMPLE])
        self._run(
            self.spot,
            ["convert_spot_to_process.py", "--codes", CODE_PATTERN_SAMPLE],
        )
        self._assert_untouched(log, target, original, symlink=True)

    def test_dangling_symlink_is_not_created_on_resume(self):
        log, target, original = self._plant("spot_to_process_done.txt", dangling=True)
        self._prepare_spot(log, [SHELL_STEM])
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_resume_open_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("spot_to_process_done.txt", regular=True)
        self._prepare_spot(log, [CODE_PATTERN_SAMPLE])
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.spot.open = open_hook
            try:
                self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
            finally:
                self.spot.open = open
        self.assertEqual(target.read_bytes(), original)

    def test_shell_command_filename_is_not_recorded_in_regular_log(self):
        log, _target, _original = self._plant("spot_to_process_done.txt", regular=True)
        self._prepare_spot(log, [SHELL_STEM])
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        text = log.read_text(encoding="utf-8") if log.is_file() else ""
        self.assertNotIn(SHELL_STEM, text)

    def test_valid_code_is_recorded_and_skipped_on_later_resume(self):
        log, _target, _original = self._plant("spot_to_process_done.txt", regular=True)
        log.write_bytes(b"")
        self._prepare_spot(log, [CODE_PATTERN_SAMPLE])
        counter = self.tmp / "osascript-count"
        os.environ["OSASCRIPT_COUNTER"] = str(counter)
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        self.assertTrue(log.is_file(), "a regular progress log has to stay a regular file")
        recorded = {line for line in log.read_text(encoding="utf-8").splitlines() if line}
        self.assertIn(CODE_PATTERN_SAMPLE, recorded)
        self.assertEqual(counter.read_text(encoding="utf-8"), "1")

    def test_underscore_code_is_recorded(self):
        log, _target, _original = self._plant("spot_to_process_done.txt", regular=True)
        log.write_bytes(b"")
        self._prepare_spot(log, [UNDERSCORE_CODE])
        self._run(self.spot, ["convert_spot_to_process.py", "--resume"])
        recorded = {line for line in log.read_text(encoding="utf-8").splitlines() if line}
        self.assertIn(UNDERSCORE_CODE, recorded)

    def _prepare_filename_batch(self, module, log: Path, stem: str, *, kind: str):
        svg_dir = self.tmp / "svg"
        spec_dir = self.tmp / "spec"
        ai_dir = self.tmp / "ai"
        svg_dir.mkdir()
        spec_dir.mkdir()
        ai_dir.mkdir()
        module.AI_OUT_DIR = ai_dir
        module.PROGRESS_LOG = log
        module.SVG_DIR = svg_dir
        module.SPEC_DIR = spec_dir
        if kind == "svg":
            (svg_dir / f"{stem}.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
        elif kind == "spec":
            (spec_dir / f"{stem}.json").write_text("{}")
        else:
            raise AssertionError(kind)

    def test_step1_resume_does_not_append_filename_through_symlink(self):
        log, target, original = self._plant("progress_step1.txt")
        self._prepare_filename_batch(self.step1, log, SHELL_STEM, kind="svg")
        self._run(self.step1, ["step1_convert_svg_to_cmyk_ai.py", "--all", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_step1_resume_does_not_append_valid_code_through_symlink(self):
        log, target, original = self._plant("progress_step1.txt")
        self._prepare_filename_batch(self.step1, log, CODE_PATTERN_SAMPLE, kind="svg")
        self._run(self.step1, ["step1_convert_svg_to_cmyk_ai.py", "--all", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_step1_fresh_run_does_not_truncate_through_symlink(self):
        log, target, original = self._plant("progress_step1.txt")
        self._prepare_filename_batch(self.step1, log, CODE_PATTERN_SAMPLE, kind="svg")
        self._run(self.step1, ["step1_convert_svg_to_cmyk_ai.py", "--all"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_step1_append_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("progress_step1.txt", regular=True)
        self._prepare_filename_batch(self.step1, log, CODE_PATTERN_SAMPLE, kind="svg")
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.step1.open = open_hook
            try:
                self._run(self.step1, ["step1_convert_svg_to_cmyk_ai.py", "--all", "--resume"])
            finally:
                self.step1.open = open
        self.assertEqual(target.read_bytes(), original)

    def test_step1_reset_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("progress_step1.txt", regular=True)
        self._prepare_filename_batch(self.step1, log, CODE_PATTERN_SAMPLE, kind="svg")
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.step1.open = open_hook
            try:
                self._run(self.step1, ["step1_convert_svg_to_cmyk_ai.py", "--all"])
            finally:
                self.step1.open = open
        self.assertEqual(target.read_bytes(), original)

    def test_step2_resume_does_not_append_filename_through_symlink(self):
        log, target, original = self._plant("progress_step2.txt")
        self._prepare_filename_batch(self.step2, log, SHELL_STEM, kind="spec")
        self._run(self.step2, ["step2_apply_pantone_swatches.py", "--all", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_step2_resume_does_not_append_valid_code_through_symlink(self):
        log, target, original = self._plant("progress_step2.txt")
        self._prepare_filename_batch(self.step2, log, CODE_PATTERN_SAMPLE, kind="spec")
        self._run(self.step2, ["step2_apply_pantone_swatches.py", "--all", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_step2_fresh_run_does_not_truncate_through_symlink(self):
        log, target, original = self._plant("progress_step2.txt")
        self._prepare_filename_batch(self.step2, log, CODE_PATTERN_SAMPLE, kind="spec")
        self._run(self.step2, ["step2_apply_pantone_swatches.py", "--all"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_step2_append_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("progress_step2.txt", regular=True)
        self._prepare_filename_batch(self.step2, log, CODE_PATTERN_SAMPLE, kind="spec")
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.step2.open = open_hook
            try:
                self._run(self.step2, ["step2_apply_pantone_swatches.py", "--all", "--resume"])
            finally:
                self.step2.open = open
        self.assertEqual(target.read_bytes(), original)

    def test_step2_reset_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("progress_step2.txt", regular=True)
        self._prepare_filename_batch(self.step2, log, CODE_PATTERN_SAMPLE, kind="spec")
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.step2.open = open_hook
            try:
                self._run(self.step2, ["step2_apply_pantone_swatches.py", "--all"])
            finally:
                self.step2.open = open
        self.assertEqual(target.read_bytes(), original)

    def test_batch_update_resume_does_not_append_filename_through_symlink(self):
        log, target, original = self._plant("progress.txt")
        self._prepare_filename_batch(self.batch, log, SHELL_STEM, kind="svg")
        self._run(self.batch, ["batch_ai_cmyk_update.py", "--all", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_batch_update_resume_does_not_append_valid_code_through_symlink(self):
        log, target, original = self._plant("progress.txt")
        self._prepare_filename_batch(self.batch, log, CODE_PATTERN_SAMPLE, kind="svg")
        self._run(self.batch, ["batch_ai_cmyk_update.py", "--all", "--resume"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_batch_update_fresh_run_does_not_truncate_through_symlink(self):
        log, target, original = self._plant("progress.txt")
        self._prepare_filename_batch(self.batch, log, CODE_PATTERN_SAMPLE, kind="svg")
        self._run(self.batch, ["batch_ai_cmyk_update.py", "--all"])
        self._assert_untouched(log, target, original, symlink=True)

    def test_batch_update_append_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("progress.txt", regular=True)
        self._prepare_filename_batch(self.batch, log, CODE_PATTERN_SAMPLE, kind="svg")
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.batch.open = open_hook
            try:
                self._run(self.batch, ["batch_ai_cmyk_update.py", "--all", "--resume"])
            finally:
                self.batch.open = open
        self.assertEqual(target.read_bytes(), original)

    def test_batch_update_reset_does_not_follow_symlink_swapped_in_after_stat(self):
        log, target, original = self._plant("progress.txt", regular=True)
        self._prepare_filename_batch(self.batch, log, CODE_PATTERN_SAMPLE, kind="svg")
        with swap_log_to_symlink_on_open(log, target) as open_hook:
            self.batch.open = open_hook
            try:
                self._run(self.batch, ["batch_ai_cmyk_update.py", "--all"])
            finally:
                self.batch.open = open
        self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
