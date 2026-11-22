"""Filename injection in scripts/convert_spot_to_process.py.

These tests fail while a name in 04_ai_cmyk is pasted into the ExtendScript
template with str.format. They pass when that name is not executed: the batch
refuses it before writing a script, or the path is data inside the script.

The oracle is the ExtendScript host the batch actually invokes. osascript is
not installed here, and neither is Illustrator, so the test supplies the
osascript binary on PATH. That stand-in reads the JSX file named by the
product command and evaluates it with the ECMA-262 string and call rules
ExtendScript implements, plus the File methods the JavaScript Tools Guide
defines. File.execute launches a program. File.open("w") plus File.write
creates or overwrites a file. A fixed converter must not reach either method
from text that came from a filename.

Not covered here, because an extra file in 04_ai_cmyk never becomes their
script text:

- scripts/batch_ai_cmyk.py
- scripts/batch_ai_cmyk_update.py
- scripts/batch_ai_cmyk_missing.py
- scripts/batch_ai_cmyk_missing8.py
- scripts/step1_convert_svg_to_cmyk_ai.py
- scripts/step2_apply_pantone_swatches.py

Those scripts interpolate SVG paths, JSON fields, or a fixed code list. The
osascript line in convert_spot_to_process.py also quotes JSX_PATH, which is
the fixed temp_convert_spot.jsx path, not the AI filename.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "convert_spot_to_process.py"
NODE = shutil.which("node")

# Legal filenames. A slash cannot be part of a name, so the spelling that
# comments out the rest of the line with // is not a file the batch can open.
# Each name below closes the JavaScript string and keeps the template's
# trailing .ai"); as a separate expression.
LAUNCH = 'ZZ"); (new File("launch-me")).execute(); (".ai'
WRITE = (
    'ZZ"); (function(){var f=new File("owned");'
    'f.open("w");f.write("owned");f.close();})(); (".ai'
)
NEWLINE_LAUNCH = 'ZZ"\n); (new File("launch-me")).execute();\n(".ai'
CR_LAUNCH = 'ZZ"\r); (new File("launch-me")).execute();\r(".ai'
# Two backslashes encode one escaped backslash, so the following quote ends
# the string. One backslash escapes that quote instead.
TWO_BACKSLASH_LAUNCH = 'ZZ\\\\"); (new File("launch-me")).execute(); (".ai'
ONE_BACKSLASH_LAUNCH = 'ZZ\\"); (new File("launch-me")).execute(); (".ai'

PAYLOADS = (
    ("quote", LAUNCH),
    ("write", WRITE),
    ("newline", NEWLINE_LAUNCH),
    ("carriage-return", CR_LAUNCH),
    ("two-backslashes", TWO_BACKSLASH_LAUNCH),
    ("one-backslash", ONE_BACKSLASH_LAUNCH),
)


HOST_PRELUDE = r"""
var __executes = [];
var __writes = [];
var __reads = [];
function File(path) {
    this.fsName = path === undefined ? "" : String(path);
}
File.prototype.open = function (mode) {
    this._mode = String(mode);
    return true;
};
File.prototype.read = function () {
    __reads.push(this.fsName);
    return "";
};
File.prototype.write = function (text) {
    __writes.push({path: this.fsName, mode: this._mode || "", text: String(text)});
    return true;
};
File.prototype.close = function () { return true; };
File.prototype.execute = function () {
    __executes.push(this.fsName);
    return true;
};
var app = { open: function () { throw new Error("no document"); } };
var ColorModel = { SPOT: 1, PROCESS: 2 };
function IllustratorSaveOptions() {}
var SaveOptions = { DONOTSAVECHANGES: 1 };
"""


NODE_RUNNER = r"""
const fs = require("fs");
const vm = require("vm");
const jsx = fs.readFileSync(process.argv[2], "utf8");
const prelude = fs.readFileSync(process.argv[3], "utf8");
const sandbox = {};
vm.createContext(sandbox);
let error = null;
try {
  vm.runInContext(prelude + "\n" + jsx, sandbox, {filename: "generated.jsx"});
} catch (e) {
  error = String(e && e.stack || e);
}
fs.writeFileSync(process.argv[4], JSON.stringify({
  executes: sandbox.__executes || [],
  writes: sandbox.__writes || [],
  reads: sandbox.__reads || [],
  error: error
}));
"""


OSASCRIPT = r"""#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path

