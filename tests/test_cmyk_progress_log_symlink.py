"""Security tests for CMYK progress-log writes.

The batch updaters reset and append `04_ai_cmyk/logs/*.txt`. That directory is
gitignored, but a symlink placed there (including one force-added to git) is
followed by `Path.write_text` and `open(..., "a")`. A verified SVG or spec
whose stem is a shell command is logged on the skip path, without Illustrator.

These tests exercise that path. They fail while the write follows a symlink,
including when the path is replaced with a symlink after any earlier check and
immediately before the open. They pass once a new run neither modifies the
symlink target nor records a shell-command stem.

    python3 -m unittest tests.test_cmyk_progress_log_symlink -v
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ORIGINAL = b"# maintainer shell startup\nSAFE_LINE=1\n"
SAFE_CODE = "PY_reverse"
UNSAFE_CODE = "echo owned-by-test"
ASCII_ROOT = Path("/tmp/flag_project")

# inotify masks from /usr/include/linux/inotify.h and
# /usr/include/x86_64-linux-gnu/sys/inotify.h on this system.
IN_MODIFY = 0x00000002
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
IN_Q_OVERFLOW = 0x00004000
IN_CLOEXEC = 0o2000000
IN_NONBLOCK = 0o4000
WATCH_MASK = (
    IN_MODIFY
    | IN_CLOSE_WRITE
    | IN_CREATE
    | IN_DELETE
    | IN_DELETE_SELF
    | IN_MOVE_SELF
    | IN_MOVED_FROM
    | IN_MOVED_TO
)

BATCH_CASES = (
    ("batch_ai_cmyk_update.py", "svg", "progress.txt"),
    ("step1_convert_svg_to_cmyk_ai.py", "svg", "progress_step1.txt"),
    ("step2_apply_pantone_swatches.py", "spec", "progress_step2.txt"),
)

RACE_PRELUDE = r"""
import importlib.util
import os
import runpy
import sys
import traceback

progress = os.environ["RACE_PROGRESS"]
victim = os.environ["RACE_VICTIM"]
count_path = os.environ["RACE_COUNT"]
script = sys.argv[1]
sys.argv = [script, *sys.argv[2:]]

swaps = 0
entered = False
progress_norm = os.path.normcase(os.path.abspath(progress))
progress_base = os.path.basename(progress)

def is_write(mode, flags):
    if isinstance(mode, str):
        return any(ch in mode for ch in "wax+")
    if isinstance(flags, int):
        return (flags & os.O_ACCMODE) != os.O_RDONLY
    return False

def hook(event, args):
    global swaps, entered
    if entered or event != "open" or not args:
        return
    try:
        path = os.fsdecode(os.fspath(args[0]))
    except (TypeError, ValueError):
        return
    full = os.path.normcase(os.path.abspath(path))
    relative_leaf = os.path.dirname(path) in ("", ".") and os.path.basename(path) == progress_base
    if full != progress_norm and not relative_leaf:
        return
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if not is_write(mode, flags):
        return
    entered = True
    try:
        if os.path.lexists(progress):
            os.unlink(progress)
        os.symlink(victim, progress)
        swaps += 1
    finally:
        entered = False

