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


def load_vegetation_lists(packages: str | Path) -> dict[str, set[str]]:
    vegetation = Path(packages) / "vegetation"
    return {
        "bushes": _load_name_list(vegetation / "bushes.xml"),
        "grassBushes": _load_name_list(vegetation / "grassBushes.xml"),
    }


def vegetation_metadata(
    packages: str | Path,
    source_path: str | Path,
    has_collision_mesh: bool,
) -> dict:
    densities = load_vegetation_densities(packages)
    vegetation_lists = load_vegetation_lists(packages)
    resource_path = resource_path_for(packages, source_path)
    stem = Path(resource_path).stem.lower()
    density = densities.get(resource_path)

    if stem in vegetation_lists["grassBushes"]:
        vegetation_list = "grassBushes"
        camouflage_affects = False
        reason = "listed_in_grassBushes"
    elif stem in vegetation_lists["bushes"]:
        vegetation_list = "bushes"
        camouflage_affects = bool(has_collision_mesh and density is not None)
        reason = "listed_in_bushes" if camouflage_affects else "missing_collision_or_density"
    else:
        vegetation_list = "unlisted"
        if has_collision_mesh and density is not None:
            camouflage_affects = True
            reason = "collision_mesh_with_destructibles_density"
        else:
            camouflage_affects = None
            reason = "not_enough_metadata"

    if camouflage_affects is True:
        camouflage_density = density
    elif camouflage_affects is False:
        camouflage_density = 0.0
    else:
        camouflage_density = None

    return {
        "resource_path": resource_path,
        "vegetation_list": vegetation_list,
        "destructibles_density": density,
        "camouflage_affects": camouflage_affects,
        "camouflage_density": camouflage_density,
        "camouflage_reason": reason,
    }


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


def _load_name_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        match.group(1).lower()
        for match in re.finditer(r"<([^!?/][^/>\s]*)\s*/>", text)
        if match.group(1) != "root"
    }