log_path = Path(os.environ["SPOT_EVAL_LOG"])
node = os.environ["SPOT_NODE"]
runner = os.environ["SPOT_NODE_RUNNER"]
prelude = os.environ["SPOT_HOST_PRELUDE"]

args = sys.argv[1:]
scripts = []
i = 0
while i < len(args):
    if args[i] == "-e" and i + 1 < len(args):
        scripts.append(args[i + 1])
        i += 2
        continue
    log_path.write_text(json.dumps({
        "harness_error": "unexpected osascript argument",
        "args": args,
    }) + "\n")
    sys.exit(2)

text = "\n".join(scripts)
match = re.search(r'do javascript file POSIX file "([^"]*)"', text)
if not match:
    log_path.write_text(json.dumps({
        "harness_error": "command did not name a JSX file",
        "text": text,
    }) + "\n")
    sys.exit(2)

jsx_path = Path(match.group(1))
out = log_path.with_suffix(".one.json")
proc = __import__("subprocess").run(
    [node, runner, str(jsx_path), prelude, str(out)],
    capture_output=True, text=True,
)
if proc.returncode != 0 or not out.exists():
    log_path.write_text(json.dumps({
        "harness_error": "javascript evaluator failed",
        "status": proc.returncode,
        "stderr": proc.stderr,
    }) + "\n")
    sys.exit(2)

