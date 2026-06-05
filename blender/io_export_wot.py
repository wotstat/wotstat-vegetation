bl_info = {
    "name": "WOT Simple Object Exporter",
    "author": "WotStat",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "File > Export > WOT Simple Object (.model)",
    "description": "Export a simple mesh visual/model/primitives set for WOT/BigWorld.",
    "category": "Import-Export",
}

import os
import struct
from pathlib import Path
from xml.sax.saxutils import escape

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector


ROOT_PREFIX = struct.pack("<I", 0x42A14E65)
SHADER_PATH = "shaders/std_effects/lightonly_alpha.fx"
TEXTURE_NAME = "yellow.dds"

# Header copied from the local WOT samples. It declares the xyznuvtb vertex
# stream; the last dword is replaced with the actual vertex count.
VERTEX_HEADER = bytes.fromhex(
    "78797a6e757674620000000000000000"
    "00000000000000000000c84200000000"
    "bb4c93b20000803fdfee8233f202501b"
    "0070686572653100617065310000703f"
    "4f000000"
)

# Header copied from the local WOT samples. It declares a 16-bit index list;
# the dword at 0x40 is replaced with the actual index count.
INDEX_HEADER = bytes.fromhex(
    "6c697374000000003900000000000000"
    "00000000000000000000000000000000"
    "00000000000000000000000000dad116"
    "000000000000c84200000000bb4c93b2"
    "5001000001000000"
)


def _as_resource_path(*parts):
    resource_parts = []
    for part in parts:
        for resource_part in str(part).replace("\\", "/").split("/"):
            resource_part = resource_part.strip()
            if resource_part:
                resource_parts.append(resource_part)
    return "/".join(resource_parts)


def _texture_resource_path(texture_prefix):
    texture_prefix = texture_prefix.strip()
    if texture_prefix.lower().endswith(".dds"):
        return _as_resource_path(texture_prefix)
    return _as_resource_path(texture_prefix, TEXTURE_NAME)


def _resource_path_parts(value):
    return [part for part in _as_resource_path(value).split("/") if part]


def _resource_context_from_export(export_directory, resource_prefix):
    prefix_path = _as_resource_path(resource_prefix)
    prefix_parts = _resource_path_parts(prefix_path)
    if not prefix_parts:
        return export_directory, ""

    export_path = Path(export_directory).resolve()
    directory_parts = list(export_path.parts)
    lower_directory_parts = [part.lower() for part in directory_parts]
    lower_prefix_parts = [part.lower() for part in prefix_parts]

    match_index = None
    last_possible_index = len(directory_parts) - len(prefix_parts)
    for index in range(last_possible_index, -1, -1):
        if lower_directory_parts[index:index + len(prefix_parts)] == lower_prefix_parts:
            match_index = index
            break

    if match_index is None:
        return export_directory, prefix_path

    root_parts = directory_parts[:match_index]
    resource_root = str(Path(*root_parts)) if root_parts else os.curdir
    export_resource_prefix = _as_resource_path(*directory_parts[match_index:])
    return resource_root, export_resource_prefix


def _texture_filename(texture_prefix):
    texture_path = _texture_resource_path(texture_prefix)
    if texture_path.lower().endswith(".dds"):
        return os.path.basename(texture_path)
    return TEXTURE_NAME


def _resource_path_startswith(resource_path, prefix):
    path_parts = [part.lower() for part in _resource_path_parts(resource_path)]
    prefix_parts = [part.lower() for part in _resource_path_parts(prefix)]
    return bool(prefix_parts) and path_parts[:len(prefix_parts)] == prefix_parts


def _shared_texture_resource_path(texture_prefix, resource_prefix):
    texture_path = _texture_resource_path(texture_prefix)
    if _resource_path_startswith(texture_path, resource_prefix):
        return texture_path
    return _as_resource_path(resource_prefix, texture_path)


