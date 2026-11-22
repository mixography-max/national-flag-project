"""Pantone names from official spec JSON must stay data in generated ExtendScript.

scripts/batch_ai_cmyk_update.py copies each color's pantone into double-quoted
ExtendScript. These tests run that updater on a spec file and then evaluate the
temp_run.jsx file it writes. They pass only when every pantone value is still
the original string and the marker assignment inside a hostile value does not run.

scripts/batch_ai_cmyk.py interpolates pantone the same way, but the module does
not compile (unterminated string at scripts/batch_ai_cmyk.py:89), so it is not
executed here. Path strings interpolated from the project directory are not spec
fields and are not covered.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');
const sandbox = {
  pwned: 0,
  __getByName: [],
  __spotNames: [],
  __mappingPantones: [],
};
vm.createContext(sandbox);
const init = `
  var UserInteractionLevel = { DONTDISPLAYALERTS: 1, DISPLAYALERTS: 2 };
  var ColorModel = { SPOT: 1, PROCESS: 2 };
  var DocumentColorSpace = { CMYK: { id: 'CMYK' } };
  var SaveOptions = { DONOTSAVECHANGES: 1 };
  function IllustratorSaveOptions() { this.pdfCompatible = false; }
  function CMYKColor() { this.cyan = 0; this.magenta = 0; this.yellow = 0; this.black = 0; }
  function SpotColor() { this.spot = null; this.tint = 100; }
  function File(path) { this.path = path; this.open = function () {}; this.writeln = function () {}; this.close = function () {}; }
  var $ = { sleep: function () {}, writeln: function () {} };
  var doc = {
    pageItems: [],
    pathItems: [],
    documentColorSpace: DocumentColorSpace.CMYK,
    spots: {
      getByName: function (name) {
        __getByName.push(name);
        return null;
      },
      add: function () {
        var spot = {};
        Object.defineProperty(spot, 'name', {
          configurable: true,
          enumerable: true,
          get: function () { return spot.__name; },
          set: function (v) { spot.__name = v; __spotNames.push(v); }
        });
        return spot;
      }
    },
    saveAs: function () {},
    save: function () {},
    close: function () {}
  };
  var app = {
    userInteractionLevel: 0,
    activeDocument: doc,
    documents: [doc],
    open: function () { return doc; },
    executeMenuCommand: function () {}
  };
  var __origPush = Array.prototype.push;
  Array.prototype.push = function () {
    for (var i = 0; i < arguments.length; i++) {
      var item = arguments[i];
      if (item && typeof item === 'object' && Object.prototype.hasOwnProperty.call(item, 'pantone')) {
        __mappingPantones.push(item.pantone);
      }
    }
    return __origPush.apply(this, arguments);
  };
`;
try {
  vm.runInContext(init + '\n' + src, sandbox, { timeout: 3000 });
  process.stdout.write(JSON.stringify({
    ok: true,
    pwned: sandbox.pwned,
    getByName: sandbox.__getByName,
    spotNames: sandbox.__spotNames,
    mappingPantones: sandbox.__mappingPantones,
  }));
} catch (e) {
  process.stdout.write(JSON.stringify({
    ok: false,
    error: String(e && e.stack ? e.stack : e),
    pwned: sandbox.pwned,
    getByName: sandbox.__getByName,
    spotNames: sandbox.__spotNames,
    mappingPantones: sandbox.__mappingPantones,
  }));
}
"""


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


UPDATE = load_module(
    "batch_ai_cmyk_update", REPO / "scripts" / "batch_ai_cmyk_update.py"
)
STEP2 = load_module(
    "step2_apply_pantone_swatches",
    REPO / "scripts" / "step2_apply_pantone_swatches.py",
)

