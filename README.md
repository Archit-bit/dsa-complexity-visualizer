# DSA Tools

This folder now has two apps:

- Complexity Estimator (CLI + simple web):
  - `complexity_analyzer.py`
  - `web_app/`
- Code Execution Visualizer (new):
  - `visualizer_app/`

## 1) Complexity Estimator CLI

```bash
python3 complexity_analyzer.py
```

## 2) Complexity Estimator Web

```bash
python3 web_app/server.py
```

Open: http://127.0.0.1:8000

## 3) Code Execution Visualizer Web

```bash
python3 visualizer_app/server.py
```

Open: http://127.0.0.1:8010

### Visualizer Features

- Step-by-step execution timeline
- Loop iteration counter (per `for` / `while` line)
- Variable change tracking on each step
- Return value capture
- Stdout capture (`print` output)
- Timeout and max-step guard for runaway code

### Input Format for Visualizer

- Paste Python code.
- If there is exactly one function, function name can be empty.
- Args must be JSON array, e.g.:
  - `[[2,7,11,15], 9]`
  - `[5]`

### Notes

- Visualizer currently supports Python code execution.
- It uses lightweight AST restrictions for safer local usage and blocks imports/file I/O/eval-like calls.
- Designed for local learning, not untrusted multi-user hosting.
