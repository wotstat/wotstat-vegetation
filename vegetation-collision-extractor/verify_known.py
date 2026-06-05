#!/usr/bin/env python3
"""Verify extraction on vegetation objects known to have collision meshes."""

from __future__ import annotations

import argparse
from pathlib import Path

from destructibles import load_vegetation_densities, resource_path_for
from srt_collision import bbox, combine_meshes, parse_srt, resolve_srt_path, write_obj


KNOWN_OBJECTS = [
    "vegetation/Broadleaves/Chestnut/Chestnut_10m",
    "vegetation/Broadleaves/Poplar/Poplar_12m",
    "vegetation/Broadleaves/Poplar/Poplar_21m",
    "vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_5m",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Print stats for known vegetation collision meshes.")
    parser.add_argument("--packages", default="./packages", help="Path to unpacked merged packages.")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional directory where OBJ files for the known meshes will be written.",
    )
    args = parser.parse_args()

    densities = load_vegetation_densities(args.packages)
    failures = 0
    for object_name in KNOWN_OBJECTS:
        try:
            source = resolve_srt_path(args.packages, object_name)
            density = densities.get(resource_path_for(args.packages, source))
            srt = parse_srt(source)
            meshes = srt.collision_meshes()
            if not meshes:
                raise RuntimeError("no COLLISION mesh found")

            vertices, triangles = combine_meshes(meshes)
            mins, maxs = bbox(vertices)
            lods = ",".join(str(lod) for lod in sorted({mesh.lod for mesh in meshes}))
            source_rel = source.as_posix()
            print(object_name)
            print(f"  source: {source_rel}")
            print(f"  lods: {lods}")
            print(f"  vertices: {len(vertices)}")
            print(f"  triangles: {len(triangles)}")
            if density is not None:
                print(f"  density: {density:g}")
            print(
                "  bbox: "
                f"min=({mins[0]:.6g}, {mins[1]:.6g}, {mins[2]:.6g}) "
                f"max=({maxs[0]:.6g}, {maxs[1]:.6g}, {maxs[2]:.6g})"
            )

            if args.out_dir:
                out = Path(args.out_dir) / f"{Path(object_name).name}.obj"
                metadata = {"density": density} if density is not None else {}
                write_obj(out, meshes, metadata=metadata)
                print(f"  wrote: {out.as_posix()}")
        except Exception as exc:
            failures += 1
            print(object_name)
            print(f"  error: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
