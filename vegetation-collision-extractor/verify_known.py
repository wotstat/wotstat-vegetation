#!/usr/bin/env python3
"""Verify extraction and camouflage classification on known vegetation objects."""

from __future__ import annotations

import argparse
from pathlib import Path

from destructibles import vegetation_metadata
from srt_collision import bbox, combine_meshes, parse_srt, resolve_srt_path, write_obj


KNOWN_OBJECTS = [
    ("vegetation/Broadleaves/Chestnut/Chestnut_10m", True),
    ("vegetation/Broadleaves/Poplar/Poplar_12m", True),
    ("vegetation/Broadleaves/Poplar/Poplar_21m", True),
    ("vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_5m", True),
    ("vegetation/Broadleaves/DryTree/DryTree_Bush_var2", False),
    ("vegetation/Conifers/Pine_Young/Pine_Young_almoust_2m", False),
    ("vegetation/Broadleaves/Shrubs/Hawthorn/Hawthorn_03", False),
    ("vegetation/Broadleaves/Shrubs/Bush_Wild_Autumn/Bush_Wild_Autumn_5m", True),
    ("vegetation/Broadleaves/Oak_dry/Oak_dry_25m", True),
    ("vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_2m", True),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print stats and camouflage classification for known vegetation collision meshes."
    )
    parser.add_argument("--packages", default="./packages", help="Path to unpacked merged packages.")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional directory where OBJ files for the known meshes will be written.",
    )
    args = parser.parse_args()

    failures = 0
    for object_name, expected_camo in KNOWN_OBJECTS:
        try:
            source = resolve_srt_path(args.packages, object_name)
            srt = parse_srt(source)
            meshes = srt.collision_meshes()
            if not meshes:
                raise RuntimeError("no COLLISION mesh found")
            metadata = vegetation_metadata(args.packages, source, has_collision_mesh=bool(meshes))
            if metadata["camouflage_affects"] is not expected_camo:
                raise RuntimeError(
                    f"camouflage mismatch: expected {expected_camo}, got {metadata['camouflage_affects']}"
                )

            vertices, triangles = combine_meshes(meshes)
            mins, maxs = bbox(vertices)
            lods = ",".join(str(lod) for lod in sorted({mesh.lod for mesh in meshes}))
            source_rel = source.as_posix()
            print(object_name)
            print(f"  source: {source_rel}")
            print(f"  lods: {lods}")
            print(f"  vertices: {len(vertices)}")
            print(f"  triangles: {len(triangles)}")
            if metadata["destructibles_density"] is not None:
                print(f"  destructibles_density: {metadata['destructibles_density']:g}")
            print(f"  vegetation_list: {metadata['vegetation_list']}")
            print(f"  camouflage_affects: {metadata['camouflage_affects']}")
            if metadata["camouflage_density"] is not None:
                print(f"  camouflage_density: {metadata['camouflage_density']:g}")
            print(f"  camouflage_reason: {metadata['camouflage_reason']}")
            print(
                "  bbox: "
                f"min=({mins[0]:.6g}, {mins[1]:.6g}, {mins[2]:.6g}) "
                f"max=({maxs[0]:.6g}, {maxs[1]:.6g}, {maxs[2]:.6g})"
            )

            if args.out_dir:
                out = Path(args.out_dir) / f"{Path(object_name).name}.obj"
                write_obj(out, meshes, metadata=metadata)
                print(f"  wrote: {out.as_posix()}")
        except Exception as exc:
            failures += 1
            print(object_name)
            print(f"  error: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