def _texture_export_paths(
    export_directory,
    resource_root,
    resource_prefix,
    export_resource_prefix,
    texture_prefix,
    shared_texture,
):
    if shared_texture:
        resource_path = _shared_texture_resource_path(texture_prefix, resource_prefix)
        file_path = os.path.join(resource_root, *resource_path.split("/"))
        return resource_path, file_path

    filename = _texture_filename(texture_prefix)
    resource_path = _as_resource_path(export_resource_prefix, filename)
    file_path = os.path.join(export_directory, filename)
    return resource_path, file_path


def _format_vec(vec):
    return f"{vec.x:.6f} {vec.y:.6f} {vec.z:.6f}"


def _pad4(data):
    pad = (-len(data)) % 4
    if pad:
        return data + (b"\0" * pad)
    return data


def _section_table(sections):
    table = bytearray()
    for name, data in sections:
        name_bytes = name.encode("ascii")
        table += struct.pack("<I", len(data))
        table += b"\0" * 16
        table += struct.pack("<I", len(name_bytes))
        table += _pad4(name_bytes)
    return bytes(table) + struct.pack("<I", len(table))


def _signed_bits(value, bits, scale):
    value = max(-1.0, min(1.0, float(value)))
    encoded = int(round(value * scale))
    if encoded < 0:
        encoded += 1 << bits
    return encoded & ((1 << bits) - 1)


def _pack_normal(vec):
    return (
        _signed_bits(vec.x, 11, 1023)
        | (_signed_bits(vec.y, 11, 1023) << 11)
        | (_signed_bits(vec.z, 10, 511) << 22)
    )


def _to_wot_vec(vec, y_up):
    if y_up:
        return Vector((vec.x, vec.z, vec.y))
    return Vector((vec.x, vec.y, vec.z))


def _axis_signs(invert_x, invert_y, invert_z):
    return (
        -1.0 if invert_x else 1.0,
        -1.0 if invert_y else 1.0,
        -1.0 if invert_z else 1.0,
    )


def _apply_axis_signs(vec, signs):
    return Vector((vec.x * signs[0], vec.y * signs[1], vec.z * signs[2]))


def _to_export_vec(vec, y_up, signs):
    return _apply_axis_signs(_to_wot_vec(vec, y_up), signs)


def _needs_winding_flip(y_up, signs):
    determinant_sign = -1.0 if y_up else 1.0
    for sign in signs:
        determinant_sign *= sign
    return determinant_sign < 0.0


def _safe_normalized(vec, fallback):
    if vec.length_squared <= 1.0e-12:
        return fallback.copy()
    return vec.normalized()


def _fallback_tangent(normal):
    axis = Vector((1.0, 0.0, 0.0))
    if abs(normal.dot(axis)) > 0.85:
        axis = Vector((0.0, 1.0, 0.0))
    return _safe_normalized(axis - normal * axis.dot(normal), Vector((0.0, 0.0, 1.0)))


def _triangle_tangent(points, uvs, normal):
    edge1 = points[1] - points[0]
    edge2 = points[2] - points[0]
    duv1 = uvs[1] - uvs[0]
    duv2 = uvs[2] - uvs[0]
    determinant = duv1.x * duv2.y - duv1.y * duv2.x

    if abs(determinant) <= 1.0e-10:
        tangent = _fallback_tangent(normal)
        binormal = _safe_normalized(normal.cross(tangent), Vector((0.0, 0.0, 1.0)))
        return tangent, binormal

    inv_det = 1.0 / determinant
    tangent = (edge1 * duv2.y - edge2 * duv1.y) * inv_det
    tangent = _safe_normalized(tangent - normal * tangent.dot(normal), _fallback_tangent(normal))
    binormal = _safe_normalized(normal.cross(tangent), Vector((0.0, 0.0, 1.0)))
    return tangent, binormal


def _triangle_loop_indices(triangle):
    if hasattr(triangle, "loop_indices"):
        return triangle.loop_indices
    return triangle.loops


