#!/usr/bin/env python3
"""Command-line extractor for World of Tanks vegetation collision meshes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from destructibles import load_vegetation_densities, resource_path_for
from srt_collision import (
    bbox,
    combine_meshes,
    parse_srt,
    resolve_srt_path,
    write_json,
    write_obj,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract SRT draw calls marked as COLLISION into OBJ or JSON."
    )
    parser.add_argument("--packages", default="./packages", help="Path to unpacked merged packages.")
    parser.add_argument(
        "--object",
        required=True,
        help="Vegetation resource path or SRT stem, for example vegetation/Broadleaves/Poplar/Poplar_12m.",
    )
    parser.add_argument("--out", required=True, help="Output .obj or .json path.")
    parser.add_argument(
        "--lod",
        type=int,
        default=None,
        help="LOD to extract. Defaults to the lowest LOD that has a selected collision mesh.",
    )
    parser.add_argument(
        "--include-solid",
        action="store_true",
        help="Also include draw calls whose render-state name/kind is SOLID.",
    )
    args = parser.parse_args(argv)

    try:
        source = resolve_srt_path(args.packages, args.object)
        densities = load_vegetation_densities(args.packages)
        resource_path = resource_path_for(args.packages, source)
        density = densities.get(resource_path)
        metadata = {"density": density} if density is not None else {}

        srt = parse_srt(source)
        meshes = srt.collision_meshes(lod=args.lod, include_solid=args.include_solid)
        if not meshes:
            print(f"No COLLISION mesh found: {source.as_posix()}", file=sys.stderr)
            return 2

        out = Path(args.out)
        if out.suffix.lower() == ".json":
            write_json(out, meshes, metadata=metadata)
        else:
            write_obj(out, meshes, metadata=metadata)

        vertices, triangles = combine_meshes(meshes)
        mins, maxs = bbox(vertices)
        lods = sorted({mesh.lod for mesh in meshes})
        print(f"source: {source.as_posix()}")
        print(f"lods: {','.join(str(lod) for lod in lods)}")
        print(f"vertices: {len(vertices)}")
        print(f"triangles: {len(triangles)}")
        if density is not None:
            print(f"density: {density:g}")
        print(
            "bbox: "
            f"min=({mins[0]:.6g}, {mins[1]:.6g}, {mins[2]:.6g}) "
            f"max=({maxs[0]:.6g}, {maxs[1]:.6g}, {maxs[2]:.6g})"
        )
        print(f"wrote: {out.as_posix()}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
