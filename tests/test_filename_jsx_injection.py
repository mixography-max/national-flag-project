"""Filename and spec-string injection into Illustrator JSX batch scripts.

These tests fail while a data-file name or a spec string can break out of the
JavaScript quotes in a generated script that the batch driver then executes.
They pass once those values are rejected or embedded so the script text cannot
run, while a real country code such as PY_reverse is still opened.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import batch_ai_cmyk_update  # noqa: E402
import convert_spot_to_process  # noqa: E402
import step1_convert_svg_to_cmyk_ai as step1  # noqa: E402
import step2_apply_pantone_swatches as step2  # noqa: E402

from tests.jsx_host import JsxHost  # noqa: E402

# Evaluated while the generated script builds the File argument, before open.
ATTACK = 'ZZ"+(PAYLOAD_RAN=1)+"'
SAFE = "PY_reverse"


def _spec(pantone: str | None = None) -> str:
    color = {"hex": "#112233", "cmyk": "0-0-0-0", "pantone": pantone or "Pantone 000 C"}
    return json.dumps({"colors": [color]})


class FilenameJsxInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dirs: list[Path] = []

    def tearDown(self) -> None:
        for path in self._dirs:
            shutil.rmtree(path, ignore_errors=True)

    def _tmp(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="flag-jsx-"))
        self._dirs.append(path)
        return path

    def _layout(self, root: Path) -> dict[str, Path]:
        spec = root / "02_official_specs"
        svg = root / "03_svg_verified"
        ai = root / "04_ai_cmyk"
        logs = ai / "logs"
        for directory in (spec, svg, logs):
            directory.mkdir(parents=True, exist_ok=True)
        return {"root": root, "spec": spec, "svg": svg, "ai": ai, "logs": logs}

    def _write_pair(self, paths: dict[str, Path], code: str, spec_text: str, svg: bool, ai: bool) -> None:
        if spec_text is not None:
            (paths["spec"] / f"{code}.json").write_text(spec_text, encoding="utf-8")
        if svg:
            (paths["svg"] / f"{code}.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        if ai:
            (paths["ai"] / f"{code}.ai").write_bytes(b"%AI")

    def _symlink(self, module, root: Path) -> None:
        link = module.ASCII_ROOT
        if link.is_symlink() or link.exists():
            link.unlink()
        os.symlink(str(root), str(link))

    def _bind(self, module, host: JsxHost, **constants):
        sleep = patch.object(module.time, "sleep", lambda *_a, **_k: None) if hasattr(module, "time") else None
        runners = [
            patch.object(module.subprocess, "run", host),
        ]
        if sleep is not None:
            runners.append(sleep)
        for name, value in constants.items():
            runners.append(patch.object(module, name, value))
        stack = None
        from contextlib import ExitStack
        stack = ExitStack()
        for item in runners:
            stack.enter_context(item)
        return stack

    def _host(self, root: Path) -> JsxHost:
        host = JsxHost()
        host.install(root / "host")
        return host

    def _finish(self, host: JsxHost, root: Path) -> JsxHost:
        host.sweep(root)
        return host

    def assertNoPayload(self, host: JsxHost) -> None:
        self.assertEqual(host.payload, 0, host.debug())

    def assertOpened(self, host: JsxHost, path: str) -> None:
        seen = host.opened + host.files
        self.assertIn(path, seen, host.debug())

    # --- step2: the reported sink ------------------------------------------

    def test_step2_default_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        self._write_pair(paths, SAFE, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            step2, host,
            PROJECT_ROOT=root,
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step2.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step2.sys, "argv", ["step2"]):
            step2.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertOpened(host, "/tmp/flag_project/04_ai_cmyk/PY_reverse.ai")

    def test_step2_all_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            step2, host,
            PROJECT_ROOT=root,
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step2.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step2.sys, "argv", ["step2", "--all"]):
            step2.main()
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_step2_process_country_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            step2, host,
            PROJECT_ROOT=root,
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step2.txt",
            ASCII_ROOT=root / "ascii",
        ):
            self._symlink(step2, root)
            step2.process_country(ATTACK)
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_step2_codes_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            step2, host,
            PROJECT_ROOT=root,
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step2.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step2.sys, "argv", ["step2", "--codes", ATTACK]):
            step2.main()
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_step2_safe_country_code_is_opened(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, SAFE, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            step2, host,
            PROJECT_ROOT=root,
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step2.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step2.sys, "argv", ["step2", "--all"]):
            step2.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertOpened(host, "/tmp/flag_project/04_ai_cmyk/PY_reverse.ai")
        self.assertTrue(any("do javascript" in " ".join(cmd) for cmd in host.commands), host.debug())

    def test_step2_pantone_string_does_not_run(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, SAFE, _spec(pantone=ATTACK), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            step2, host,
            PROJECT_ROOT=root,
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step2.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step2.sys, "argv", ["step2", "--codes", SAFE]):
            step2.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertOpened(host, "/tmp/flag_project/04_ai_cmyk/PY_reverse.ai")

    # --- step1 shares the unescaped path sink --------------------------------

    def test_step1_all_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=True, ai=False)
        self._write_pair(paths, SAFE, _spec(), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            step1, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step1.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step1.sys, "argv", ["step1", "--all"]):
            step1.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertOpened(host, "/tmp/flag_project/03_svg_verified/PY_reverse.svg")

    def test_step1_update_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            step1, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step1.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(step1.sys, "argv", ["step1"]):
            step1.main()
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_step1_process_country_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            step1, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress_step1.txt",
            ASCII_ROOT=root / "ascii",
        ):
            self._symlink(step1, root)
            step1.process_country(ATTACK)
        self._finish(host, root)
        self.assertNoPayload(host)

    # --- older batch drivers share the same sink ------------------------------

    def test_batch_update_all_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=True, ai=False)
        self._write_pair(paths, SAFE, _spec(), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            batch_ai_cmyk_update, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(batch_ai_cmyk_update.sys, "argv", ["update", "--all"]):
            batch_ai_cmyk_update.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertOpened(host, str((root / "ascii" / "03_svg_verified" / f"{SAFE}.svg")))

    def test_batch_update_default_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            batch_ai_cmyk_update, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress.txt",
            ASCII_ROOT=root / "ascii",
        ), patch.object(batch_ai_cmyk_update.sys, "argv", ["update"]):
            batch_ai_cmyk_update.main()
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_batch_update_process_country_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            batch_ai_cmyk_update, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress.txt",
            ASCII_ROOT=root / "ascii",
        ):
            self._symlink(batch_ai_cmyk_update, root)
            batch_ai_cmyk_update.process_country(ATTACK)
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_batch_update_pantone_string_does_not_run(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, SAFE, _spec(pantone=ATTACK), svg=True, ai=False)
        host = self._host(root)
        with self._bind(
            batch_ai_cmyk_update, host,
            PROJECT_ROOT=root,
            SVG_DIR=paths["svg"],
            SPEC_DIR=paths["spec"],
            AI_OUT_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "progress.txt",
            ASCII_ROOT=root / "ascii",
        ):
            self._symlink(batch_ai_cmyk_update, root)
            batch_ai_cmyk_update.process_country(SAFE)
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_convert_spot_default_mode_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        self._write_pair(paths, SAFE, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            convert_spot_to_process, host,
            PROJECT_ROOT=root,
            AI_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "spot_to_process_done.txt",
            JSX_PATH=root / "temp_convert_spot.jsx",
        ), patch.object(convert_spot_to_process.sys, "argv", ["convert"]):
            convert_spot_to_process.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertOpened(host, str((paths["ai"] / f"{SAFE}.ai").absolute()))

    def test_convert_spot_process_one_does_not_run_filename_script(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            convert_spot_to_process, host,
            PROJECT_ROOT=root,
            AI_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "spot_to_process_done.txt",
            JSX_PATH=root / "temp_convert_spot.jsx",
        ):
            convert_spot_to_process.process_one(ATTACK)
        self._finish(host, root)
        self.assertNoPayload(host)

    def test_convert_spot_dry_run_does_not_write_jsx(self) -> None:
        root = self._tmp()
        paths = self._layout(root)
        self._write_pair(paths, ATTACK, _spec(), svg=False, ai=True)
        host = self._host(root)
        with self._bind(
            convert_spot_to_process, host,
            PROJECT_ROOT=root,
            AI_DIR=paths["ai"],
            PROGRESS_LOG=paths["logs"] / "spot_to_process_done.txt",
            JSX_PATH=root / "temp_convert_spot.jsx",
        ), patch.object(convert_spot_to_process.sys, "argv", ["convert", "--dry-run"]):
            convert_spot_to_process.main()
        self._finish(host, root)
        self.assertNoPayload(host)
        self.assertFalse(any("do javascript" in " ".join(cmd) for cmd in host.commands), host.debug())
        self.assertFalse((root / "temp_convert_spot.jsx").exists())


if __name__ == "__main__":
    unittest.main()