def _mesh_to_export_data(
    context,
    objects,
    apply_modifiers,
    y_up,
    invert_x,
    invert_y,
    invert_z,
    invert_normals,
):
    depsgraph = context.evaluated_depsgraph_get()
    signs = _axis_signs(invert_x, invert_y, invert_z)
    flip_winding = _needs_winding_flip(y_up, signs)
    vertices = []
    indices = []
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((float("-inf"), float("-inf"), float("-inf")))

    for obj in objects:
        eval_obj = obj.evaluated_get(depsgraph) if apply_modifiers else obj
        if apply_modifiers:
            try:
                mesh = eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            except TypeError:
                mesh = eval_obj.to_mesh()
        else:
            mesh = obj.data.copy()
        if mesh is None:
            continue

        try:
            mesh.calc_loop_triangles()
            if hasattr(mesh, "calc_normals_split"):
                mesh.calc_normals_split()

            uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
            normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()

            for tri in mesh.loop_triangles:
                loop_indices = tuple(_triangle_loop_indices(tri))
                vertex_indices = tuple(tri.vertices)
                if flip_winding:
                    loop_indices = (loop_indices[0], loop_indices[2], loop_indices[1])
                    vertex_indices = (vertex_indices[0], vertex_indices[2], vertex_indices[1])

                tri_positions = []
                tri_normals = []
                tri_uvs = []

                for loop_index, vertex_index in zip(loop_indices, vertex_indices):
                    position = obj.matrix_world @ mesh.vertices[vertex_index].co
                    position = _to_export_vec(position, y_up, signs)
                    normal = normal_matrix @ mesh.loops[loop_index].normal
                    normal = _safe_normalized(_to_export_vec(normal, y_up, signs), Vector((0.0, 1.0, 0.0)))
                    if invert_normals:
                        normal = -normal

                    if uv_layer:
                        uv = uv_layer[loop_index].uv
                        texcoord = Vector((uv.x, 1.0 - uv.y))
                    else:
                        texcoord = Vector((0.0, 0.0))

                    tri_positions.append(position)
                    tri_normals.append(normal)
                    tri_uvs.append(texcoord)

                face_normal = _safe_normalized(
                    (tri_normals[0] + tri_normals[1] + tri_normals[2]) / 3.0,
                    Vector((0.0, 1.0, 0.0)),
                )
                tangent, binormal = _triangle_tangent(tri_positions, tri_uvs, face_normal)

                for position, normal, texcoord in zip(tri_positions, tri_normals, tri_uvs):
                    if len(vertices) >= 65535:
                        raise ValueError("WOT simple export uses 16-bit indices; reduce the mesh below 65535 exported vertices.")

                    for axis in range(3):
                        mins[axis] = min(mins[axis], position[axis])
                        maxs[axis] = max(maxs[axis], position[axis])

                    tangent = _safe_normalized(tangent - normal * tangent.dot(normal), _fallback_tangent(normal))
                    binormal = _safe_normalized(normal.cross(tangent), Vector((0.0, 0.0, 1.0)))

                    vertices.append((position, normal, texcoord, tangent, binormal))
                    indices.append(len(vertices) - 1)
        finally:
            if apply_modifiers:
                eval_obj.to_mesh_clear()
            else:
                bpy.data.meshes.remove(mesh)

    if not vertices or not indices:
        raise ValueError("No triangles were found to export.")

    return vertices, indices, mins, maxs


def _build_vertices_section(vertices):
    header = bytearray(VERTEX_HEADER)
    struct.pack_into("<I", header, 0x40, len(vertices))

    section = bytearray(header)
    for position, normal, texcoord, tangent, binormal in vertices:
        section += struct.pack(
            "<3fI2f2I",
            position.x,
            position.y,
            position.z,
            _pack_normal(normal),
            texcoord.x,
            texcoord.y,
            _pack_normal(tangent),
            _pack_normal(binormal),
        )
    return bytes(section)