sys.addaudithook(hook)
mark_code = os.environ.get("RACE_MARK_DONE")
try:
    if mark_code:
        spec = importlib.util.spec_from_file_location("progress_log_mark_done", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.mark_done(mark_code)
    else:
        runpy.run_path(script, run_name="__main__")
except Exception:
    traceback.print_exc()
finally:
    with open(count_path, "w", encoding="utf-8") as handle:
        handle.write(str(swaps))
"""


def _libc():
    import ctypes
    import ctypes.util

    library = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    library.inotify_init1.argtypes = [ctypes.c_int]
    library.inotify_init1.restype = ctypes.c_int
    library.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    library.inotify_add_watch.restype = ctypes.c_int
    return library


class TargetWatch:
    """Record create/modify/delete events for one filename under a directory."""

    def __init__(self, parent: Path, name: str):
        if not sys.platform.startswith("linux"):
            raise unittest.SkipTest("inotify side-effect watch is Linux-specific")
        self.name = name
        self._fd = _libc().inotify_init1(IN_CLOEXEC | IN_NONBLOCK)
        if self._fd < 0:
            error = ctypes_errno()
            raise OSError(error, "inotify_init1")
        watch = _libc().inotify_add_watch(self._fd, os.fsencode(parent), WATCH_MASK)
        if watch < 0:
            os.close(self._fd)
            raise OSError(ctypes_errno(), "inotify_add_watch")

    def collect(self) -> list[tuple[int, str]]:
        events = []
        while True:
            try:
                data = os.read(self._fd, 8192)
            except BlockingIOError:
                break
            if not data:
                break
            index = 0
            while index + 16 <= len(data):
                _wd, mask, _cookie, length = struct.unpack_from("iIII", data, index)
                raw_name = data[index + 16 : index + 16 + length].split(b"\x00", 1)[0]
                events.append((mask, raw_name.decode("utf-8", "surrogateescape")))
                index += 16 + length
        return events

    def close(self) -> None:
        os.close(self._fd)


def ctypes_errno() -> int:
    import ctypes

    return ctypes.get_errno()


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"git {args!r} exited {result.returncode}\n{result.stdout}\n{result.stderr}"
        )
    return result


def clean_ascii_root() -> None:
    if ASCII_ROOT.is_symlink() or (ASCII_ROOT.exists() and not ASCII_ROOT.is_dir()):
        ASCII_ROOT.unlink()


def write_input(project: Path, kind: str, stem: str) -> None:
    if kind == "svg":
        directory = project / "03_svg_verified"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{stem}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>',
            encoding="utf-8",
        )
        (project / "02_official_specs").mkdir(parents=True, exist_ok=True)
    elif kind == "spec":
        directory = project / "02_official_specs"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{stem}.json").write_text("{}", encoding="utf-8")
    else:
        raise AssertionError(kind)


def prepare_project(root: Path, script_name: str, kind: str, stem: str) -> tuple[Path, Path]:
    project = root / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(REPO / "scripts" / script_name, scripts / script_name)
    logs = project / "04_ai_cmyk" / "logs"
    logs.mkdir(parents=True)
    write_input(project, kind, stem)
    progress_name = dict((name, progress) for name, _kind, progress in BATCH_CASES)[script_name]
    return project, logs / progress_name


def run_script(
    project: Path,
    script_name: str,
    args: list[str],
    *,
    race_progress: Path | None = None,
    race_victim: Path | None = None,
    race_count: Path | None = None,
    mark_done_code: str | None = None,
) -> subprocess.CompletedProcess[str]:
    script = project / "scripts" / script_name
    clean_ascii_root()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    command = [sys.executable, str(script), *args]
    if race_progress is not None:
        env["RACE_PROGRESS"] = str(race_progress)
        env["RACE_VICTIM"] = str(race_victim)
        env["RACE_COUNT"] = str(race_count)
        if mark_done_code is not None:
            env["RACE_MARK_DONE"] = mark_done_code
        command = [sys.executable, "-c", RACE_PRELUDE, str(script), *args]
    try:
        return subprocess.run(
            command,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        clean_ascii_root()


def load_script(path: Path):
    name = "progress_log_under_test_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ProgressLogSymlinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def tearDown(self) -> None:
        clean_ascii_root()

    def assert_outside_file_untouched(
        self,
        watch: TargetWatch,
        victim: Path,
        original: bytes | None,
        result: subprocess.CompletedProcess[str] | None = None,
    ) -> None:
        events = [
            (mask, name)
            for mask, name in watch.collect()
            if name == victim.name or mask & IN_Q_OVERFLOW
        ]
        detail = f"inotify={events!r}"
        if result is not None:
            detail += f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        self.assertEqual(events, [], detail)
        if original is None:
            self.assertFalse(victim.exists(), detail)
        else:
            self.assertEqual(victim.read_bytes(), original, detail)

    def test_checked_out_force_added_symlink_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            victim_dir = root / "outside"
            victim_dir.mkdir()
            victim = victim_dir / "shell_startup"
            victim.write_bytes(ORIGINAL)
            repo = root / "attacker"
            repo.mkdir()
            git(repo, "init")
            shutil.copy2(REPO / ".gitignore", repo / ".gitignore")
            self.assertIn("04_ai_cmyk/logs/", (repo / ".gitignore").read_text(encoding="utf-8"))
            shutil.copytree(REPO / "scripts", repo / "scripts")
            # The copy includes every script. Only the updater is invoked below.
            write_input(repo, "svg", UNSAFE_CODE)
            link = repo / "04_ai_cmyk" / "logs" / "progress.txt"
            link.parent.mkdir(parents=True)
            link.symlink_to(victim)
            relative = "04_ai_cmyk/logs/progress.txt"
            ignored = git(repo, "check-ignore", "-q", "--", relative, check=False)
            self.assertEqual(ignored.returncode, 0, ignored.stderr)
            plain_add = git(repo, "add", "--", relative, check=False)
            staged = git(repo, "diff", "--cached", "--name-only").stdout.splitlines()
            self.assertNotIn(relative, staged, plain_add.stderr)
            git(repo, "add", "-f", "--", relative)
            git(repo, "add", "--", ".gitignore", "scripts/batch_ai_cmyk_update.py", "03_svg_verified")
            listed = git(repo, "ls-files", "-s", "--", relative).stdout
            self.assertIn("120000", listed)
            git(
                repo,
                "-c",
                "user.email=progress-log-test@example.com",
                "-c",
                "user.name=progress-log-test",
                "commit",
                "-m",
                "add ignored progress symlink",
            )
            blob = git(repo, "cat-file", "-p", f"HEAD:{relative}").stdout
            self.assertEqual(blob.strip(), str(victim))
            clone = root / "maintainer"
            cloned = subprocess.run(
                ["git", "clone", "--quiet", str(repo), str(clone)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(cloned.returncode, 0, cloned.stderr)
            cloned_link = clone / relative
            self.assertTrue(cloned_link.is_symlink(), cloned_link)
            self.assertEqual(os.readlink(cloned_link), str(victim))
            watch = TargetWatch(victim_dir, victim.name)
            try:
                result = run_script(clone, "batch_ai_cmyk_update.py", [])
                self.assertIn("Mode:", result.stdout, result.stderr)
                self.assert_outside_file_untouched(watch, victim, ORIGINAL, result)
            finally:
                watch.close()

    def _run_case(
        self,
        script_name: str,
        kind: str,
        progress_name: str,
        stem: str,
        args: list[str],
        *,
        link: str,
        race: bool,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            victim_dir = root / "outside"
            victim_dir.mkdir()
            victim = victim_dir / "shell_startup"
            original: bytes | None
            if link == "dangling":
                original = None
            else:
                victim.write_bytes(ORIGINAL)
                original = ORIGINAL
            project, progress = prepare_project(root, script_name, kind, stem)
            self.assertEqual(progress.name, progress_name)
            if link == "present":
                progress.symlink_to(victim)
            elif link == "dangling":
                progress.symlink_to(victim)
            elif link == "regular":
                progress.write_text("OTHER\n", encoding="utf-8")
            else:
                raise AssertionError(link)
            watch = TargetWatch(victim_dir, victim.name)
            try:
                if race:
                    count = root / "swaps.txt"
                    result = run_script(
                        project,
                        script_name,
                        args,
                        race_progress=progress,
                        race_victim=victim,
                        race_count=count,
                    )
                    swaps = int(count.read_text(encoding="utf-8")) if count.exists() else 0
                    self.assertGreaterEqual(swaps, 1, f"{result.stdout}\n{result.stderr}")
                else:
                    result = run_script(project, script_name, args)
                self.assertIn("Mode:", result.stdout, result.stderr)
                if args == ["--resume"]:
                    self.assertIn("[1/1]", result.stdout, result.stderr)
                self.assert_outside_file_untouched(watch, victim, original, result)
            finally:
                watch.close()

    def test_new_run_does_not_touch_symlink_target(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            for stem in (SAFE_CODE, UNSAFE_CODE):
                with self.subTest(script=script_name, stem=stem):
                    self._run_case(
                        script_name,
                        kind,
                        progress_name,
                        stem,
                        [],
                        link="present",
                        race=False,
                    )

    def test_resume_does_not_append_through_symlink(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            with self.subTest(script=script_name):
                self._run_case(
                    script_name,
                    kind,
                    progress_name,
                    SAFE_CODE,
                    ["--resume"],
                    link="present",
                    race=False,
                )

    def test_dangling_progress_symlink_creates_nothing(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            with self.subTest(script=script_name):
                self._run_case(
                    script_name,
                    kind,
                    progress_name,
                    SAFE_CODE,
                    [],
                    link="dangling",
                    race=False,
                )

    def test_open_does_not_follow_symlink_swapped_in_at_open(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            with self.subTest(script=script_name):
                self._run_case(
                    script_name,
                    kind,
                    progress_name,
                    SAFE_CODE,
                    [],
                    link="regular",
                    race=True,
                )

    def test_resume_append_does_not_follow_symlink_swapped_in_at_open(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            with self.subTest(script=script_name):
                self._run_case(
                    script_name,
                    kind,
                    progress_name,
                    SAFE_CODE,
                    ["--resume"],
                    link="regular",
                    race=True,
                )

    def test_regular_progress_log_records_safe_code(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            with self.subTest(script=script_name):
                with tempfile.TemporaryDirectory() as raw:
                    project, progress = prepare_project(Path(raw), script_name, kind, SAFE_CODE)
                    result = run_script(project, script_name, [])
                    self.assertIn("Mode:", result.stdout, result.stderr)
                    self.assertEqual(
                        progress.read_text(encoding="utf-8"),
                        SAFE_CODE + "\n",
                        f"{result.stdout}\n{result.stderr}",
                    )

    def test_regular_progress_log_does_not_record_shell_stem(self) -> None:
        for script_name, kind, progress_name in BATCH_CASES:
            with self.subTest(script=script_name):
                with tempfile.TemporaryDirectory() as raw:
                    project, progress = prepare_project(Path(raw), script_name, kind, UNSAFE_CODE)
                    result = run_script(project, script_name, [])
                    self.assertIn("Mode:", result.stdout, result.stderr)
                    recorded = progress.read_text(encoding="utf-8") if progress.exists() and not progress.is_symlink() else ""
                    self.assertNotIn(UNSAFE_CODE, recorded, f"{result.stdout}\n{result.stderr}")

    def test_convert_spot_mark_done_does_not_follow_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            victim_dir = root / "outside"
            victim_dir.mkdir()
            victim = victim_dir / "shell_startup"
            victim.write_bytes(ORIGINAL)
            project = root / "project"
            scripts = project / "scripts"
            scripts.mkdir(parents=True)
            script = scripts / "convert_spot_to_process.py"
            shutil.copy2(REPO / "scripts" / "convert_spot_to_process.py", script)
            progress = project / "04_ai_cmyk" / "logs" / "spot_to_process_done.txt"
            progress.parent.mkdir(parents=True)
            progress.symlink_to(victim)
            watch = TargetWatch(victim_dir, victim.name)
            try:
                module = load_script(script)
                raised = False
                try:
                    module.mark_done(SAFE_CODE)
                except Exception:
                    raised = True
                still_linked = progress.is_symlink() and os.path.realpath(progress) == str(victim.resolve())
                self.assertFalse(
                    still_linked and not raised,
                    "mark_done followed or ignored the progress symlink",
                )
                self.assert_outside_file_untouched(watch, victim, ORIGINAL)
            finally:
                watch.close()

    def test_convert_spot_mark_done_does_not_follow_symlink_swapped_in_at_open(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            victim_dir = root / "outside"
            victim_dir.mkdir()
            victim = victim_dir / "shell_startup"
            victim.write_bytes(ORIGINAL)
            project = root / "project"
            scripts = project / "scripts"
            scripts.mkdir(parents=True)
            script_name = "convert_spot_to_process.py"
            shutil.copy2(REPO / "scripts" / script_name, scripts / script_name)
            progress = project / "04_ai_cmyk" / "logs" / "spot_to_process_done.txt"
            progress.parent.mkdir(parents=True)
            progress.write_text("OTHER\n", encoding="utf-8")
            count = root / "swaps.txt"
            watch = TargetWatch(victim_dir, victim.name)
            try:
                result = run_script(
                    project,
                    script_name,
                    [],
                    race_progress=progress,
                    race_victim=victim,
                    race_count=count,
                    mark_done_code=SAFE_CODE,
                )
                swaps = int(count.read_text(encoding="utf-8")) if count.exists() else 0
                self.assertGreaterEqual(swaps, 1, f"{result.stdout}\n{result.stderr}")
                self.assert_outside_file_untouched(watch, victim, ORIGINAL, result)
            finally:
                watch.close()

    def test_convert_spot_mark_done_does_not_record_shell_stem(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            project = root / "project"
            scripts = project / "scripts"
            scripts.mkdir(parents=True)
            script = scripts / "convert_spot_to_process.py"
            shutil.copy2(REPO / "scripts" / "convert_spot_to_process.py", script)
            progress = project / "04_ai_cmyk" / "logs" / "spot_to_process_done.txt"
            progress.parent.mkdir(parents=True)
            progress.write_text("KEEP\n", encoding="utf-8")
            module = load_script(script)
            try:
                module.mark_done(UNSAFE_CODE)
            except Exception:
                pass
            recorded = ""
            if progress.exists() and not progress.is_symlink():
                recorded = progress.read_text(encoding="utf-8")
            self.assertNotIn(UNSAFE_CODE, recorded)


if __name__ == "__main__":
    unittest.main()
