#!/usr/bin/env python3
"""Helpers for reading vegetation density from destructibles.xml."""

from __future__ import annotations

import re
from pathlib import Path


ENTRY_RE = re.compile(r"<entry>\s*(.*?)\s*</entry>", re.S)
TEXT_TAG_RE = r"<{tag}>\s*([^<]+?)\s*</{tag}>"


def load_vegetation_densities(packages: str | Path) -> dict[str, float]:
    path = Path(packages) / "scripts" / "destructibles.xml"
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8", errors="replace")
    densities: dict[str, float] = {}
    for block in ENTRY_RE.findall(text):
        filename = _tag_text(block, "filename")
        density = _tag_text(block, "density")
        if not filename or not density or not filename.lower().startswith("vegetation/"):
            continue
        try:
            densities[_normalize_resource_path(filename)] = float(density)
        except ValueError:
            continue
    return densities


def resource_path_for(packages: str | Path, source_path: str | Path) -> str:
    packages_path = Path(packages).resolve()
    source = Path(source_path).resolve()
    try:
        return _normalize_resource_path(source.relative_to(packages_path).as_posix())
    except ValueError:
        return _normalize_resource_path(Path(source_path).as_posix())


def _tag_text(block: str, tag: str) -> str | None:
    match = re.search(TEXT_TAG_RE.format(tag=re.escape(tag)), block)
    if not match:
        return None
    return match.group(1).strip()


def _normalize_resource_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if value.startswith("packages/"):
        value = value[len("packages/") :]
    return value.lower()

