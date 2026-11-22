"""Path injection in scripts/batch_ai_cmyk_update.py.

A verified SVG stem is copied into the ExtendScript passed to Illustrator.
Double quotes and backslashes in that stem must stay inside string literals,
and a stem that is not a country code must be refused before the updater
writes a script or starts Illustrator.

Safe country codes are the stems already shipped in 03_svg_verified:
two uppercase letters, optionally followed by an underscore and a lowercase
word (JP, PY_reverse, CR_state, PE_state, PH_war).
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Saved before tests replace the batch module's subprocess.run. Assigning that
# name replaces the shared subprocess module attribute, so the JSX harness
# must keep this original.
REAL_SUBPROCESS_RUN = subprocess.run

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "batch_ai_cmyk_update.py"

# Stems that close the double-quoted ExtendScript string and call SENTINEL
# while the File() argument is evaluated. The backslash form still evaluates
# to a different path if only quotation marks are escaped.
QUOTE_STEM = 'AB"+(SENTINEL())+"'
BACKSLASH_STEM = 'CD\\\\"+(SENTINEL())+"'
NEWLINE_STEM = 'EF\n"+(SENTINEL())+"'
UNSAFE_STEMS = (QUOTE_STEM, BACKSLASH_STEM, NEWLINE_STEM)

# Adobe JavaScript Tools Guide CS5, "ExtendScript overview": ExtendScript
# implements JavaScript according to the ECMA specification. The harness below
# evaluates the generated program with that language's string literals,
# addition operator, and call expressions. Illustrator objects the script
# touches are filled in from the calls in generate_jsx (open, the CMYK wait
# loop, saveAs, close).
JSX_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const jsx = fs.readFileSync(process.argv[2], "utf8");
let calls = 0;
function SENTINEL() {
  calls += 1;
  return "ZZ";
}
function File(p) {
  this.p = String(p);
}
function IllustratorSaveOptions() {}
const doc = {
  pageItems: [],
  layers: [],
  documentColorSpace: "CMYK",
  spots: {
    getByName() {
      throw new Error("missing spot");
    },
  },
  saveAs(file) {
    saved.push(file.p);
  },
  close() {},
};
const opened = [];
const saved = [];
const app = {
  userInteractionLevel: 0,
  documents: [doc],
  activeDocument: doc,
  open(file) {
    opened.push(file.p);
    app.documents = [doc];
    app.activeDocument = doc;
    return doc;
  },
  executeMenuCommand() {},
};
const sandbox = {
  app,
  File,
  SENTINEL,
  UserInteractionLevel: { DONTDISPLAYALERTS: 0 },
  DocumentColorSpace: { CMYK: "CMYK" },
  SaveOptions: { DONOTSAVECHANGES: 1 },
  IllustratorSaveOptions,
  $: { sleep() {} },
};
let error = null;
let result = null;
try {
  result = vm.runInNewContext(jsx, sandbox, { timeout: 2000 });
} catch (err) {
  error = err.name + ": " + err.message;
}
process.stdout.write(JSON.stringify({
  calls,
  opened,
  saved,
  result,
  error,
}));
"""


