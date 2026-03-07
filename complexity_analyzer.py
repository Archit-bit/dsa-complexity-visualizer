#!/usr/bin/env python3
"""
A small, educational complexity analyzer for pasted DSA solutions.
It uses lightweight heuristics and explains each inference.
"""

from __future__ import annotations

import math
import re
import textwrap


LINEAR_TOKENS = [
    "for",
    "while",
    "map(",
    "filter(",
    "reduce(",
    "sum(",
]

SORT_TOKENS = ["sort(", "sorted(", "Collections.sort", "Arrays.sort", "std::sort", ".sort("]

LOG_TOKENS = [
    "// 2",
    "/= 2",
    "*= 2",
    "<<= 1",
    ">>= 1",
    "mid =",
    "binary_search",
    "bisect",
]


class ComplexityResult:
    def __init__(self) -> None:
        self.time_terms: list[str] = []
        self.space_terms: list[str] = []
        self.explanations: list[str] = []

    def add_time(self, term: str, reason: str) -> None:
        self.time_terms.append(term)
        self.explanations.append(f"Time: {reason} -> {term}")

    def add_space(self, term: str, reason: str) -> None:
        self.space_terms.append(term)
        self.explanations.append(f"Space: {reason} -> {term}")


def normalize(code: str) -> str:
    # Remove multiline comments and single-line comments.
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"#.*", "", code)
    code = re.sub(r"//.*", "", code)
    return code


def max_loop_nesting(code: str) -> int:
    """Approximate nesting by indentation and braces."""
    lines = [ln.rstrip() for ln in code.splitlines() if ln.strip()]
    depth = 0
    best = 0
    stack: list[int] = []

    for ln in lines:
        stripped = ln.strip()
        indent = len(ln) - len(ln.lstrip())

        while stack and indent <= stack[-1] and not stripped.startswith(("elif", "else", "except", "finally")):
            stack.pop()

        is_loop = bool(re.search(r"\b(for|while)\b", stripped))
        if is_loop:
            stack.append(indent)
            depth = len(stack)
            best = max(best, depth)

        # braces hint at closure of block in C/Java/C++ style
        if "}" in stripped and stack:
            stack.pop()

    return max(best, 1 if re.search(r"\b(for|while)\b", code) else 0)


def detects_recursion(code: str) -> tuple[bool, bool]:
    """Return (has_recursion, appears_branching_recursion)."""
    funcs = set(re.findall(r"\bdef\s+(\w+)\s*\(|\b(?:int|long|void|bool|float|double|string|char|auto)\s+(\w+)\s*\(", code, flags=re.I))
    names = {name for pair in funcs for name in pair if name}

    for name in names:
        calls = re.findall(rf"\b{name}\s*\(", code)
        if len(calls) >= 2:  # declaration + at least one call
            recursive_calls = len(calls) - 1
            return True, recursive_calls >= 2

    # fallback for common explicit recursive patterns
    if "return " in code and re.search(r"\b\w+\(.*\)\s*\+\s*\w+\(", code):
        return True, True

    return False, False


def has_aux_structure(code: str) -> bool:
    patterns = [
        r"\[[^\]]*\]\s*\*\s*n",   # Python list init like [0] * n
        r"new\s+\w+\s*\[",         # Java/C++ array allocation
        r"vector<",
        r"ArrayList<",
        r"dict\(",
        r"\{\}",
        r"unordered_map",
        r"unordered_set",
        r"stack<",
        r"queue<",
    ]
    return any(re.search(p, code, flags=re.I) for p in patterns)


def has_slicing_or_copy(code: str) -> bool:
    return bool(
        re.search(r"\[[^\]]*:[^\]]*\]", code) or
        re.search(r"\.copy\s*\(", code) or
        re.search(r"copy\s*\(", code)
    )


def analyze(code: str) -> ComplexityResult:
    result = ComplexityResult()
    clean = normalize(code)
    lower = clean.lower()

    if not clean.strip():
        result.add_time("O(1)", "No executable content detected")
        result.add_space("O(1)", "No auxiliary structures detected")
        return result

    # Recursion first (often dominant in DSA).
    rec, branching = detects_recursion(clean)
    if rec and branching:
        result.add_time("O(2^n) (or worse depending on branching)", "Function appears to call itself multiple times per frame")
        result.add_space("O(n)", "Recursive call stack grows with depth")
    elif rec:
        result.add_time("O(n)", "Single recursive call chain over input size")
        result.add_space("O(n)", "Recursive call stack grows with depth")

    # Sorting hints.
    if any(tok.lower() in lower for tok in SORT_TOKENS):
        result.add_time("O(n log n)", "Sorting operation detected")

    # Logarithmic loop hints.
    if any(tok in lower for tok in LOG_TOKENS):
        result.add_time("O(log n)", "Loop/index appears to grow or shrink geometrically")

    # Loop nesting.
    nesting = max_loop_nesting(clean)
    if nesting == 1:
        result.add_time("O(n)", "One loop over data detected")
    elif nesting >= 2:
        term = "n^" + str(nesting)
        result.add_time(f"O({term})", f"Detected approximately {nesting} levels of nested loops")

    # Membership checks can lift complexity if inside loops.
    membership_like = re.search(r"\bif\s+.+\s+in\s+([A-Za-z_]\w*)", clean)
    if membership_like and membership_like.group(1) != "range" and "set(" not in lower and "unordered_set" not in lower:
        result.add_time("Potential O(n^2)", "Linear membership checks (`in` on list/array) may be inside iteration")

    # Space analysis.
    if has_aux_structure(clean):
        result.add_space("O(n)", "Auxiliary collection/array allocation detected")
    if has_slicing_or_copy(clean):
        result.add_space("O(n)", "Slicing/copy operation creates additional data")

    if not result.time_terms:
        result.add_time("O(1)", "No loops/recursion/sorting patterns found")
    if not result.space_terms:
        result.add_space("O(1)", "No obvious extra memory allocation patterns found")

    return result


def combine_terms(terms: list[str]) -> str:
    unique = []
    for t in terms:
        if t not in unique:
            unique.append(t)
    if len(unique) == 1:
        return unique[0]

    # Display all candidate terms and pick a rough dominant term.
    rank = {
        "O(1)": 0,
        "O(log n)": 1,
        "O(n)": 2,
        "O(n log n)": 3,
        "O(n^2)": 4,
        "O(n^3)": 5,
        "O(2^n) (or worse depending on branching)": 6,
        "Potential O(n^2)": 4,
    }

    def score(term: str) -> int:
        if term in rank:
            return rank[term]
        m = re.match(r"O\(n\^(\d+)\)", term)
        if m:
            return int(m.group(1)) + 2
        return 2

    dominant = max(unique, key=score)
    return f"Candidates: {', '.join(unique)} | Estimated dominant: {dominant}"


def read_multiline() -> str:
    print("Paste your DSA solution below. End input with a single line: END")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    print("=== DSA Complexity Explainer ===")
    print("This is a heuristic analyzer for learning, not a formal proof tool.\n")

    code = read_multiline()
    result = analyze(code)

    time_summary = combine_terms(result.time_terms)
    space_summary = combine_terms(result.space_terms)

    print("\n--- Result ---")
    print(f"Estimated Time Complexity: {time_summary}")
    print(f"Estimated Space Complexity: {space_summary}")

    print("\n--- How it was calculated ---")
    for i, exp in enumerate(result.explanations, 1):
        print(f"{i}. {exp}")

    print("\nTip: Compare this output with manual analysis and adjust edge cases.")


if __name__ == "__main__":
    main()
