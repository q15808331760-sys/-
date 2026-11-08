#!/usr/bin/env python3
"""Emit the exact extracted Godot startup sources into Actions logs for diagnosis."""
from pathlib import Path

root = Path("Pokemon_Battle_Lab_Remake")
targets = [
    root / "project.godot",
    root / "scenes" / "main.tscn",
    root / "scripts" / "main.gd",
]
for path in targets:
    if not path.is_file():
        raise SystemExit(f"Missing startup source: {path}")
    print(f"::group::SOURCE {path.as_posix()}")
    print(path.read_text(encoding="utf-8"))
    print(f"::endgroup::")
