#!/usr/bin/env python3
"""Local code visualization server for Python DSA solutions.

Security note: executes user-provided Python code locally in a restricted builtins
environment. This is for personal/local use, not for untrusted multi-user hosting.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import io
import json
import subprocess
import sys
import textwrap
import time
import traceback
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PORT = 8010
TIMEOUT_SECONDS = 3
MAX_STEPS = 3000

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"


class UnsafeCodeError(Exception):
    pass


def ensure_safe_ast(code: str) -> None:
    tree = ast.parse(code)
    banned_nodes = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.Raise, ast.Try)

    for node in ast.walk(tree):
        if isinstance(node, banned_nodes):
            raise UnsafeCodeError(f"Unsupported construct for visualizer: {node.__class__.__name__}")

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"open", "exec", "eval", "compile", "input", "__import__"}:
                raise UnsafeCodeError(f"Blocked call: {node.func.id}()")


def preprocess_user_code(code: str) -> str:
    """Normalize pasted snippets (especially LeetCode-style indentation)."""
    return textwrap.dedent(code).strip("\n")


ALLOWED_BUILTINS: dict[str, Any] = {
    "__build_class__": builtins.__build_class__,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "pow": pow,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "object": object,
    "zip": zip,
}

TYPING_ALIASES: dict[str, Any] = {
    "List": list,
    "Dict": dict,
    "Set": set,
    "Tuple": tuple,
    "Optional": object,
    "Any": object,
}


def repr_short(value: Any, limit: int = 120) -> str:
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def serializable_locals(frame_locals: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in frame_locals.items():
        if k.startswith("__"):
            continue
        out[k] = repr_short(v)
    return out


def build_loop_line_set(code: str) -> set[int]:
    tree = ast.parse(code)
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)) and getattr(node, "lineno", None):
            lines.add(node.lineno)
    return lines


def pick_callable(exec_scope: dict[str, Any], function_name: str | None) -> Any:
    if function_name:
        fn = exec_scope.get(function_name)
        if callable(fn):
            return fn

        solution_cls = exec_scope.get("Solution")
        if isinstance(solution_cls, type) and hasattr(solution_cls, function_name):
            return getattr(solution_cls(), function_name)

        raise ValueError(f"Function '{function_name}' was not found (top-level or in class Solution)")

    callables = []
    for key, val in exec_scope.items():
        if key.startswith("__"):
            continue
        if key in TYPING_ALIASES:
            continue
        if callable(val) and not isinstance(val, type):
            callables.append((key, val))

    if len(callables) == 1:
        return callables[0][1]
    if len(callables) > 1:
        names = ", ".join(name for name, _ in callables)
        raise ValueError(f"Multiple callables found ({names}). Please specify function name.")

    # LeetCode pattern: class Solution with one public method.
    solution_cls = exec_scope.get("Solution")
    if isinstance(solution_cls, type):
        methods = []
        for name, val in solution_cls.__dict__.items():
            if name.startswith("_"):
                continue
            if callable(val):
                methods.append(name)
        if len(methods) == 1:
            return getattr(solution_cls(), methods[0])
        if len(methods) > 1:
            names = ", ".join(methods)
            raise ValueError(f"Multiple methods in Solution ({names}). Please specify function name.")
    return None


def run_trace(payload: dict[str, Any]) -> dict[str, Any]:
    code = preprocess_user_code(payload.get("code", ""))
    function_name = payload.get("function_name") or None
    raw_args = payload.get("args")

    start = time.time()
    steps: list[dict[str, Any]] = []
    loop_lines = build_loop_line_set(code)
    loop_hits: dict[int, int] = {}
    event_counter = 0
    started_target = function_name is None

    ensure_safe_ast(code)

    compiled = compile(code, "<user_code>", "exec")
    globals_scope = {"__builtins__": ALLOWED_BUILTINS, "__name__": "__main__", **TYPING_ALIASES}
    locals_scope: dict[str, Any] = {}

    exec(compiled, globals_scope, locals_scope)
    merged_scope = {**globals_scope, **locals_scope}
    target = pick_callable(merged_scope, function_name)

    args = []
    if raw_args:
        parsed = json.loads(raw_args)
        if not isinstance(parsed, list):
            raise ValueError("Args must be a JSON array, e.g. [5, [1,2,3]]")
        args = parsed

    call_args = args
    if target is not None:
        # Support method-style snippets pasted without class wrapper:
        # def twoSum(self, nums, target): ...
        try:
            sig = inspect.signature(target)
            params = list(sig.parameters.values())
            if params and params[0].name == "self":
                call_args = [object(), *args]
        except Exception:
            call_args = args

    source_lines = code.splitlines()
    previous_locals: dict[str, str] = {}

    def tracer(frame, event, arg):
        nonlocal event_counter, started_target, previous_locals

        if time.time() - start > TIMEOUT_SECONDS:
            raise TimeoutError(f"Execution exceeded {TIMEOUT_SECONDS}s time limit")

        if target is not None and not started_target:
            if event == "call" and frame.f_code.co_name == target.__name__:
                started_target = True
            else:
                return tracer

        if event not in {"line", "return"}:
            return tracer

        if event_counter >= MAX_STEPS:
            raise RuntimeError(f"Step limit reached ({MAX_STEPS}). Possible infinite loop.")

        lineno = frame.f_lineno
        source = source_lines[lineno - 1].rstrip() if 1 <= lineno <= len(source_lines) else ""

        current_locals = serializable_locals(frame.f_locals)
        changed = {}
        for key, value in current_locals.items():
            if previous_locals.get(key) != value:
                changed[key] = value

        deleted = [k for k in previous_locals.keys() if k not in current_locals]
        previous_locals = current_locals

        loop_iteration = None
        if lineno in loop_lines and event == "line":
            loop_hits[lineno] = loop_hits.get(lineno, 0) + 1
            loop_iteration = loop_hits[lineno]

        step = {
            "idx": event_counter + 1,
            "event": event,
            "line": lineno,
            "source": source,
            "changed": changed,
            "deleted": deleted,
            "locals": current_locals,
        }
        if loop_iteration is not None:
            step["loop_iteration"] = loop_iteration
        if event == "return":
            step["return_value"] = repr_short(arg)

        steps.append(step)
        event_counter += 1
        return tracer

    stdout_buffer = io.StringIO()
    with redirect_stdout(stdout_buffer):
        sys.settrace(tracer)
        result_value = None
        try:
            if target is not None:
                result_value = target(*call_args)
        finally:
            sys.settrace(None)

    return {
        "ok": True,
        "result": {
            "return_value": repr_short(result_value),
            "stdout": stdout_buffer.getvalue(),
            "steps": steps,
            "summary": {
                "total_steps": len(steps),
                "loop_lines": sorted(loop_lines),
            },
        },
    }


def run_worker() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        result = run_trace(payload)
        sys.stdout.write(json.dumps(result))
        return 0
    except Exception as exc:
        err = {
            "ok": False,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(limit=6),
            },
        }
        sys.stdout.write(json.dumps(err))
        return 0


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self._html(INDEX_FILE.read_text(encoding="utf-8"))
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/visualize":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                self._json(400, {"ok": False, "error": {"message": "Empty request body"}})
                return
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": {"message": "Invalid JSON payload"}})
            return

        try:
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker"],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=TIMEOUT_SECONDS + 1,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self._json(
                408,
                {"ok": False, "error": {"type": "Timeout", "message": f"Execution timed out after ~{TIMEOUT_SECONDS}s"}},
            )
            return

        if not proc.stdout:
            self._json(500, {"ok": False, "error": {"message": "Worker returned no output"}})
            return

        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self._json(500, {"ok": False, "error": {"message": "Worker returned invalid JSON", "raw": proc.stdout[:2000]}})
            return

        status = 200 if result.get("ok") else 400
        self._json(status, result)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving Visualizer on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        raise SystemExit(run_worker())
    main()