# Expression text that is valid in getByName("..."), spot.name = "...", and
# pantone: "...". .strip() does not remove it when the breakout is in the middle.
QUOTE_BREAK = '193 C"+(pwned=(pwned||0)+1)+"'
BACKSLASH_BREAK = '193 C\\\\"+(pwned=(pwned||0)+1)+"\\\\'
NEWLINE_BREAK = '193 C\n"+(pwned=(pwned||0)+1)+"'
CR_BREAK = '193 C\r"+(pwned=(pwned||0)+1)+"'
LINE_SEP_BREAK = '193 C\u2028"+(pwned=(pwned||0)+1)+"'
PARA_SEP_BREAK = '193 C\u2029"+(pwned=(pwned||0)+1)+"'
COMMENT_BREAK = '193 C"); pwned=(pwned||0)+1; //'
ONE_BACKSLASH = "193 C\\281"
TWO_BACKSLASHES = "193 C\\\\281"


def color(pantone, hex_value="#B31942", cmyk="0, 100, 66, 13", name="Old Glory Red"):
    return {
        "color_name": name,
        "hex": hex_value,
        "rgb": "179, 25, 66",
        "cmyk": cmyk,
        "pantone": pantone,
    }


def evaluate_jsx(source: str) -> dict:
    work = Path(tempfile.mkdtemp(prefix="jsx-eval-"))
    try:
        harness = work / "harness.js"
        script = work / "generated.jsx"
        harness.write_text(HARNESS, encoding="utf-8")
        script.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            ["node", str(harness), str(script)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if completed.returncode != 0 and not completed.stdout:
            raise AssertionError(completed.stderr)
        return json.loads(completed.stdout)
    finally:
        shutil.rmtree(work)


@contextmanager
def patched_module(module, **values):
    previous = {key: getattr(module, key) for key in values}
    real_run = module.subprocess.run
    calls = []

    def spy(cmd, **kwargs):
        calls.append(list(cmd))
        kwargs = dict(kwargs)
        kwargs["timeout"] = 5
        return real_run(cmd, **kwargs)

    for key, value in values.items():
        setattr(module, key, value)
    module.subprocess.run = spy
    try:
        yield calls
    finally:
        module.subprocess.run = real_run
        for key, value in previous.items():
            setattr(module, key, value)


class PantoneExtendscriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pantone-jsx-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _layout(self, module, folder_name):
        root = self.tmp / folder_name
        spec_dir = root / "02_official_specs"
        svg_dir = root / "03_svg_verified"
        ai_dir = root / "04_ai_cmyk"
        ascii_root = self.tmp / f"ascii-{folder_name}"
        spec_dir.mkdir(parents=True)
        svg_dir.mkdir(parents=True)
        ai_dir.mkdir(parents=True)
        return root, spec_dir, svg_dir, ai_dir, ascii_root

    def _run_updater(self, module, folder, spec, code="US", need_svg=True, need_ai=False):
        root, spec_dir, svg_dir, ai_dir, ascii_root = self._layout(module, folder)
        (spec_dir / f"{code}.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if need_svg:
            (svg_dir / f"{code}.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        if need_ai:
            (ai_dir / f"{code}.ai").write_bytes(b"")
        if ascii_root.is_symlink() or ascii_root.exists():
            ascii_root.unlink()
        os.symlink(str(root.absolute()), str(ascii_root))
        values = {
            "PROJECT_ROOT": root,
            "SPEC_DIR": spec_dir,
            "AI_OUT_DIR": ai_dir,
            "ASCII_ROOT": ascii_root,
        }
        if hasattr(module, "SVG_DIR"):
            values["SVG_DIR"] = svg_dir
        with patched_module(module, **values) as calls:
            try:
                module.process_country(code)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        jsx_path = root / "temp_run.jsx"
        self.assertTrue(jsx_path.is_file(), "process_country did not write temp_run.jsx")
        self.assertTrue(calls, "process_country did not invoke osascript")
        command = calls[0]
        self.assertEqual(command[0], "osascript")
        self.assertIn(str(ascii_root / "temp_run.jsx"), " ".join(command))
        self.assertIn("do javascript file", " ".join(command))
        return evaluate_jsx(jsx_path.read_text(encoding="utf-8"))

    def assert_update_keeps_pantones(self, result, pantones):
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["pwned"], 0)
        self.assertEqual(result["mappingPantones"], pantones)
        spot_pantones = [value for value in pantones if value and value not in ("White", "Black")]
        self.assertEqual(result["spotNames"], spot_pantones)
        self.assertEqual(result["getByName"], spot_pantones + spot_pantones)

    def assert_step2_keeps_pantone(self, result, pantone):
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["pwned"], 0)
        if pantone and pantone not in ("White", "", "N/A"):
            self.assertEqual(result["getByName"], [pantone])
            self.assertEqual(result["spotNames"], [pantone])
        else:
            self.assertEqual(result["getByName"], [])
            self.assertEqual(result["spotNames"], [])

    def test_update_pantone_from_colors_stays_a_javascript_string(self):
        cases = {
            "quote_breakout": QUOTE_BREAK,
            "backslash_breakout": BACKSLASH_BREAK,
            "newline_breakout": NEWLINE_BREAK,
            "carriage_return_breakout": CR_BREAK,
            "line_separator_breakout": LINE_SEP_BREAK,
            "paragraph_separator_breakout": PARA_SEP_BREAK,
            "line_comment_breakout": COMMENT_BREAK,
            "one_backslash": ONE_BACKSLASH,
            "two_backslashes": TWO_BACKSLASHES,
            "plain_193_c": "193 C",
            "white": "White",
            "black": "Black",
            "empty": "",
        }
        for name, pantone in cases.items():
            with self.subTest(name=name):
                spec = {
                    "iso_alpha2": "US",
                    "name_en": "United States",
                    "colors": [color(pantone)],
                }
                result = self._run_updater(UPDATE, name, spec)
                self.assert_update_keeps_pantones(result, [pantone])

    def test_update_us_spec_shape_keeps_every_pantone(self):
        """Same colors array shape as 02_official_specs/US.json, with a hostile red name."""
        pantones = [QUOTE_BREAK, "", "281 C"]
        spec = {
            "iso_alpha2": "US",
            "name_en": "United States",
            "colors": [
                color(pantones[0]),
                color("", hex_value="#FFFFFF", cmyk="0, 0, 0, 0", name="White"),
                color("281 C", hex_value="#0A3161", cmyk="100, 68, 0, 54", name="Old Glory Blue"),
            ],
        }
        result = self._run_updater(UPDATE, "us-shape", spec)
        self.assert_update_keeps_pantones(result, pantones)

    def test_update_colors_extracted_fallback_stays_a_javascript_string(self):
        spec = {"colors_extracted": [color(QUOTE_BREAK)]}
        result = self._run_updater(UPDATE, "extracted", spec)
        self.assert_update_keeps_pantones(result, [QUOTE_BREAK])

    def test_update_non_numeric_cmyk_does_not_run_as_script(self):
        spec = {"colors": [color("193 C", cmyk="0); pwned=(pwned||0)+1; //")]}
        result = self._run_updater(UPDATE, "cmyk", spec)
        self.assert_update_keeps_pantones(result, ["193 C"])

    def test_step2_pantone_embedded_with_json_stays_data(self):
        cases = {
            "quote_breakout": QUOTE_BREAK,
            "backslash_breakout": BACKSLASH_BREAK,
            "newline_breakout": NEWLINE_BREAK,
            "line_separator_breakout": LINE_SEP_BREAK,
            "paragraph_separator_breakout": PARA_SEP_BREAK,
            "one_backslash": ONE_BACKSLASH,
            "plain_193_c": "193 C",
            "white": "White",
        }
        for name, pantone in cases.items():
            with self.subTest(name=name):
                spec = {"colors": [color(pantone)]}
                result = self._run_updater(
                    STEP2, "step2-" + name, spec, need_svg=False, need_ai=True
                )
                self.assert_step2_keeps_pantone(result, pantone)


if __name__ == "__main__":
    unittest.main()