def load_module():
    spec = importlib.util.spec_from_file_location(
        "batch_ai_cmyk_update_under_test", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute_jsx(jsx_text):
    """Run the generated ExtendScript and return the paths Illustrator would use."""
    with tempfile.TemporaryDirectory() as work:
        work_path = Path(work)
        script_path = work_path / "harness.js"
        jsx_path = work_path / "generated.jsx"
        script_path.write_text(JSX_HARNESS, encoding="utf-8")
        jsx_path.write_text(jsx_text, encoding="utf-8")
        completed = REAL_SUBPROCESS_RUN(
            ["node", str(script_path), str(jsx_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if completed.returncode != 0:
        raise AssertionError(
            "generated script failed to parse or run\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return json.loads(completed.stdout)


def embedded_paths(module, svg_path, ai_path):
    svg_abs = str(module.ASCII_ROOT / svg_path.relative_to(module.PROJECT_ROOT))
    ai_abs = str(module.ASCII_ROOT / ai_path.relative_to(module.PROJECT_ROOT))
    return svg_abs, ai_abs


class CmykPathInjectionTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.module.PROJECT_ROOT = self.root
        self.module.SVG_DIR = self.root / "03_svg_verified"
        self.module.SPEC_DIR = self.root / "02_official_specs"
        self.module.AI_OUT_DIR = self.root / "04_ai_cmyk"
        self.module.PROGRESS_LOG = self.module.AI_OUT_DIR / "logs" / "progress.txt"
        self.module.ASCII_ROOT = self.root / "ascii_link"
        self.module.SVG_DIR.mkdir()
        self.module.SPEC_DIR.mkdir()
        self.module.AI_OUT_DIR.mkdir()
        self.illustrator_calls = []
        self.writes = []
        self._real_open = open

        def tracking_open(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                self.writes.append(os.fspath(file))
            return self._real_open(file, mode, *args, **kwargs)

        def recording_run(cmd, **kwargs):
            joined = " ".join(str(part) for part in cmd)
            body = ""
            if "temp_run.jsx" in joined:
                jsx_path = self.module.PROJECT_ROOT / "temp_run.jsx"
                body = jsx_path.read_text(encoding="utf-8")
                # Illustrator would rewrite the AI file. Refresh its mtime so
                # the updater's age check observes that save.
                now = self.module.time.time()
                out_dir = self.module.AI_OUT_DIR
                if out_dir.exists():
                    for ai_file in out_dir.glob("*.ai"):
                        os.utime(ai_file, (now, now))
            self.illustrator_calls.append({"cmd": joined, "body": body})
            return subprocess.CompletedProcess(
                cmd, 0, stdout="SAVED_OK", stderr=""
            )

        class _IllustratorSubprocess:
            TimeoutExpired = subprocess.TimeoutExpired

            @staticmethod
            def run(cmd, **kwargs):
                return recording_run(cmd, **kwargs)

        # Replace the binding in the batch module only. The shared subprocess
        # module stays available to the JSX harness.
        self.module.subprocess = _IllustratorSubprocess()
        self.module.time.sleep = lambda *_args, **_kwargs: None
        import builtins

        self._builtins = builtins
        builtins.open = tracking_open

    def tearDown(self):
        self._builtins.open = self._real_open
        self._tmpdir.cleanup()

    def add_country(self, code, svg_text="<svg xmlns='http://www.w3.org/2000/svg'/>"):
        svg_path = self.module.SVG_DIR / f"{code}.svg"
        spec_path = self.module.SPEC_DIR / f"{code}.json"
        svg_path.write_text(svg_text, encoding="utf-8")
        spec_path.write_text('{"colors": []}\n', encoding="utf-8")
        return svg_path, spec_path

    def assert_jsx_is_data(self, jsx_text, svg_path, ai_path):
        svg_abs, ai_abs = embedded_paths(self.module, svg_path, ai_path)
        outcome = execute_jsx(jsx_text)
        self.assertIsNone(
            outcome["error"],
            f"script did not run to completion: {outcome}",
        )
        self.assertEqual(outcome["result"], "SAVED_OK", outcome)
        self.assertEqual(outcome["calls"], 0, outcome)
        self.assertEqual(outcome["opened"], [svg_abs], outcome)
        self.assertEqual(outcome["saved"], [ai_abs], outcome)

    def test_generate_jsx_embeds_open_and_save_paths_as_data(self):
        for stem in UNSAFE_STEMS:
            with self.subTest(stem=stem):
                svg_path, _spec_path = self.add_country(stem)
                ai_path = self.module.AI_OUT_DIR / f"{stem}.ai"
                jsx_text = self.module.generate_jsx(
                    svg_path, ai_path, {"colors": []}
                )
                self.assert_jsx_is_data(jsx_text, svg_path, ai_path)

    def test_process_country_refuses_unsafe_stem_before_side_effects(self):
        for stem in UNSAFE_STEMS:
            with self.subTest(stem=stem):
                svg_path, spec_path = self.add_country(stem)
                self.writes.clear()
                self.illustrator_calls.clear()
                try:
                    status = self.module.process_country(stem)
                except Exception as exc:
                    status = exc
                self.assertFalse(
                    any(Path(path).name == "temp_run.jsx" for path in self.writes),
                    f"JSX was written before refusal: {self.writes}",
                )
                self.assertEqual(self.illustrator_calls, [])
                self.assertTrue(svg_path.exists())
                self.assertTrue(spec_path.exists())
                self.assertFalse((self.module.AI_OUT_DIR / f"{stem}.ai").exists())
                self.assertNotEqual(status, "SUCCESS")

    def test_get_codes_needing_update_keeps_only_country_codes(self):
        self.add_country("JP")
        self.add_country("PY_reverse")
        self.add_country(QUOTE_STEM)
        self.assertEqual(
            self.module.get_codes_needing_update(),
            ["JP", "PY_reverse"],
        )

    def test_main_runs_the_authorized_country_and_not_the_injected_stem(self):
        for mode in ("--all", "--update"):
            with self.subTest(mode=mode):
                self.add_country("JP")
                self.add_country(QUOTE_STEM)
                ai_path = self.module.AI_OUT_DIR / "JP.ai"
                ai_path.write_bytes(b"previous")
                os.utime(ai_path, (1, 1))
                # SVG is newer than the AI file, so default mode selects JP.
                os.utime(
                    self.module.SVG_DIR / "JP.svg",
                    (2_000_000_000, 2_000_000_000),
                )
                self.illustrator_calls.clear()
                self.writes.clear()
                argv = ["batch_ai_cmyk_update.py"]
                if mode == "--all":
                    argv.append("--all")
                previous_argv = sys.argv
                sys.argv = argv
                try:
                    self.module.main()
                finally:
                    sys.argv = previous_argv

                launched = [
                    call for call in self.illustrator_calls if call["body"]
                ]
                self.assertEqual(len(launched), 1, self.illustrator_calls)
                command = launched[0]["cmd"]
                jsx_ascii = str(self.module.ASCII_ROOT / "temp_run.jsx")
                self.assertIn(
                    'tell application "Adobe Illustrator" to do javascript '
                    f'file POSIX file "{jsx_ascii}"',
                    command,
                )
                self.assert_jsx_is_data(
                    launched[0]["body"],
                    self.module.SVG_DIR / "JP.svg",
                    self.module.AI_OUT_DIR / "JP.ai",
                )
                self.assertNotIn(QUOTE_STEM, launched[0]["body"])


if __name__ == "__main__":
    unittest.main()
