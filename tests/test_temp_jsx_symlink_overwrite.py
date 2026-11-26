"""Symlink-safe writes for generated Illustrator scripts.

These tests fail while the vulnerability is present. A fixed writer creates
its script without following a pre-existing symlink, so the target file
outside the repository keeps its original bytes and inode.

`scripts/batch_ai_cmyk.py` is not covered. That module raises SyntaxError
at the unterminated string on line 89, so its `temp_run.jsx` write never runs.
The every-five-files call in step1 and step2 is the same `close_all_documents`
function covered below.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SENTINEL = b"ORIGINAL_SENTINEL_CONTENT\n"


def load_script(relative_path):
    path = REPO / relative_path
    spec = importlib.util.spec_from_file_location(
        "under_test_" + path.stem, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TempJsxSymlinkOverwriteTests(unittest.TestCase):
    def setUp(self):
        self._workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self._workspace.cleanup)
        self.victim = Path(self._workspace.name) / "maintainer_file"
        self.victim.write_bytes(SENTINEL)
        self.victim_inode = self.victim.stat().st_ino

    def plant(self, name):
        link = REPO / name
        if os.path.lexists(link):
            self.fail(f"refusing to replace existing path {link}")
        # Absolute target, the same shape as a symlink checked out into the repo root.
        link.symlink_to(self.victim)
        self.addCleanup(lambda path=link: path.unlink(missing_ok=True))
        return link

    def assert_target_preserved(self, operation):
        self.assertTrue(
            self.victim.exists(),
            f"{operation} removed the symlink target",
        )
        self.assertEqual(
            self.victim.stat().st_ino,
            self.victim_inode,
            f"{operation} replaced the symlink target",
        )
        self.assertEqual(
            self.victim.read_bytes(),
            SENTINEL,
            f"{operation} followed the symlink and overwrote the target",
        )

    def call_writer(self, func):
        try:
            return func()
        except FileNotFoundError as exc:
            # The destructive open happens before osascript. This environment
            # has no osascript, which a fixed writer still invokes afterward.
            if "osascript" not in str(exc):
                raise
            return None

    def preserve_file(self, path):
        existed = path.exists() and not path.is_symlink()
        previous = path.read_bytes() if existed else None

        def restore():
            if previous is None:
                if path.is_symlink() or path.is_file():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(previous)

        self.addCleanup(restore)

    def preserve_flag_project_link(self):
        link = Path("/tmp/flag_project")
        was_link = link.is_symlink()
        target = Path(link).readlink() if was_link else None

        def restore():
            if link.is_symlink() or link.is_file():
                link.unlink()
            if was_link:
                link.symlink_to(target)

        self.addCleanup(restore)

    def run_script(self, relative_path, *args):
        return subprocess.run(
            [sys.executable, str(REPO / relative_path), *args],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_step2_close_all_documents_does_not_follow_symlink(self):
        self.plant("temp_closeall.jsx")
        module = load_script("scripts/step2_apply_pantone_swatches.py")
        self.call_writer(module.close_all_documents)
        self.assert_target_preserved("step2 close_all_documents")

    def test_step2_process_country_does_not_follow_symlink(self):
        self.plant("temp_run.jsx")
        module = load_script("scripts/step2_apply_pantone_swatches.py")
        self.call_writer(lambda: module.process_country("LC"))
        self.assert_target_preserved("step2 process_country")

    def test_documented_step2_codes_lc_does_not_follow_temp_run_symlink(self):
        """python3 scripts/step2_apply_pantone_swatches.py --codes LC"""
        self.plant("temp_run.jsx")
        self.preserve_file(REPO / "04_ai_cmyk" / "logs" / "progress_step2.txt")
        self.preserve_flag_project_link()
        self.run_script(
            "scripts/step2_apply_pantone_swatches.py", "--codes", "LC"
        )
        self.assert_target_preserved("step2 --codes LC")

    def test_step2_end_of_run_close_does_not_follow_symlink(self):
        """A run that skips the country still calls close_all_documents at the end."""
        self.plant("temp_closeall.jsx")
        self.preserve_file(REPO / "04_ai_cmyk" / "logs" / "progress_step2.txt")
        self.preserve_flag_project_link()
        self.run_script(
            "scripts/step2_apply_pantone_swatches.py",
            "--codes",
            "NO_SUCH_COUNTRY_CODE",
        )
        self.assert_target_preserved("step2 end-of-run close_all_documents")

    def test_step1_close_all_documents_does_not_follow_symlink(self):
        self.plant("temp_closeall.jsx")
        module = load_script("scripts/step1_convert_svg_to_cmyk_ai.py")
        self.call_writer(module.close_all_documents)
        self.assert_target_preserved("step1 close_all_documents")

    def test_step1_process_country_does_not_follow_symlink(self):
        self.plant("temp_run.jsx")
        module = load_script("scripts/step1_convert_svg_to_cmyk_ai.py")
        self.call_writer(lambda: module.process_country("LC"))
        self.assert_target_preserved("step1 process_country")

    def test_batch_update_close_all_documents_does_not_follow_symlink(self):
        self.plant("temp_closeall.jsx")
        module = load_script("scripts/batch_ai_cmyk_update.py")
        self.call_writer(module.close_all_documents)
        self.assert_target_preserved("batch_ai_cmyk_update close_all_documents")

    def test_batch_update_process_country_does_not_follow_symlink(self):
        self.plant("temp_run.jsx")
        module = load_script("scripts/batch_ai_cmyk_update.py")
        self.call_writer(lambda: module.process_country("LC"))
        self.assert_target_preserved("batch_ai_cmyk_update process_country")

    def test_convert_spot_process_one_does_not_follow_symlink(self):
        self.plant("temp_convert_spot.jsx")
        module = load_script("scripts/convert_spot_to_process.py")
        self.call_writer(lambda: module.process_one("LC"))
        self.assert_target_preserved("convert_spot_to_process process_one")

    def test_batch_missing_script_does_not_follow_symlink(self):
        self.plant("temp_CC.jsx")
        self.run_script("scripts/batch_ai_cmyk_missing.py")
        self.assert_target_preserved("batch_ai_cmyk_missing.py")

    def test_batch_missing8_script_does_not_follow_symlink(self):
        self.plant("temp_CC.jsx")
        self.run_script("scripts/batch_ai_cmyk_missing8.py")
        self.assert_target_preserved("batch_ai_cmyk_missing8.py")


if __name__ == "__main__":
    unittest.main()
