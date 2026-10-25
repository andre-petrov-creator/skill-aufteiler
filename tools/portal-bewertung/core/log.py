"""Zentrales Logging — stumm by default, mit Verbose-Flag auf stderr.

Wichtig: Logs gehen IMMER auf stderr, NIE auf stdout. stdout ist für das
JSON-Result reserviert.
"""
from __future__ import annotations

import sys

_VERBOSE = False


def set_verbose(verbose: bool) -> None:
    global _VERBOSE
    _VERBOSE = verbose


def log(msg: str) -> None:
    if _VERBOSE:
        print(f">>> {msg}", flush=True, file=sys.stderr)