def _build_indices_section(indices, vertex_count):
    header = bytearray(INDEX_HEADER)
    struct.pack_into("<I", header, 0x40, len(indices))

    section = bytearray(header)
    for index in indices:
        section += struct.pack("<H", index)

    section += struct.pack("<4I", 0, len(indices) // 3, 0, vertex_count)
    return bytes(section)


def _write_primitives(path, vertices, indices):
    sections = [
        ("vertices", _build_vertices_section(vertices)),
        ("indices", _build_indices_section(indices, len(vertices))),
    ]

    with open(path, "wb") as handle:
        handle.write(ROOT_PREFIX)
        for _name, data in sections:
            handle.write(data)
        handle.write(_section_table(sections))


def _write_model(path, resource_base, mins, maxs):
    resource_base = escape(resource_base)
    content = f"""<?xml version="1.0" encoding="utf-8"?>
<root>
\t<nodelessVisual>{resource_base}</nodelessVisual>
\t<materialNames/>
\t<visibilityBox>
\t\t<min>{_format_vec(mins)}</min>
\t\t<max>{_format_vec(maxs)}</max>
\t</visibilityBox>
</root>
"""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _write_visual(path, texture_resource_path, mins, maxs):
    texture_path = escape(texture_resource_path)
    shader_path = escape(SHADER_PATH)
    content = f"""<?xml version="1.0" encoding="utf-8"?>
<root>
\t<node>
\t\t<identifier>Scene Root</identifier>
\t\t<transform>
\t\t\t<row0>1.000000 0.000000 0.000000</row0>
\t\t\t<row1>0.000000 1.000000 0.000000</row1>
\t\t\t<row2>0.000000 0.000000 1.000000</row2>
\t\t\t<row3>0.000000 0.000000 0.000000</row3>
\t\t</transform>
\t</node>
\t<renderSet>
\t\t<treatAsWorldSpaceObject>false</treatAsWorldSpaceObject>
\t\t<node>Scene Root</node>
\t\t<geometry>
\t\t\t<vertices>vertices</vertices>
\t\t\t<primitive>indices</primitive>
\t\t\t<primitiveGroup>
\t\t\t\t0
\t\t\t\t<material>
\t\t\t\t\t<identifier>lambert1</identifier>
\t\t\t\t\t<fx>{shader_path}</fx>
\t\t\t\t\t<collisionFlags>0</collisionFlags>
\t\t\t\t\t<materialKind>0</materialKind>
\t\t\t\t\t<property>
\t\t\t\t\t\tlightEnable
\t\t\t\t\t\t<Bool>true</Bool>
\t\t\t\t\t</property>
\t\t\t\t\t<property>
\t\t\t\t\t\talphaReference
\t\t\t\t\t\t<Int>0</Int>
\t\t\t\t\t</property>
\t\t\t\t\t<property>
\t\t\t\t\t\talphaTestEnable
\t\t\t\t\t\t<Bool>false</Bool>
\t\t\t\t\t</property>
\t\t\t\t\t<property>
\t\t\t\t\t\tdoubleSided
\t\t\t\t\t\t<Bool>false</Bool>
\t\t\t\t\t</property>
\t\t\t\t\t<property>
\t\t\t\t\t\tdiffuseMap
\t\t\t\t\t\t<Texture>{texture_path}</Texture>
\t\t\t\t\t</property>
\t\t\t\t</material>
\t\t\t</primitiveGroup>
\t\t</geometry>
\t</renderSet>
\t<boundingBox>
\t\t<min>{_format_vec(mins)}</min>
\t\t<max>{_format_vec(maxs)}</max>
\t</boundingBox>
</root>
"""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _yellow_dds_bytes():
    header = bytearray()
    header += b"DDS "
    header += struct.pack("<I", 124)
    header += struct.pack("<I", 0x00081007)
    header += struct.pack("<I", 4)
    header += struct.pack("<I", 4)
    header += struct.pack("<I", 8)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", 0)
    header += struct.pack("<11I", *([0] * 11))
    header += struct.pack("<I", 32)
    header += struct.pack("<I", 0x00000004)
    header += b"DXT1"
    header += struct.pack("<5I", 0, 0, 0, 0, 0)
    header += struct.pack("<I", 0x00001000)
    header += struct.pack("<4I", 0, 0, 0, 0)

    block = struct.pack("<HHI", 0xFFE0, 0xF7E0, 0)
    return bytes(header) + block


def _ensure_texture_dds(path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(_yellow_dds_bytes())


class EXPORT_SCENE_OT_wot_simple(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.wot_simple"
    bl_label = "Export WOT Simple Object"
    bl_options = {"PRESET"}

    filename_ext = ".model"
    filter_glob: StringProperty(default="*.model", options={"HIDDEN"})

    resource_prefix: StringProperty(
        name="Resource prefix",
        default="mods",
        description="Resource root marker to find inside the saved model path",
    )
    texture_prefix: StringProperty(
        name="Texture path",
        default="mods/wotstat-vegetation/colliders",
        description="Resource folder for yellow.dds, or a full .dds resource path",
    )
    shared_texture: BoolProperty(
        name="Shared texture",
        default=True,
        description="Use Texture path under the Resource prefix; otherwise put the texture beside the model",
    )
    apply_modifiers: BoolProperty(
        name="Apply modifiers",
        default=True,
        description="Export the evaluated mesh with modifiers applied",
    )
    y_up: BoolProperty(
        name="Convert Blender Z-up to WOT Y-up",
        default=True,
        description="Map Blender XYZ to WOT XZY coordinates",
    )
    invert_x: BoolProperty(
        name="Invert X",
        default=False,
        description="Multiply exported X position and vector values by -1",
    )
    invert_y: BoolProperty(
        name="Invert Y",
        default=False,
        description="Multiply exported Y position and vector values by -1",
    )
    invert_z: BoolProperty(
        name="Invert Z",
        default=True,
        description="Multiply exported Z position and vector values by -1",
    )
    invert_normals: BoolProperty(
        name="Invert normals",
        default=False,
        description="Flip exported vertex normals after coordinate conversion",
    )

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if not selected_meshes and context.active_object and context.active_object.type == "MESH":
            selected_meshes = [context.active_object]

        if not selected_meshes:
            self.report({"ERROR"}, "Select at least one mesh object.")
            return {"CANCELLED"}

        model_path = bpy.path.ensure_ext(self.filepath, self.filename_ext)
        directory = os.path.dirname(model_path)
        base_name = os.path.splitext(os.path.basename(model_path))[0]
        visual_path = os.path.join(directory, f"{base_name}.visual")
        primitives_path = os.path.join(directory, f"{base_name}.primitives")
        resource_root, export_resource_prefix = _resource_context_from_export(directory, self.resource_prefix)
        resource_base = _as_resource_path(export_resource_prefix, base_name)
        texture_resource_path, texture_file_path = _texture_export_paths(
            directory,
            resource_root,
            self.resource_prefix,
            export_resource_prefix,
            self.texture_prefix,
            self.shared_texture,
        )

        try:
            vertices, indices, mins, maxs = _mesh_to_export_data(
                context,
                selected_meshes,
                self.apply_modifiers,
                self.y_up,
                self.invert_x,
                self.invert_y,
                self.invert_z,
                self.invert_normals,
            )
            _write_primitives(primitives_path, vertices, indices)
            _write_visual(visual_path, texture_resource_path, mins, maxs)
            _write_model(model_path, resource_base, mins, maxs)
            _ensure_texture_dds(texture_file_path)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Exported {base_name}: {len(vertices)} vertices, {len(indices) // 3} triangles.",
        )
        return {"FINISHED"}


def menu_func_export(self, _context):
    self.layout.operator(EXPORT_SCENE_OT_wot_simple.bl_idname, text="WOT Simple Object (.model)")


classes = (EXPORT_SCENE_OT_wot_simple,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
