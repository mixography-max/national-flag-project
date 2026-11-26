"""Failing tests for symlinked progress-log and temp-JSX writes.

These tests are expected to fail until the batch scripts stop following
symlinks when they reset or append those paths, and until country codes
taken from repository filenames are constrained to the codes this project
actually uses.

Run them from the repository root:

    python3 -m unittest discover -s tests -v

What a fix has to satisfy
-------------------------
The victim file is created first and its bytes and inode are recorded.
The script is then run with a progress log, ``temp_closeall.jsx``,
``temp_run.jsx``, or ``temp_convert_spot.jsx`` that is a symlink to that
file. The run must leave the victim bytes, the victim inode, and the
symlink itself in place. Deleting the symlink, replacing it, truncating
the victim, or appending to the victim is a failure even if the script
exits afterwards.

Several tests lie to ``os.lstat`` and to ``os.stat(..., follow_symlinks=False)``
about that symlink, so a check that runs before ``open`` still sees a
regular file. Re-checking the path between the check and the write does
not pass. The write itself has to refuse to follow the symlink (for
example ``os.open`` with ``os.O_NOFOLLOW``, including when the file is
created or appended). The same lie is installed before the script module
is imported, so a name bound with ``from os import lstat`` is covered too.

Logged codes have to be exactly the safe names ``AD`` and ``PY_reverse``.
Those match the real stems in this tree (two uppercase letters, or those
letters plus an underscore and an alphanumeric suffix, as in
``PY_reverse``, ``CR_state``, ``PE_state``, and ``PH_war``). A spec, SVG,
or AI stem that is a shell command must not be written into the log.

Not covered here
----------------
- A symlink in a parent directory of the log, rather than at the log path.
- Writes performed by Adobe Illustrator itself. ``osascript`` is not
  installed in this environment, and the generated JSX error logs are
  written from that process.
- ``convert_spot_to_process.py`` reaching ``mark_done`` from ``main``:
  that call sits after a successful Illustrator run. ``mark_done`` is
  invoked directly. ``main`` is still run for the JSX overwrite and for
  the fresh-run ``unlink`` of the progress log.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import posix
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ORIGINAL = b"export KEEP_ORIGINAL=1\n"
SHELL_CODE = "echo INJECTED_MARKER"
SNEAKY_CODE = "AD$(echo INJECTED_MARKER)"
SAFE_CODES = {"AD", "PY_reverse"}
ASCII_ROOT = Path("/tmp/flag_project")
GITIGNORE = "04_ai_cmyk/logs/\ntemp_*.jsx\n"
SVG = "<svg xmlns=\"http://www.w3.org/2000/svg\"/>\n"
SPEC = "{\"colors\": []}\n"


def _reset_ascii_root() -> None:
    if ASCII_ROOT.is_symlink():
        ASCII_ROOT.unlink()
    elif ASCII_ROOT.is_dir():
        shutil.rmtree(ASCII_ROOT)
    elif ASCII_ROOT.exists():
        ASCII_ROOT.unlink()


def _write_files(root: Path, files: list[tuple[str, str]]) -> None:
    for rel, content in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


@contextlib.contextmanager
def _hide_symlink_from_lstat(link: Path):
    """Report ``link`` as a regular file to lstat-style lookups.

    ``open`` is left untouched, so a later open of the same path still
    follows the real symlink unless the caller passes O_NOFOLLOW (or
    otherwise opens the descriptor without following it).
    """
    real_stat = os.stat
    real_lstat = os.lstat
    decoy_path = Path(tempfile.mkstemp(prefix="decoy-not-a-link-")[1])
    decoy_stat = real_stat(decoy_path)
    target = os.path.abspath(link)

    def same(path) -> bool:
        try:
            return os.path.abspath(os.fspath(path)) == target
        except (TypeError, ValueError):
            return False

    def fake_stat(path, *args, follow_symlinks=True, **kwargs):
        if same(path) and not follow_symlinks:
            return decoy_stat
        return real_stat(path, *args, follow_symlinks=follow_symlinks, **kwargs)

    def fake_lstat(path, *args, **kwargs):
        if same(path):
            return decoy_stat
        return real_lstat(path, *args, **kwargs)

    os.stat = posix.stat = fake_stat
    os.lstat = posix.lstat = fake_lstat
    try:
        if stat.S_ISLNK(real_lstat(link).st_mode) is not True:
            raise AssertionError(f"{link} is not a symlink under the real lstat")
        yield
    finally:
        os.stat = posix.stat = real_stat
        os.lstat = posix.lstat = real_lstat
        decoy_path.unlink(missing_ok=True)


class ProgressLogSymlinkTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="flag-progress-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.addCleanup(_reset_ascii_root)
        _reset_ascii_root()

    def _git(self, cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            self.fail(f"git {' '.join(args)} failed\n{proc.stdout}\n{proc.stderr}")
        return proc

    def _victim(self) -> tuple[Path, int]:
        sentinel = self.tmp / "home" / ".zshrc"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(ORIGINAL)
        return sentinel, sentinel.stat().st_ino

    def _assert_preserved(self, sentinel: Path, inode: int, link: Path, detail: str = "") -> None:
        message = detail[-4000:]
        self.assertTrue(sentinel.is_file(), message)
        self.assertFalse(sentinel.is_symlink(), message)
        self.assertEqual(sentinel.stat().st_ino, inode, message)
        self.assertEqual(sentinel.read_bytes(), ORIGINAL, message)
        self.assertTrue(link.is_symlink(), message)
        self.assertEqual(os.readlink(link), str(sentinel), message)

    def _stage_copy(self, script: str, files: list[tuple[str, str]]) -> Path:
        project = self.tmp / "project"
        script_dir = project / "scripts"
        script_dir.mkdir(parents=True)
        shutil.copy(REPO / "scripts" / script, script_dir / script)
        _write_files(project, files)
        return project

    def _plant(self, project: Path, rel: str, sentinel: Path) -> Path:
        link = project / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(sentinel)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(sentinel))
        return link

    def _git_deliver(
        self,
        script: str,
        files: list[tuple[str, str]],
        symlink_rel: str,
        sentinel: Path,
    ) -> tuple[Path, Path]:
        origin = self.tmp / "origin"
        maint = self.tmp / "maintainer"
        origin.mkdir()
        self._git(origin, ["init", "-b", "main"])
        self._git(origin, ["config", "user.email", "tester@example.com"])
        self._git(origin, ["config", "user.name", "Tester"])
        self._git(origin, ["config", "commit.gpgsign", "false"])
        self._git(origin, ["config", "core.symlinks", "true"])
        (origin / "scripts").mkdir()
        shutil.copy(REPO / "scripts" / script, origin / "scripts" / script)
        (origin / ".gitignore").write_text(GITIGNORE)
        self._git(origin, ["add", ".gitignore", f"scripts/{script}"])
        self._git(origin, ["commit", "-m", "base"])
        cloned = subprocess.run(
            ["git", "clone", str(origin), str(maint)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(cloned.returncode, 0, cloned.stderr)
        self._git(maint, ["config", "core.symlinks", "true"])

        _write_files(origin, files)
        link = origin / symlink_rel
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(sentinel)
        ignored = subprocess.run(
            ["git", "-C", str(origin), "check-ignore", "-q", symlink_rel],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            ignored.returncode,
            0,
            f"{symlink_rel} is not ignored by the repository gitignore",
        )
        self._git(origin, ["add", "-f", symlink_rel, *[rel for rel, _content in files]])
        listed = self._git(origin, ["ls-files", "-s", symlink_rel]).stdout
        self.assertTrue(
            listed.startswith("120000 "),
            f"git did not store {symlink_rel} as a symlink: {listed!r}",
        )
        self._git(origin, ["commit", "-m", "add symlink"])
        self._git(maint, ["pull", "--ff-only"])
        pulled = maint / symlink_rel
        self.assertTrue(pulled.is_symlink(), "git pull did not materialize the symlink")
        self.assertEqual(os.readlink(pulled), str(sentinel))
        return maint, pulled

    def _run_subprocess(self, project: Path, script: str, args: list[str]) -> subprocess.CompletedProcess:
        _reset_ascii_root()
        return subprocess.run(
            [sys.executable, str(project / "scripts" / script), *args],
            cwd=project,
            capture_output=True,
            text=True,
        )

    def _run_main(self, project: Path, script: str, args: list[str], hide: Path | None) -> str:
        _reset_ascii_root()
        script_path = project / "scripts" / script
        module_name = f"progress_under_test_{script.replace('.', '_')}_{id(project)}"
        old_argv = sys.argv
        sys.argv = [str(script_path), *args]
        output = io.StringIO()

        def invoke() -> None:
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    module.main()
            except BaseException:
                pass
            finally:
                sys.modules.pop(module_name, None)

        try:
            if hide is None:
                invoke()
            else:
                with _hide_symlink_from_lstat(hide):
                    if Path(hide).is_symlink():
                        self.fail("lstat hook did not hide the symlink from Path.is_symlink")
                    if stat.S_ISLNK(os.lstat(hide).st_mode):
                        self.fail("lstat hook did not hide the symlink from os.lstat")
                    invoke()
        finally:
            sys.argv = old_argv
            _reset_ascii_root()
        return output.getvalue()

    def test_convert_spot_jsx_write_does_not_follow_symlink_when_lstat_is_stale(self):
        sentinel, inode = self._victim()
        project = self._stage_copy(SPOT, [("04_ai_cmyk/AD.ai", "not-an-ai")])
        link = self._plant(project, "temp_convert_spot.jsx", sentinel)
        detail = self._run_main(project, SPOT, [], hide=link)
        self._assert_preserved(sentinel, inode, link, detail)

    def test_convert_spot_fresh_run_does_not_unlink_progress_symlink(self):
        sentinel, inode = self._victim()
        project = self._stage_copy(SPOT, [("04_ai_cmyk/AD.ai", "not-an-ai")])
        link = self._plant(project, SPOT_LOG, sentinel)
        detail = self._run_main(project, SPOT, [], hide=link)
        self._assert_preserved(sentinel, inode, link, detail)

    def test_convert_spot_mark_done_does_not_append_through_symlink_when_lstat_is_stale(self):
        sentinel, inode = self._victim()
        project = self._stage_copy(SPOT, [])
        link = self._plant(project, SPOT_LOG, sentinel)

        def call(module):
            module.mark_done(SHELL_CODE)

        self._run_loaded(project, SPOT, link, call)
        self._assert_preserved(sentinel, inode, link)

    def _run_loaded(self, project: Path, script: str, hide: Path, call) -> None:
        """Import ``script`` while ``hide`` is concealed and call ``call(module)``."""
        script_path = project / "scripts" / script
        module_name = f"progress_loaded_{script.replace('.', '_')}_{id(project)}"
        with _hide_symlink_from_lstat(hide):
            if Path(hide).is_symlink() or stat.S_ISLNK(os.lstat(hide).st_mode):
                self.fail("lstat hook did not hide the symlink")
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                try:
                    call(module)
                except BaseException:
                    pass
            finally:
                sys.modules.pop(module_name, None)

    def _attack_via_pull(self, script: str, log_rel: str, files: list[tuple[str, str]], args: list[str]) -> None:
        sentinel, inode = self._victim()
        project, link = self._git_deliver(script, files, log_rel, sentinel)
        proc = self._run_subprocess(project, script, args)
        detail = f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        self._assert_preserved(sentinel, inode, link, detail)

    def _attack_with_stale_lstat(
        self,
        script: str,
        link_rel: str,
        files: list[tuple[str, str]],
        args: list[str],
    ) -> None:
        sentinel, inode = self._victim()
        project = self._stage_copy(script, files)
        link = self._plant(project, link_rel, sentinel)
        detail = self._run_main(project, script, args, hide=link)
        self._assert_preserved(sentinel, inode, link, detail)


STEP2 = "step2_apply_pantone_swatches.py"
STEP1 = "step1_convert_svg_to_cmyk_ai.py"
BATCH = "batch_ai_cmyk_update.py"
SPOT = "convert_spot_to_process.py"
STEP2_LOG = "04_ai_cmyk/logs/progress_step2.txt"
STEP1_LOG = "04_ai_cmyk/logs/progress_step1.txt"
BATCH_LOG = "04_ai_cmyk/logs/progress.txt"
SPOT_LOG = "04_ai_cmyk/logs/spot_to_process_done.txt"

STEP2_ATTACK = [
    ("02_official_specs/AD.json", SPEC),
    (f"02_official_specs/{SHELL_CODE}.json", SPEC),
]
STEP1_ATTACK = [
    ("03_svg_verified/AD.svg", SVG),
    (f"03_svg_verified/{SHELL_CODE}.svg", SVG),
]
BATCH_ATTACK = STEP1_ATTACK

DOCUMENTED_RUNS = [
    ("step2", STEP2, STEP2_LOG, STEP2_ATTACK, ["--all"]),
    ("step2", STEP2, STEP2_LOG, STEP2_ATTACK, []),
    ("step1", STEP1, STEP1_LOG, STEP1_ATTACK, ["--all"]),
    ("step1", STEP1, STEP1_LOG, STEP1_ATTACK, []),
    ("batch", BATCH, BATCH_LOG, BATCH_ATTACK, ["--all"]),
    ("batch", BATCH, BATCH_LOG, BATCH_ATTACK, []),
]

STALE_LOG_RUNS = [
    ("step2_all", STEP2, STEP2_LOG, STEP2_ATTACK, ["--all"]),
    ("step2_default", STEP2, STEP2_LOG, STEP2_ATTACK, []),
    ("step2_resume", STEP2, STEP2_LOG, STEP2_ATTACK, ["--resume"]),
    ("step2_empty", STEP2, STEP2_LOG, [], ["--all"]),
    ("step1_all", STEP1, STEP1_LOG, STEP1_ATTACK, ["--all"]),
    ("step1_default", STEP1, STEP1_LOG, STEP1_ATTACK, []),
    ("step1_resume", STEP1, STEP1_LOG, STEP1_ATTACK, ["--resume"]),
    ("step1_empty", STEP1, STEP1_LOG, [], ["--all"]),
    ("batch_all", BATCH, BATCH_LOG, BATCH_ATTACK, ["--all"]),
    ("batch_default", BATCH, BATCH_LOG, BATCH_ATTACK, []),
    ("batch_resume", BATCH, BATCH_LOG, BATCH_ATTACK, ["--resume"]),
    ("batch_empty", BATCH, BATCH_LOG, [], ["--all"]),
]

CLOSEALL_RUNS = [
    ("step2", STEP2, [("02_official_specs/AD.json", SPEC)]),
    ("step1", STEP1, [("03_svg_verified/AD.svg", SVG)]),
    ("batch", BATCH, [("03_svg_verified/AD.svg", SVG)]),
]

TEMP_RUN_FILES = {
    STEP2: [
        ("02_official_specs/AD.json", SPEC),
        ("04_ai_cmyk/AD.ai", "not-an-ai"),
    ],
    STEP1: [
        ("03_svg_verified/AD.svg", SVG),
        ("02_official_specs/AD.json", SPEC),
    ],
    BATCH: [
        ("03_svg_verified/AD.svg", SVG),
        ("02_official_specs/AD.json", SPEC),
    ],
}

VALIDATION_FILES = {
    STEP2: [
        ("02_official_specs/AD.json", SPEC),
        ("02_official_specs/PY_reverse.json", SPEC),
        (f"02_official_specs/{SHELL_CODE}.json", SPEC),
        (f"02_official_specs/{SNEAKY_CODE}.json", SPEC),
    ],
    STEP1: [
        ("03_svg_verified/AD.svg", SVG),
        ("03_svg_verified/PY_reverse.svg", SVG),
        (f"03_svg_verified/{SHELL_CODE}.svg", SVG),
        (f"03_svg_verified/{SNEAKY_CODE}.svg", SVG),
    ],
    BATCH: [
        ("03_svg_verified/AD.svg", SVG),
        ("03_svg_verified/PY_reverse.svg", SVG),
        (f"03_svg_verified/{SHELL_CODE}.svg", SVG),
        (f"03_svg_verified/{SNEAKY_CODE}.svg", SVG),
    ],
}

VALIDATION_LOGS = {
    STEP2: STEP2_LOG,
    STEP1: STEP1_LOG,
    BATCH: BATCH_LOG,
}


def _bind_documented_runs() -> None:
    for key, script, log_rel, files, args in DOCUMENTED_RUNS:
        mode = "all" if args == ["--all"] else "default"

        def test(self, script=script, log_rel=log_rel, files=files, args=args):
            self._attack_via_pull(script, log_rel, files, args)

        test.__name__ = f"test_{key}_{mode}_pull_does_not_write_symlink_target"
        setattr(ProgressLogSymlinkTests, test.__name__, test)


def _bind_stale_lstat_runs() -> None:
    for key, script, log_rel, files, args in STALE_LOG_RUNS:

        def test(self, script=script, log_rel=log_rel, files=files, args=args):
            self._attack_with_stale_lstat(script, log_rel, files, args)

        test.__name__ = f"test_{key}_stale_lstat_does_not_write_progress_log"
        setattr(ProgressLogSymlinkTests, test.__name__, test)


def _bind_closeall_runs() -> None:
    for key, script, files in CLOSEALL_RUNS:

        def test(self, script=script, files=files):
            self._attack_with_stale_lstat(script, "temp_closeall.jsx", files, ["--all"])

        test.__name__ = f"test_{key}_stale_lstat_does_not_write_temp_closeall"
        setattr(ProgressLogSymlinkTests, test.__name__, test)


def _bind_temp_run_cases() -> None:
    for script, files in TEMP_RUN_FILES.items():
        key = script.split("_", 1)[0]

        def test(self, script=script, files=files):
            self._attack_with_stale_lstat(script, "temp_run.jsx", files, ["--all"])

        test.__name__ = f"test_{key}_stale_lstat_does_not_write_temp_run"
        setattr(ProgressLogSymlinkTests, test.__name__, test)


def _bind_validation_cases() -> None:
    for script, files in VALIDATION_FILES.items():
        key = script.split("_", 1)[0]
        log_rel = VALIDATION_LOGS[script]

        def test(self, script=script, files=files, log_rel=log_rel):
            project = self._stage_copy(script, files)
            detail = self._run_main(project, script, ["--all"], hide=None)
            log = project / log_rel
            self.assertTrue(log.is_file(), detail)
            self.assertFalse(log.is_symlink(), detail)
            lines = [line for line in log.read_text().splitlines() if line]
            self.assertEqual(set(lines), SAFE_CODES, detail)
            for line in lines:
                self.assertRegex(line, r"^[A-Z]{2}(?:_[A-Za-z0-9]+)?$", detail)

        test.__name__ = f"test_{key}_log_keeps_only_country_codes"
        setattr(ProgressLogSymlinkTests, test.__name__, test)


_bind_documented_runs()
_bind_stale_lstat_runs()
_bind_closeall_runs()
_bind_temp_run_cases()
_bind_validation_cases()


if __name__ == "__main__":
    unittest.main()
