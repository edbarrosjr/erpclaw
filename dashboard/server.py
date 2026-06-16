#!/usr/bin/env python3
"""ERPClaw — Painel operável (local).

A zero-dependency, stdlib-only bridge between a static web UI and the same
`scripts/db_query.py` router the AI assistant drives. The browser cannot shell
out, so this server does it: it validates an action against the bundled
allowlist, execs `python3 scripts/db_query.py --action <name> [--flags]`, and
returns the parsed JSON. It binds to localhost only — it operates real books.

Run:
    python3 dashboard/server.py            # http://127.0.0.1:8787
    python3 dashboard/server.py --port 9000
    ERPCLAW_DASH_PORT=9000 python3 dashboard/server.py

No pip install. Same Python that runs the foundation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_QUERY = ROOT / "scripts" / "db_query.py"
ERPCLAW_BIN = ROOT / "bin" / "erpclaw"
INDEX_HTML = HERE / "index.html"

# Action names are verb-object kebab-case. Anything else never reaches a shell.
ACTION_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$")
ACTION_TIMEOUT_S = 120
MAX_BODY = 2 * 1024 * 1024

_ACTION_CACHE: set[str] | None = None


def discover_actions() -> set[str]:
    """The allowlist: every action `bin/erpclaw list` can resolve from SKILL.md.

    Cached for the process lifetime. Falls back to an empty set (the handler
    then accepts any well-formed action name) only if discovery fails entirely.
    """
    global _ACTION_CACHE
    if _ACTION_CACHE is not None:
        return _ACTION_CACHE
    actions: set[str] = set()
    try:
        out = subprocess.run(
            [sys.executable, str(ERPCLAW_BIN), "list"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        ).stdout
        for line in out.splitlines():
            m = re.match(r"^\s{2,}([a-z][a-z0-9-]+)\s*$", line)
            if m and ACTION_RE.match(m.group(1)):
                actions.add(m.group(1))
    except Exception as exc:  # noqa: BLE001 - discovery is best-effort
        print(f"[dashboard] action discovery failed: {exc}", file=sys.stderr)
    _ACTION_CACHE = actions
    return actions


def extract_json(stdout: str):
    """db_query.py prints JSON to stdout, sometimes after human summary lines.

    Return the first decodable JSON value at or after the first '{' or '['.
    """
    for i, ch in enumerate(stdout):
        if ch in "{[":
            try:
                obj, _ = json.JSONDecoder().raw_decode(stdout[i:])
                return obj
            except json.JSONDecodeError:
                continue
    return None


def run_action(action: str, args: dict, confirm: bool) -> dict:
    if not ACTION_RE.match(action or ""):
        return {"ok": False, "error": f"invalid action name: {action!r}"}
    allow = discover_actions()
    if allow and action not in allow:
        return {"ok": False, "error": f"unknown action: {action} (not in allowlist)"}

    argv = [sys.executable, str(DB_QUERY), "--action", action]
    for key, value in (args or {}).items():
        if not re.match(r"^[a-z][a-z0-9-]*$", str(key)):
            return {"ok": False, "error": f"invalid arg name: {key!r}"}
        if value is None or value == "":
            continue
        if value is True:
            argv.append(f"--{key}")
        elif value is False:
            continue
        else:
            argv += [f"--{key}", str(value)]
    if confirm:
        argv.append("--user-confirmed")

    try:
        proc = subprocess.run(
            argv, cwd=str(ROOT), capture_output=True, text=True,
            timeout=ACTION_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"action timed out after {ACTION_TIMEOUT_S}s"}
    except OSError as exc:
        return {"ok": False, "error": f"failed to exec router: {exc}"}

    parsed = extract_json(proc.stdout)
    ok = proc.returncode == 0 and not (
        isinstance(parsed, dict) and parsed.get("status") == "error"
    )
    return {
        "ok": ok,
        "action": action,
        "returncode": proc.returncode,
        "parsed": parsed,
        "stdout": proc.stdout[-20000:],
        "stderr": proc.stderr[-20000:],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ERPClawDash/1.0"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def log_message(self, fmt, *a):  # quieter console
        sys.stderr.write("[dashboard] " + (fmt % a) + "\n")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            try:
                self._send(200, INDEX_HTML.read_bytes(), "text/html; charset=utf-8")
            except OSError as exc:
                self._json(500, {"error": str(exc)})
            return
        if self.path == "/api/actions":
            self._json(200, {"actions": sorted(discover_actions())})
            return
        if self.path == "/api/health":
            self._json(200, {"ok": True, "root": str(ROOT), "db_query": DB_QUERY.exists()})
            return
        if self.path.startswith("/assets/"):
            name = self.path[len("/assets/"):].split("?", 1)[0]
            if re.fullmatch(r"[A-Za-z0-9._-]+", name or ""):
                fp = ROOT / "assets" / name
                if fp.is_file():
                    ctype = {
                        ".svg": "image/svg+xml", ".png": "image/png",
                        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".webp": "image/webp", ".gif": "image/gif",
                        ".ico": "image/x-icon",
                    }.get(fp.suffix.lower(), "application/octet-stream")
                    self._send(200, fp.read_bytes(), ctype)
                    return
            self._json(404, {"error": "asset not found"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/api/action":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._json(400, {"ok": False, "error": "bad content length"})
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._json(400, {"ok": False, "error": f"bad json: {exc}"})
            return
        result = run_action(
            payload.get("action", ""),
            payload.get("args", {}) or {},
            bool(payload.get("confirm", False)),
        )
        self._json(200, result)


def main() -> int:
    ap = argparse.ArgumentParser(description="ERPClaw local operable dashboard")
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("ERPCLAW_DASH_PORT", "8787")))
    ap.add_argument("--host", default=os.environ.get("ERPCLAW_DASH_HOST", "127.0.0.1"))
    opts = ap.parse_args()

    if not DB_QUERY.exists():
        print(f"[dashboard] cannot find router at {DB_QUERY}", file=sys.stderr)
        return 1
    n = len(discover_actions())
    httpd = ThreadingHTTPServer((opts.host, opts.port), Handler)
    print(f"ERPClaw dashboard → http://{opts.host}:{opts.port}  "
          f"({n} actions, router: {DB_QUERY})")
    print("DB: ~/.openclaw/erpclaw/data.sqlite   (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[dashboard] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
