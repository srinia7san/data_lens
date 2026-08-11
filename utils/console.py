"""
Pretty console logger for the DA pipeline.

Provides colorful, structured output for each LangGraph node so you can
follow the pipeline's progress at a glance.
"""

import textwrap
import time
import sys
from datetime import datetime

# Reconfigure stdout/stderr to UTF-8 on Windows to prevent 'charmap' codec errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── ANSI color codes ──────────────────────────────────────────────────────────
_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"

_CYAN    = "\033[96m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_MAGENTA = "\033[95m"
_RED     = "\033[91m"
_BLUE    = "\033[94m"
_WHITE   = "\033[97m"

# ── Box-drawing characters ────────────────────────────────────────────────────
_H  = "─"
_TL = "╭"
_TR = "╮"
_BL = "╰"
_BR = "╯"
_V  = "│"

_WIDTH = 80

# ── Node → (icon, color) mapping ─────────────────────────────────────────────
_NODE_STYLES = {
    "schema":       ("🗄️ ", _CYAN),
    "generate_sql": ("🤖", _MAGENTA),
    "validate_sql": ("✅", _GREEN),
    "exec_sql":     ("⚡", _YELLOW),
    "answer_node":  ("💡", _BLUE),
}

# Track timing per node
_timers: dict[str, float] = {}


def _bar(char_l: str, char_r: str, color: str, title: str = "") -> str:
    """Draw a horizontal bar with an optional centered title."""
    if title:
        padding = _WIDTH - len(title) - 4  # 4 = 2 border + 2 spaces
        left = padding // 2
        right = padding - left
        return f"{color}{char_l}{_H * left} {_BOLD}{title}{_RESET}{color} {_H * right}{char_r}{_RESET}"
    return f"{color}{char_l}{_H * (_WIDTH - 2)}{char_r}{_RESET}"


def _wrap(text: str, indent: int = 4, max_width: int = _WIDTH - 6) -> str:
    """Word-wrap text with indent."""
    lines = text.split("\n")
    wrapped = []
    prefix = " " * indent
    for line in lines:
        if len(line) <= max_width:
            wrapped.append(f"{prefix}{line}")
        else:
            for sub in textwrap.wrap(line, width=max_width):
                wrapped.append(f"{prefix}{sub}")
    return "\n".join(wrapped)


def node_start(node_name: str, detail: str = "") -> None:
    """Call at the start of a node to print a header."""
    _timers[node_name] = time.time()
    icon, color = _NODE_STYLES.get(node_name, ("⚙️ ", _WHITE))
    ts = datetime.now().strftime("%H:%M:%S")

    print()
    print(_bar(_TL, _TR, color, f"{icon}  {node_name.upper()}"))
    print(f"{color}{_V}{_RESET}  {_DIM}started at {ts}{_RESET}")
    if detail:
        print(f"{color}{_V}{_RESET}")
        print(f"{color}{_V}{_RESET}  {detail}")
    print(f"{color}{_V}{_RESET}")


def node_detail(node_name: str, label: str, value: str, truncate: int = 500) -> None:
    """Print a labeled detail line inside a node box."""
    _, color = _NODE_STYLES.get(node_name, ("⚙️ ", _WHITE))
    display = value if len(value) <= truncate else value[:truncate] + f" {_DIM}... ({len(value)} chars total){_RESET}"
    print(f"{color}{_V}{_RESET}  {_BOLD}{label}:{_RESET}")
    print(_wrap(display))
    print(f"{color}{_V}{_RESET}")


def node_end(node_name: str, summary: str = "") -> None:
    """Call at the end of a node to print a footer with elapsed time."""
    elapsed = time.time() - _timers.pop(node_name, time.time())
    _, color = _NODE_STYLES.get(node_name, ("⚙️ ", _WHITE))

    if summary:
        print(f"{color}{_V}{_RESET}  {_GREEN}✓{_RESET} {summary}")
    print(f"{color}{_V}{_RESET}  {_DIM}completed in {elapsed:.2f}s{_RESET}")
    print(_bar(_BL, _BR, color))
    print()


def pipeline_start(question: str) -> None:
    """Print the pipeline header."""
    print()
    print(f"{_BOLD}{_CYAN}{'=' * _WIDTH}{_RESET}")
    print(f"{_BOLD}{_CYAN}  🚀  DATA ANALYST PIPELINE{_RESET}")
    print(f"{_CYAN}{'=' * _WIDTH}{_RESET}")
    print()
    print(f"  {_BOLD}Question:{_RESET}")
    print(_wrap(question, indent=4, max_width=_WIDTH - 8))
    print()
    print(f"{_CYAN}{'─' * _WIDTH}{_RESET}")


def pipeline_end(result: dict) -> None:
    """Print the pipeline result summary."""
    print()
    print(f"{_BOLD}{_GREEN}{'=' * _WIDTH}{_RESET}")
    print(f"{_BOLD}{_GREEN}  ✅  PIPELINE COMPLETE{_RESET}")
    print(f"{_GREEN}{'=' * _WIDTH}{_RESET}")
    print()

    if result.get("generated_query"):
        print(f"  {_BOLD}SQL Query:{_RESET}")
        print(_wrap(result["generated_query"]))
        print()

    if result.get("result"):
        rows = result["result"].get("rows", [])
        print(f"  {_BOLD}Result:{_RESET} {len(rows)} row(s) returned")
        # Show first 5 rows
        for i, row in enumerate(rows[:5]):
            print(f"    {_DIM}Row {i+1}:{_RESET} {row}")
        if len(rows) > 5:
            print(f"    {_DIM}... and {len(rows) - 5} more rows{_RESET}")
        print()

    if result.get("answer"):
        print(f"  {_BOLD}Answer:{_RESET}")
        print(_wrap(result["answer"]))
        print()

    print(f"{_GREEN}{'=' * _WIDTH}{_RESET}")
    print()
