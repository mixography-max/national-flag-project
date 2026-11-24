"""Failing tests for the CMYK progress-log symlink write.

The step 1 converter, the step 2 swatch script, and the older batch updater
select a code from a repository filename, then reset and append that code
to a progress log. Those opens follow a symlink. A code is logged on SKIP
when the matching spec or AI file is absent, which is the path a new
verified SVG takes.

These tests call that entrypoint. They fail while the write follows a
symlink or records a code outside a short safe alphabet, and they pass
once both stop. Refusal must not change the symlink target first. A
check that the path is not a symlink, followed by an open that follows
one, still fails: the tests report a regular file to lstat, stat, and
readlink while the kernel open still sees the symlink.

Not covered here, because the append is reached only after Adobe
Illustrator reports success and this environment has no Illustrator:

- scripts/convert_spot_to_process.py mark_done (the non-resume reset
  unlinks the progress path instead of following it)
- ExtendScript File.open of the JSX error logs inside the converters
"""

from __future__ import annotations

import errno
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SAFE_CODE = re.compile(r"^[A-Za-z0-9_]{1,32}$")
PAYLOAD = "echo OWNED_MARKER"
KEY_LINE = "ssh-ed25519 AAAA"
ORIGINAL = b"ORIGINAL LINE\n"

SCRIPTS = (
    {
        "name": "step1",
        "file": "step1_convert_svg_to_cmyk_ai.py",
        "log_name": "progress_step1.txt",
        "plant": "svg",
    },
    {
        "name": "step2",
        "file": "step2_apply_pantone_swatches.py",
        "log_name": "progress_step2.txt",
        "plant": "spec",
    },
    {
        "name": "batch_update",
        "file": "batch_ai_cmyk_update.py",
        "log_name": "progress.txt",
        "plant": "svg",
    },
)


def load_script(filename: str):
    path = REPO / "scripts" / filename
    module_name = f"cmyk_under_test_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The log write happens before this Illustrator cleanup. osascript is
    # not installed here, and the cleanup is not the behavior under test.
    module.close_all_documents = lambda: None
    module.time.sleep = lambda *_args, **_kwargs: None
    return module


def prepare(script: dict, names: list[str], *, link_log: bool):
    tmp = Path(tempfile.mkdtemp(prefix="cmyk-progress-"))
    root = tmp / "proj"
    verified = root / "05_web" / "03_svg_verified"
    specs = root / "02_official_specs"
    logs = root / "04_ai_cmyk" / "logs"
    verified.mkdir(parents=True)
    specs.mkdir(parents=True)
    logs.mkdir(parents=True)
    # The repository stores 03_svg_verified as a symlink to this directory.
    os.symlink(verified, root / "03_svg_verified", target_is_directory=True)
    for name in names:
        if script["plant"] == "svg":
            (verified / f"{name}.svg").write_text(
                "<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8"
            )
        else:
            (specs / f"{name}.json").write_text("{}\n", encoding="utf-8")
    victim = tmp / "startup_file"
    victim.write_bytes(ORIGINAL)
    inode = victim.stat().st_ino
    log = logs / script["log_name"]
    if link_log:
        log.symlink_to(victim)
    else:
        log.write_bytes(b"")
    return tmp, root, log, victim, inode


def bind(module, root: Path, log: Path):
    module.PROJECT_ROOT = root
    module.SVG_DIR = root / "03_svg_verified"
    module.SPEC_DIR = root / "02_official_specs"
    module.AI_OUT_DIR = root / "04_ai_cmyk"
    module.PROGRESS_LOG = log
    module.ASCII_ROOT = root.parent / "ascii_root"


def run_main(module, argv: list[str], *, allow_refusal: bool):
    old_argv = sys.argv
    sys.argv = argv
    try:
        try:
            module.main()
        except Exception:
            if not allow_refusal:
                raise
    finally:
        sys.argv = old_argv


