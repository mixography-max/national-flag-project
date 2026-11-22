"""Run the JSX file an Illustrator batch script hands to osascript.

Adobe Illustrator executes that file as JavaScript (ExtendScript offers the
standard JavaScript language, and the AppleScript ``do javascript`` command
executes a JavaScript script). Illustrator itself is not installed here, so
the file named by the ``do javascript file POSIX file`` argument is evaluated
as a classic script, with stubs only for the host objects the generated
program touches. A filename that breaks out of its quotes runs as part of
evaluating that script.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

_NODE = r"""
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[2], "utf8");
const sandbox = {
  PAYLOAD_RAN: 0,
  files: [],
  SaveOptions: { DONOTSAVECHANGES: 0 },
  UserInteractionLevel: { DONTDISPLAYALERTS: 1, DISPLAYALERTS: 2 },
  ColorModel: { PROCESS: 1, SPOT: 2 },
  DocumentColorSpace: { CMYK: 1 },
  ElementPlacement: { PLACEATEND: 0 },
  CMYKColor: function CMYKColor() {},
  SpotColor: function SpotColor() {},
  RGBColor: function RGBColor() {},
  GrayColor: function GrayColor() {},
  IllustratorSaveOptions: function IllustratorSaveOptions() {},
  $: { sleep() {}, writeln() {} },
};
function makeDoc() {
  const doc = {
    pageItems: [],
    pathItems: [],
    layers: [],
    width: 10,
    height: 10,
    name: "",
    note: "",
    spots: {
      getByName() { throw new Error("missing spot"); },
      add() { return {}; },
    },
    save() {},
    saveAs() {},
    close() {
      const docs = sandbox.app.documents;
      const i = docs.indexOf(doc);
      if (i >= 0) docs.splice(i, 1);
    },
  };
  return doc;
}
sandbox.File = function File(p) {
  this.path = String(p);
  sandbox.files.push(this.path);
  this.open = function () {};
  this.close = function () {};
  this.writeln = function () {};
};
sandbox.app = {
  userInteractionLevel: 0,
  documents: [],
  activeDocument: null,
  opened: [],
  executeMenuCommand() {},
  open(f) {
    const doc = makeDoc();
    this.opened.push(f && f.path);
    this.documents.push(doc);
    this.activeDocument = doc;
    return doc;
  },
};
sandbox.app.documents.add = function () {
  const doc = makeDoc();
  sandbox.app.documents.push(doc);
  sandbox.app.activeDocument = doc;
  return doc;
};
vm.createContext(sandbox);
let err = null;
try {
  vm.runInContext(src, sandbox, { timeout: 2000 });
} catch (e) {
  err = String(e && e.stack || e).split("\n")[0];
}
fs.writeFileSync(process.argv[3], JSON.stringify({
  payload: sandbox.PAYLOAD_RAN,
  err: err,
  files: sandbox.files,
  opened: sandbox.app.opened,
}));
"""

_POSIX = re.compile(r'POSIX file "([^"]+)"')


class JsxHost:
    """Stand-in for ``osascript`` that evaluates the JSX file it is given."""

    def __init__(self) -> None:
        self.payload = 0
        self.opened: list[str] = []
        self.files: list[str] = []
        self.errors: list[str] = []
        self.commands: list[list[str]] = []
        self._digests: set[str] = set()
        self._real_run = subprocess.run
        self._runner: Path | None = None

    def debug(self) -> str:
        return (
            f"payload={self.payload} opened={self.opened} files={self.files} "
            f"errors={self.errors} commands={self.commands}"
        )

    def __call__(self, cmd, **kwargs):
        if isinstance(cmd, (list, tuple)):
            argv = [str(part) for part in cmd]
        else:
            argv = [str(cmd)]
        self.commands.append(argv)
        text = " ".join(argv)
        if "do javascript" in text:
            match = _POSIX.search(text)
            if match is None:
                raise AssertionError(f"osascript command has no JSX path: {text}")
            path = Path(match.group(1))
            if path.exists():
                self.execute(path)
        return subprocess.CompletedProcess(argv, 0, stdout="SUCCESS", stderr="")

    def execute(self, path: Path) -> None:
        # The drivers overwrite one temp_run.jsx per country, so identity is
        # the bytes osascript would read, not the path.
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in self._digests:
            return
        self._digests.add(digest)
        if self._runner is None:
            raise RuntimeError("JSX runner was not installed")
        out = self._runner.with_name("jsx-result.json")
        completed = self._real_run(
            ["node", str(self._runner), str(path), str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "node failed while evaluating JSX "
                f"{path}: {completed.stderr.strip()}"
            )
        result = json.loads(out.read_text(encoding="utf-8"))
        if result.get("payload"):
            self.payload = 1
        self.files.extend(result.get("files") or [])
        self.opened.extend(result.get("opened") or [])
        if result.get("err"):
            self.errors.append(f"{path.name}: {result['err']}")

    def install(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        runner = directory / "run-jsx.js"
        runner.write_text(_NODE, encoding="utf-8")
        self._runner = runner

    def sweep(self, root: Path) -> None:
        """Evaluate JSX files the tool wrote but did not pass to osascript."""
        if not root.exists():
            return
        for path in sorted(root.rglob("*.jsx")):
            self.execute(path)