record = json.loads(out.read_text())
record["source"] = "osascript"
with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
sys.exit(0)
"""


def load_converter():
    spec = importlib.util.spec_from_file_location("convert_spot_to_process", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SpotFilenameInjectionTests(unittest.TestCase):
    def setUp(self):
        if NODE is None:
            self.fail("node is required to evaluate the generated ExtendScript")
        self.module = load_converter()
        self._saved = {
            "AI_DIR": self.module.AI_DIR,
            "JSX_PATH": self.module.JSX_PATH,
            "PROGRESS_LOG": self.module.PROGRESS_LOG,
            "argv": list(sys.argv),
            "PATH": os.environ.get("PATH", ""),
            "write_text": Path.write_text,
        }
        self.events = []
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ai_dir = self.root / "04_ai_cmyk"
        self.ai_dir.mkdir()
        self.jsx_path = self.root / "temp_convert_spot.jsx"
        self.progress = self.root / "logs" / "spot_to_process_done.txt"
        self.eval_log = self.root / "eval.jsonl"
        prelude = self.root / "host.js"
        runner = self.root / "run_jsx.js"
        prelude.write_text(HOST_PRELUDE, encoding="utf-8")
        runner.write_text(NODE_RUNNER, encoding="utf-8")
        bindir = self.root / "bin"
        bindir.mkdir()
        osascript = bindir / "osascript"
        osascript.write_text(OSASCRIPT, encoding="utf-8")
        osascript.chmod(0o755)
        os.environ["PATH"] = str(bindir) + os.pathsep + self._saved["PATH"]
        os.environ["SPOT_EVAL_LOG"] = str(self.eval_log)
        os.environ["SPOT_NODE"] = NODE
        os.environ["SPOT_NODE_RUNNER"] = str(runner)
        os.environ["SPOT_HOST_PRELUDE"] = str(prelude)
        self._prelude = prelude
        self._runner = runner

        def tracing_write_text(path_obj, data, *args, **kwargs):
            result = self._saved["write_text"](path_obj, data, *args, **kwargs)
            if Path(path_obj) == Path(self.module.JSX_PATH):
                self.events.append(self.evaluate(Path(path_obj).read_text(encoding="utf-8")))
                self.events[-1]["source"] = "write_text"
            return result

        Path.write_text = tracing_write_text
        self.module.time.sleep = lambda *args, **kwargs: None

    def tearDown(self):
        Path.write_text = self._saved["write_text"]
        sys.argv = self._saved["argv"]
        os.environ["PATH"] = self._saved["PATH"]
        for key in ("SPOT_EVAL_LOG", "SPOT_NODE", "SPOT_NODE_RUNNER", "SPOT_HOST_PRELUDE"):
            os.environ.pop(key, None)
        self.module.AI_DIR = self._saved["AI_DIR"]
        self.module.JSX_PATH = self._saved["JSX_PATH"]
        self.module.PROGRESS_LOG = self._saved["PROGRESS_LOG"]
        self.tmp.cleanup()

    def evaluate(self, jsx_text):
        source = self.root / "snippet.jsx"
        out = self.root / "snippet.json"
        source.write_bytes(jsx_text.encode("utf-8"))
        proc = subprocess.run(
            [NODE, str(self._runner), str(source), str(self._prelude), str(out)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not out.exists():
            return {
                "harness_error": "javascript evaluator failed",
                "status": proc.returncode,
                "stderr": proc.stderr,
                "executes": [],
                "writes": [],
                "reads": [],
            }
        return json.loads(out.read_text(encoding="utf-8"))

    def place(self, filename):
        for old in self.ai_dir.glob("*"):
            if old.is_file():
                old.unlink()
        target = self.ai_dir / filename
        target.write_bytes(b"%PDF-1.4 not an Illustrator document")
        return target.stem

    def arm(self):
        self.module.AI_DIR = self.ai_dir
        self.module.JSX_PATH = self.jsx_path
        self.module.PROGRESS_LOG = self.progress
        if self.progress.exists():
            self.progress.unlink()
        self.events = []
        self.eval_log.write_text("", encoding="utf-8")

    def collected(self):
        events = list(self.events)
        if self.eval_log.exists():
            for line in self.eval_log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        problems = [event for event in events if event.get("harness_error")]
        if problems:
            self.fail("ExtendScript stand-in failed: " + json.dumps(problems))
        return events

    def assert_filename_is_data(self):
        executes = []
        writes = []
        reads = []
        for event in self.collected():
            executes.extend(event.get("executes") or [])
            writes.extend(event.get("writes") or [])
            reads.extend(event.get("reads") or [])
        self.assertEqual(executes, [], "filename called File.execute")
        self.assertEqual(writes, [], "filename called File.write")
        self.assertEqual(reads, [], "filename called File.read")

    def run_payload(self, filename, mode):
        code = self.place(filename)
        self.arm()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if mode == "glob":
                sys.argv = ["convert_spot_to_process.py"]
                self.module.main()
            elif mode == "resume":
                sys.argv = ["convert_spot_to_process.py", "--resume"]
                self.module.main()
            elif mode == "codes":
                sys.argv = ["convert_spot_to_process.py", "--codes", code]
                self.module.main()
            elif mode == "process_one":
                self.module.process_one(code)
            else:
                raise AssertionError(mode)
        self.assert_filename_is_data()

    def test_default_batch_does_not_execute_filenames(self):
        for label, filename in PAYLOADS:
            with self.subTest(payload=label):
                self.run_payload(filename, "glob")

    def test_resume_batch_does_not_execute_filenames(self):
        for label, filename in PAYLOADS:
            with self.subTest(payload=label):
                self.run_payload(filename, "resume")

    def test_codes_batch_does_not_execute_filenames(self):
        for label, filename in PAYLOADS:
            with self.subTest(payload=label):
                self.run_payload(filename, "codes")

    def test_process_one_does_not_execute_filenames(self):
        for label, filename in PAYLOADS:
            with self.subTest(payload=label):
                self.run_payload(filename, "process_one")


if __name__ == "__main__":
    unittest.main()