def read_nofollow(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        return os.read(fd, 1_000_000)
    finally:
        os.close(fd)


@contextmanager
def pretend_progress_log_is_regular(progress: Path):
    """Lie to userspace symlink checks for one path.

    lstat, non-following stat, and readlink report a regular file. The
    kernel open of that path is left alone, so O_NOFOLLOW still sees the
    symlink and a later open that follows one still writes the target.
    """
    wanted = os.path.abspath(progress)
    real_stat = os.stat
    real_lstat = os.lstat
    real_readlink = os.readlink

    def same(path) -> bool:
        try:
            return os.path.abspath(os.fspath(path)) == wanted
        except (TypeError, ValueError):
            return False

    def fake_stat(path, *args, follow_symlinks=True, **kwargs):
        if same(path) and not follow_symlinks:
            return real_stat(path, *args, follow_symlinks=True, **kwargs)
        return real_stat(path, *args, follow_symlinks=follow_symlinks, **kwargs)

    def fake_lstat(path, *args, **kwargs):
        if same(path):
            return real_stat(path)
        return real_lstat(path, *args, **kwargs)

    def fake_readlink(path, *args, **kwargs):
        if same(path):
            raise OSError(errno.EINVAL, "Invalid argument")
        return real_readlink(path, *args, **kwargs)

    os.stat = fake_stat
    os.lstat = fake_lstat
    os.readlink = fake_readlink
    try:
        yield
    finally:
        os.stat = real_stat
        os.lstat = real_lstat
        os.readlink = real_readlink


class ProgressLogSymlinkTests(unittest.TestCase):
    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        tmp = getattr(self, "_tmp", None)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
            self._tmp = None

    def _start(self, script: dict, names: list[str], *, link_log: bool):
        self._cleanup()
        tmp, root, log, victim, inode = prepare(script, names, link_log=link_log)
        self._tmp = tmp
        module = load_script(script["file"])
        bind(module, root, log)
        return module, log, victim, inode

    def assert_victim_unchanged(self, victim: Path, inode: int):
        self.assertTrue(victim.is_file())
        self.assertFalse(victim.is_symlink())
        self.assertEqual(victim.stat().st_ino, inode)
        self.assertEqual(read_nofollow(victim), ORIGINAL)

    def assert_log_is_safe(self, log: Path):
        self.assertFalse(log.is_symlink(), "progress log must not be a symlink")
        text = log.read_text(encoding="utf-8") if log.exists() else ""
        self.assertNotIn(PAYLOAD, text)
        self.assertNotIn(KEY_LINE, text)
        for line in text.splitlines():
            self.assertIsNotNone(
                SAFE_CODE.fullmatch(line),
                f"progress log line is outside the safe alphabet: {line!r}",
            )

    def test_default_run_does_not_write_through_progress_symlink(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, _log, victim, inode = self._start(
                    script, [PAYLOAD], link_log=True
                )
                run_main(module, [script["file"]], allow_refusal=True)
                self.assert_victim_unchanged(victim, inode)

    def test_resume_does_not_append_through_progress_symlink(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, _log, victim, inode = self._start(
                    script, [PAYLOAD], link_log=True
                )
                run_main(module, [script["file"], "--resume"], allow_refusal=True)
                self.assert_victim_unchanged(victim, inode)

    def test_safe_code_is_not_written_through_progress_symlink(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, _log, victim, inode = self._start(
                    script, ["ZZ"], link_log=True
                )
                run_main(module, [script["file"]], allow_refusal=True)
                self.assert_victim_unchanged(victim, inode)

    def test_symlink_checks_cannot_be_reused_before_the_open(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, log, victim, inode = self._start(
                    script, [PAYLOAD], link_log=True
                )
                with pretend_progress_log_is_regular(log):
                    run_main(module, [script["file"]], allow_refusal=True)
                self.assert_victim_unchanged(victim, inode)
                self.assertTrue(log.is_symlink())

    def test_resume_symlink_checks_cannot_be_reused_before_the_append(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, log, victim, inode = self._start(
                    script, [PAYLOAD], link_log=True
                )
                with pretend_progress_log_is_regular(log):
                    run_main(
                        module, [script["file"], "--resume"], allow_refusal=True
                    )
                self.assert_victim_unchanged(victim, inode)

    def test_key_shaped_line_is_not_written_through_progress_symlink(self):
        script = SCRIPTS[0]
        module, _log, victim, inode = self._start(
            script, [KEY_LINE], link_log=True
        )
        run_main(module, [script["file"]], allow_refusal=True)
        self.assert_victim_unchanged(victim, inode)
        self.assertNotIn(KEY_LINE.encode(), read_nofollow(victim))

    def test_explicit_code_is_not_written_through_progress_symlink(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, _log, victim, inode = self._start(
                    script, [], link_log=True
                )
                run_main(
                    module,
                    [script["file"], "--codes", PAYLOAD],
                    allow_refusal=True,
                )
                self.assert_victim_unchanged(victim, inode)

    def test_unsafe_filename_is_not_recorded_in_a_regular_progress_log(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, log, _victim, _inode = self._start(
                    script, [PAYLOAD], link_log=False
                )
                run_main(module, [script["file"]], allow_refusal=True)
                self.assert_log_is_safe(log)

    def test_explicit_unsafe_code_is_not_recorded_in_a_regular_progress_log(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                module, log, _victim, _inode = self._start(
                    script, [], link_log=False
                )
                run_main(
                    module,
                    [script["file"], "--codes", PAYLOAD],
                    allow_refusal=True,
                )
                self.assert_log_is_safe(log)

    def test_safe_codes_are_still_recorded_when_spec_or_ai_is_missing(self):
        for script in SCRIPTS:
            with self.subTest(script=script["name"]):
                names = ["PY_reverse", "ZZ"]
                module, log, _victim, _inode = self._start(
                    script, names, link_log=False
                )
                run_main(module, [script["file"]], allow_refusal=False)
                self.assert_log_is_safe(log)
                recorded = {
                    line for line in log.read_text(encoding="utf-8").splitlines() if line
                }
                self.assertTrue(recorded.issuperset(names), recorded)


if __name__ == "__main__":
    unittest.main()
