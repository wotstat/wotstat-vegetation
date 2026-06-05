#!/usr/bin/env python3
"""Extract low-poly vegetation collision meshes from World of Tanks SRT files."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


RENDER_STATE_SIZE = 680
DRAW_CALL_SIZE = 40
LOD_TABLE_ENTRY_SIZE = 24
BONE_SIZE = 48

VF_DESC_OFFSET = 33
VF_DESC_SIZE = 13
STRIDE_BYTE_OFFSET = 663

WIND_DATA_SIZE = 1308
ADDITIONAL_DATA_SIZE = 31
HORIZONTAL_BILLBOARD_SIZE = 84
COLLISION_OBJECT_SIZE = 36

MATERIAL_NAME_OFFSET = 664
MATERIAL_KIND_OFFSET = 672


class SrtParseError(Exception):
    pass


class CollisionNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class RenderState:
    index: int
    stride: int
    name: str
    kind: str
    block: bytes


@dataclass
class Mesh:
    lod: int
    geom: int
    render_state: RenderState
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]
    source_path: Path

    @property
    def material_name(self) -> str:
        return self.render_state.name

    @property
    def material_kind(self) -> str:
        return self.render_state.kind


@dataclass
class SrtGeometry:
    path: Path
    strings: list[str]
    extents: tuple[float, float, float, float, float, float]
    speedtree_collision_object_count: int
    render_states: list[RenderState]
    meshes: list[Mesh]

    def collision_meshes(self, lod: int | None = None, include_solid: bool = False) -> list[Mesh]:
        names = {"COLLISION"}
        if include_solid:
            names.add("SOLID")

        meshes = [
            mesh
            for mesh in self.meshes
            if mesh.material_name in names or mesh.material_kind in names
        ]
        if not meshes:
            return []

        selected_lod = min(mesh.lod for mesh in meshes) if lod is None else lod
        return [mesh for mesh in meshes if mesh.lod == selected_lod]


class Reader:
    def __init__(self, data: bytes, path: Path):
        self.data = data
        self.path = path
        self.pos = 0
        self.endian = "<"

    def read_bytes(self, size: int) -> bytes:
        if self.pos < 0 or self.pos + size > len(self.data):
            raise SrtParseError(f"{self.path}: unexpected end of file at offset {self.pos}")
        result = self.data[self.pos : self.pos + size]
        self.pos += size
        return result

    def u32(self) -> int:
        return struct.unpack(self.endian + "I", self.read_bytes(4))[0]

    def f32(self) -> float:
        return struct.unpack(self.endian + "f", self.read_bytes(4))[0]

    def byte(self) -> int:
        return self.read_bytes(1)[0]

    def align4(self) -> None:
        self.pos = (self.pos + 3) & ~3


def parse_srt(path: str | Path) -> SrtGeometry:
    path = Path(path)
    reader = Reader(path.read_bytes(), path)

    header = _read_c_string(reader.data, 0)[0]
    if header != "SRT 06.0.0":
        raise SrtParseError(f"{path}: unsupported SRT header {header!r}")

    reader.pos = 16
    endian_byte = reader.byte()
    reader.byte()  # coordinate system
    reader.byte()  # texcoords flipped
    reader.byte()  # reserved
    reader.endian = "<" if endian_byte == 0 else ">"

    extents = struct.unpack_from(reader.endian + "6f", reader.data, reader.pos)
    reader.pos += 24

    reader.u32()  # LOD enabled
    reader.pos += 16  # four LOD distances
    reader.pos += WIND_DATA_SIZE
    reader.pos += ADDITIONAL_DATA_SIZE
    reader.align4()

    reader.pos += 16  # string table preamble
    strings = _parse_string_table(reader)

    speedtree_collision_object_count = reader.u32()
    reader.pos += speedtree_collision_object_count * COLLISION_OBJECT_SIZE

    _skip_billboards(reader)
    reader.pos += 20  # five user string refs

    render_states = _parse_render_states(reader, strings)
    descriptors = _parse_geometry_descriptors(reader)
    meshes = _parse_mesh_data(reader, descriptors, render_states, path)

    if reader.pos != len(reader.data):
        raise SrtParseError(
            f"{path}: parser stopped at {reader.pos}, file size is {len(reader.data)}"
        )

    return SrtGeometry(
        path=path,
        strings=strings,
        extents=extents,
        speedtree_collision_object_count=speedtree_collision_object_count,
        render_states=render_states,
        meshes=meshes,
    )


def resolve_srt_path(packages: str | Path, object_name: str) -> Path:
    packages = Path(packages)
    value = object_name.strip().replace("\\", "/")
    if not value:
        raise FileNotFoundError("empty vegetation object name")

    while value.startswith("./"):
        value = value[2:]
    if value.startswith("packages/"):
        value = value[len("packages/") :]

    candidates: list[Path] = []
    if "/" in value or value.lower().endswith(".srt"):
        resource = value if value.lower().endswith(".srt") else f"{value}.srt"
        candidates.append(packages / resource)

    if not candidates:
        stem = Path(value).stem.lower()
        candidates = [
            path
            for path in (packages / "vegetation").rglob("*.srt")
            if path.stem.lower() == stem
        ]

    existing = [path for path in candidates if path.exists()]
    if len(existing) == 1:
        return existing[0]
    if len(existing) > 1:
        paths = "\n".join(f"  {path.as_posix()}" for path in existing[:20])
        raise FileNotFoundError(f"ambiguous object name {object_name!r}; matches:\n{paths}")

    # Case-insensitive fallback for platforms with case-sensitive file systems.
    wanted = (value if value.lower().endswith(".srt") else f"{value}.srt").lower()
    matches = [
        path
        for path in (packages / "vegetation").rglob("*.srt")
        if path.relative_to(packages).as_posix().lower() == wanted
    ]
    if len(matches) == 1:
        return matches[0]

    raise FileNotFoundError(f"could not find SRT for {object_name!r} under {packages}")


def combine_meshes(meshes: Iterable[Mesh]) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    for mesh in meshes:
        base = len(vertices)
        vertices.extend(mesh.vertices)
        triangles.extend((a + base, b + base, c + base) for a, b, c in mesh.triangles)
    return vertices, triangles


def bbox(vertices: Iterable[tuple[float, float, float]]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    values = list(vertices)
    if not values:
        raise ValueError("cannot compute a bounding box for an empty mesh")
    mins = tuple(min(vertex[i] for vertex in values) for i in range(3))
    maxs = tuple(max(vertex[i] for vertex in values) for i in range(3))
    return mins, maxs


def write_obj(path: str | Path, meshes: list[Mesh], metadata: dict | None = None) -> None:
    path = Path(path)
    vertices, _triangles = combine_meshes(meshes)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# World of Tanks vegetation collision mesh\n")
        if meshes:
            handle.write(f"# source: {meshes[0].source_path.as_posix()}\n")
        handle.write(f"# vertices: {len(vertices)}\n")
        handle.write(f"# triangles: {sum(len(mesh.triangles) for mesh in meshes)}\n")
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    handle.write(f"# {key}: {value}\n")
        handle.write("\n")

        vertex_offset = 0
        for mesh in meshes:
            group_name = f"lod{mesh.lod}_geom{mesh.geom}_{_safe_name(mesh.material_name or mesh.material_kind)}"
            handle.write(f"g {group_name}\n")
            for x, y, z in mesh.vertices:
                handle.write(f"v {x:.9g} {y:.9g} {z:.9g}\n")
            for a, b, c in mesh.triangles:
                handle.write(f"f {a + vertex_offset + 1} {b + vertex_offset + 1} {c + vertex_offset + 1}\n")
            vertex_offset += len(mesh.vertices)
            handle.write("\n")


def write_json(path: str | Path, meshes: list[Mesh], metadata: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vertices, triangles = combine_meshes(meshes)
    mins, maxs = bbox(vertices)
    payload = {
        "source": meshes[0].source_path.as_posix() if meshes else None,
        "metadata": metadata or {},
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "bbox": {"min": mins, "max": maxs},
        "vertices": vertices,
        "triangles": triangles,
        "meshes": [
            {
                "lod": mesh.lod,
                "geom": mesh.geom,
                "material_name": mesh.material_name,
                "material_kind": mesh.material_kind,
                "vertex_count": len(mesh.vertices),
                "triangle_count": len(mesh.triangles),
            }
            for mesh in meshes
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_string_table(reader: Reader) -> list[str]:
    count = reader.u32()
    if count > 10000:
        raise SrtParseError(f"{reader.path}: unreasonable string table count {count}")

    entries = [(reader.u32(), reader.u32()) for _ in range(count)]
    strings = []
    for _padded_size, size in entries:
        raw = reader.read_bytes(size)
        strings.append(raw.rstrip(b"\0").decode("utf-8", "replace"))
    reader.align4()
    return strings


def _skip_billboards(reader: Reader) -> None:
    reader.pos += 12  # width, top, bottom
    billboard_count = reader.u32()
    reader.pos += billboard_count * 16
    reader.pos += billboard_count
    reader.align4()

    cutout_vertex_count = reader.u32()
    cutout_index_count = reader.u32()
    reader.pos += cutout_vertex_count * 8
    reader.pos += cutout_index_count * 2
    reader.align4()

    reader.pos += HORIZONTAL_BILLBOARD_SIZE
    if reader.pos > len(reader.data):
        raise SrtParseError(f"{reader.path}: billboard section exceeds file size")


def _parse_render_states(reader: Reader, strings: list[str]) -> list[RenderState]:
    state_count = reader.u32()
    has_secondary = reader.u32() == 1
    has_tertiary = reader.u32() == 1
    reader.u32()  # render mode string ref

    primary_base = reader.pos
    reader.pos += state_count * RENDER_STATE_SIZE
    if has_secondary:
        reader.pos += state_count * RENDER_STATE_SIZE
    if has_tertiary:
        reader.pos += state_count * RENDER_STATE_SIZE
    reader.pos += (1 + int(has_secondary) + int(has_tertiary)) * RENDER_STATE_SIZE

    states = []
    for index in range(state_count):
        block = reader.data[
            primary_base + index * RENDER_STATE_SIZE : primary_base + (index + 1) * RENDER_STATE_SIZE
        ]
        name_ref = struct.unpack_from(reader.endian + "I", block, MATERIAL_NAME_OFFSET)[0]
        kind_ref = struct.unpack_from(reader.endian + "I", block, MATERIAL_KIND_OFFSET)[0]
        states.append(
            RenderState(
                index=index,
                stride=block[STRIDE_BYTE_OFFSET],
                name=_string_ref(strings, name_ref),
                kind=_string_ref(strings, kind_ref),
                block=block,
            )
        )
    return states


def _parse_geometry_descriptors(reader: Reader) -> list[dict]:
    lod_count = reader.u32()
    lod_table_base = reader.pos
    reader.pos += lod_count * LOD_TABLE_ENTRY_SIZE

    descriptors = []
    for lod_index in range(lod_count):
        lod_words = struct.unpack_from(
            reader.endian + "6I",
            reader.data,
            lod_table_base + lod_index * LOD_TABLE_ENTRY_SIZE,
        )
        draw_call_count = lod_words[0]
        bone_count = lod_words[3]

        for geom_index in range(draw_call_count):
            words = struct.unpack(reader.endian + "10I", reader.read_bytes(DRAW_CALL_SIZE))
            descriptors.append(
                {
                    "lod": lod_index,
                    "geom": geom_index,
                    "render_state_index": words[2],
                    "vertex_count": words[3],
                    "index_count": words[6],
                    "is_index_32": bool(words[7] & 0xFF),
                }
            )
        reader.pos += bone_count * BONE_SIZE
    return descriptors


def _parse_mesh_data(
    reader: Reader,
    descriptors: list[dict],
    render_states: list[RenderState],
    source_path: Path,
) -> list[Mesh]:
    meshes = []
    for descriptor in descriptors:
        state_index = descriptor["render_state_index"]
        if state_index >= len(render_states):
            raise SrtParseError(f"{reader.path}: bad render state index {state_index}")
        render_state = render_states[state_index]
        stride = render_state.stride
        if stride <= 0:
            raise SrtParseError(f"{reader.path}: zero vertex stride in render state {state_index}")

        vertex_count = descriptor["vertex_count"]
        index_count = descriptor["index_count"]
        vertex_blob = reader.read_bytes(vertex_count * stride)
        index_size = 4 if descriptor["is_index_32"] else 2
        index_blob = reader.read_bytes(index_count * index_size)
        reader.align4()

        vertices = _decode_positions(reader, vertex_blob, stride, render_state.block, vertex_count)
        indices = _decode_indices(reader.endian, index_blob, index_size, index_count)
        triangles = _triangle_indices(indices, vertex_count, reader.path)

        meshes.append(
            Mesh(
                lod=descriptor["lod"],
                geom=descriptor["geom"],
                render_state=render_state,
                vertices=vertices,
                triangles=triangles,
                source_path=source_path,
            )
        )
    return meshes

def _decode_positions(
    reader: Reader,
    vertex_blob: bytes,
    stride: int,
    render_state_block: bytes,
    vertex_count: int,
) -> list[tuple[float, float, float]]:
    desc = _semantic_descriptor(render_state_block, stride, 0)
    vertices = []
    for vertex_index in range(vertex_count):
        base = vertex_index * stride
        values = _decode_semantic_values(reader.endian, vertex_blob, base, desc)
        if len(values) < 3 and base + 12 <= len(vertex_blob):
            values = list(struct.unpack_from(reader.endian + "3f", vertex_blob, base))
        if len(values) < 3:
            raise SrtParseError(f"{reader.path}: could not decode position for vertex {vertex_index}")
        vertices.append((values[0], values[1], values[2]))
    return vertices


def _decode_indices(endian: str, index_blob: bytes, index_size: int, index_count: int) -> list[int]:
    fmt = "I" if index_size == 4 else "H"
    return [
        struct.unpack_from(endian + fmt, index_blob, index * index_size)[0]
        for index in range(index_count)
    ]


def _triangle_indices(indices: list[int], vertex_count: int, path: Path) -> list[tuple[int, int, int]]:
    if len(indices) % 3 != 0:
        raise SrtParseError(f"{path}: index count {len(indices)} is not divisible by 3")
    if indices and max(indices) >= vertex_count:
        raise SrtParseError(f"{path}: index references vertex {max(indices)}, but only {vertex_count} exist")
    return [
        (indices[index], indices[index + 1], indices[index + 2])
        for index in range(0, len(indices), 3)
    ]


def _semantic_descriptor(render_state_block: bytes, stride: int, semantic_id: int) -> tuple[int, list[int]]:
    desc_start = VF_DESC_SIZE * (semantic_id + VF_DESC_OFFSET)
    desc = render_state_block[desc_start : desc_start + VF_DESC_SIZE]
    if len(desc) != VF_DESC_SIZE:
        return 0, []

    component_type = desc[0]
    component_count = sum(1 for component in desc[1:5] if component != 0xFF)
    offsets = []
    for offset in desc[9:13]:
        if offset != 0xFF and offset < stride:
            offsets.append(offset)
        if len(offsets) >= component_count:
            break
    return component_type, offsets


def _decode_semantic_values(
    endian: str,
    vertex_blob: bytes,
    base: int,
    desc: tuple[int, list[int]],
) -> list[float]:
    component_type, offsets = desc
    component_size = 4 if component_type == 0 else 2 if component_type == 1 else 1
    values = []
    for offset in offsets:
        start = base + offset
        if start + component_size > len(vertex_blob):
            break
        raw = vertex_blob[start : start + component_size]
        if component_type == 0:
            values.append(struct.unpack(endian + "f", raw)[0])
        elif component_type == 1:
            values.append(struct.unpack(endian + "e", raw)[0])
        elif component_type == 2:
            values.append((raw[0] / 255.0) * 2.0 - 1.0)
    return values


def _read_c_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.index(0, offset)
    return data[offset:end].decode("utf-8", "replace"), end + 1


def _string_ref(strings: list[str], index: int) -> str:
    if 0 <= index < len(strings):
        return strings[index]
    return ""


def _safe_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return cleaned or "mesh"
