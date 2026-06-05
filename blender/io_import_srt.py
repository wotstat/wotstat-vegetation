bl_info = {
	"name": "SRT Loader (.srt)",
	"author": "Qirashi",
	"version": (1, 0, 2),
	"blender": (4, 5, 0),
	"description": "Import .srt files version 06.0.0.",
	"doc_url": "https://github.com/qirashi/Blender-SRT-Loader",
	"category": "Import-Export",
}

import math
import struct
import mathutils  # type: ignore
from pathlib import Path

import bpy  # type: ignore
from bpy.props import StringProperty  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore


class CoordSysType:
	Y_UP_RIGHT = 0
	Z_UP_RIGHT = 1
	Y_UP_LEFT = 2
	Z_UP_LEFT = 3

class eSRTConstants:
	RENDER_STATE_SIZE           = 680
	DRAW_CALL_SIZE              = 40
	LOD_TABLE_ENTRY_SIZE        = 24
	BONE_SIZE                   = 48
	COLLISION_OBJECT_SIZE       = 36

	VF_DESC_OFFSET              = 33
	VF_DESC_SIZE                = 13
	STRIDE_BYTE_OFFSET          = 663

	HORIZONTAL_BILLBOARD_SIZE   = 84  # 1 int + 20 floats

	ADDITIONAL_DATA_SIZE        = 31
	WIND_DATA_SIZE              = 1308

class SRTParser:
	def __init__(self, data):
		self.data = data
		self.pos = 0
		self.endian = '<'
		self.is_native_endian = True
		self.platform = {}
		self.string_table_entries = []
		self.string_data_base = 0
		self.render_states = {"count": 0, "blocks": []}
		self.geometry_descriptors = {"num_lods": 0, "lods": []}

	def _read_bytes(self, size):
		if self.pos + size > len(self.data):
			raise ValueError(f"Premature end of file at position {self.pos}")
		result = self.data[self.pos:self.pos + size]
		self.pos += size
		return result

	def _read_int(self):
		return struct.unpack(self.endian + 'I', self._read_bytes(4))[0]

	def _read_float(self):
		return struct.unpack(self.endian + 'f', self._read_bytes(4))[0]

	def _read_byte(self):
		return self._read_bytes(1)[0]

	def _read_string(self):
		start = self.pos
		while self.pos < len(self.data) and self.data[self.pos] != 0:
			self.pos += 1
		result = self.data[start:self.pos].decode('utf-8', errors='ignore')
		self.pos += 1
		return result

	def _align_to_4(self):
		while self.pos % 4 != 0:
			self.pos += 1


	#  Top-level parse sections ---------------------------------------------------------
	def _parse_header(self):
		header = self._read_string()
		if header != "SRT 06.0.0":
			raise ValueError(f"Invalid header: {header}")
		self.pos = 16  # skip padding to 16-byte boundary
		return {"header": header}

	def _parse_platform(self):
		"""Matches C++ CParser::ParsePlatform: endian byte, coord system, texcoords flipped, reserved"""
		self.endian_byte = self._read_byte()
		self.coord_system = self._read_byte()
		self.texcoords_flipped = self._read_byte() == 1
		self._read_byte()  # reserved

		self.is_native_endian = self.endian_byte == 0
		self.endian = '<' if self.is_native_endian else '>'

		self.platform = {
			'endian_byte': self.endian_byte,
			'coord_system': self.coord_system,
			'texcoords_flipped': self.texcoords_flipped,
			'is_native_endian': self.is_native_endian,
			'byte_order': 'little' if self.is_native_endian else 'big',
		}
		return {"platform": self.platform}

	def _parse_extents(self):
		extents = [self._read_float() for _ in range(6)]
		if extents[0] > extents[3]:
			extents[0], extents[3] = extents[3], extents[0]
		if extents[1] > extents[4]:
			extents[1], extents[4] = extents[4], extents[1]
		if extents[2] > extents[5]:
			extents[2], extents[5] = extents[5], extents[2]
		return {"extents": {"min": extents[:3], "max": extents[3:]}}

	def _parse_lod(self):
		"""Matches SLodProfile: enabled flag + 4 float distances"""
		lod_enabled = self._read_int()
		lod_data = [self._read_float() for _ in range(4)]
		return {"lod": {"enabled": bool(lod_enabled), "ranges": lod_data}}

	def _parse_wind(self):
		"""Wind parameters blob of fixed size (covers SPairParams + options + tree data)"""
		wind_data = self._read_bytes(eSRTConstants.WIND_DATA_SIZE)
		return {"wind": wind_data}

	def _parse_additional(self):
		additional = self._read_bytes(eSRTConstants.ADDITIONAL_DATA_SIZE)
		self._align_to_4()
		return {"additional": additional}

	def _parse_string_table_preamble(self):
		preamble = {
			"u32_0": self._read_int(),
			"u32_1": self._read_int(),
			"u32_2": self._read_int(),
			"f32_0": self._read_float(),
		}
		return {"string_table_preamble": preamble}

	def _parse_string_table(self):
		"""Matches CParser::ParseStringTable: count, padded lengths, then string data"""
		try:
			count = self._read_int()
			if count > 10000 or self.pos + count * 8 > len(self.data):
				return {"string_table": "Invalid count or insufficient data"}

			entries = []
			for _ in range(count):
				size_a = self._read_int()  # padding (4 bytes)
				size_b = self._read_int()  # actual string length
				entries.append({"size_a": size_a, "size_b": size_b})

			strings_base = self.pos
			strings = []
			total_string_bytes = 0
			for entry in entries:
				chunk_len = entry["size_b"]
				if chunk_len < 0 or self.pos + chunk_len > len(self.data):
					break
				raw_string = self._read_bytes(chunk_len)
				strings.append(raw_string.rstrip(b'\x00').decode('utf-8', errors='ignore'))
				total_string_bytes += chunk_len

			self._align_to_4()
			self.string_table_entries = entries
			self.string_data_base = strings_base
			return {
				"string_table": {
					"count": count,
					"entries": entries,
					"strings": strings,
					"strings_base": strings_base,
					"total_string_bytes": total_string_bytes,
				}
			}
		except Exception:
			return {"string_table": "Parse error"}

	def _parse_collision_objects(self):
		try:
			count = self._read_int()
			if count > 1000 or self.pos + count * eSRTConstants.COLLISION_OBJECT_SIZE > len(self.data):
				return {"collision_objects": "Invalid count or insufficient data"}
			objects = []
			for _ in range(count):
				objects.append(self._read_bytes(eSRTConstants.COLLISION_OBJECT_SIZE))
			return {"collision_objects": {"count": count, "objects": objects}}
		except Exception:
			return {"collision_objects": "Parse error"}


	#  Billboard parsing (matches C++ vertical + horizontal structures) ---------------------------------------------------------
	def _parse_billboards(self):
		"""Parse vertical billboards followed by horizontal billboard (formerly 'footer')"""
		try:
			# Vertical billboards header
			width = self._read_float()
			top = self._read_float()
			bottom = self._read_float()
			num_billboards = self._read_int()

			if num_billboards < 0 or num_billboards > 10000:
				return {"billboards": "Invalid vertical billboard count"}

			# Texcoord table: 4 floats per billboard
			texcoords_size = num_billboards * 4 * 4  # 4 floats * 4 bytes
			if self.pos + texcoords_size > len(self.data):
				return {"billboards": "Texcoord table out of range"}
			texcoords_blob = self._read_bytes(texcoords_size)
			texcoords = []
			for i in range(0, len(texcoords_blob), 16):
				tc = struct.unpack(self.endian + '4f', texcoords_blob[i:i+16])
				texcoords.append(tc)

			# Rotated flags (1 byte per billboard)
			if self.pos + num_billboards > len(self.data):
				return {"billboards": "Rotated flags out of range"}
			rotated_flags = self._read_bytes(num_billboards)
			self._align_to_4()

			# Cutout vertices and indices counts
			num_cutout_verts = self._read_int()
			num_cutout_indices = self._read_int()
			if num_cutout_verts < 0 or num_cutout_indices < 0:
				return {"billboards": "Invalid cutout counts"}

			cutout_vertices = []
			cutout_indices = []
			if num_cutout_verts > 0 and num_cutout_indices > 0:
				verts_size = num_cutout_verts * 2 * 4  # 2 floats per vertex
				if self.pos + verts_size > len(self.data):
					return {"billboards": "Cutout vertices out of range"}
				verts_blob = self._read_bytes(verts_size)
				for i in range(0, verts_size, 8):
					x, y = struct.unpack(self.endian + '2f', verts_blob[i:i+8])
					cutout_vertices.append((x, y))

				indices_size = num_cutout_indices * 2  # uint16
				if self.pos + indices_size > len(self.data):
					return {"billboards": "Cutout indices out of range"}
				indices_blob = self._read_bytes(indices_size)
				for i in range(0, indices_size, 2):
					idx = struct.unpack(self.endian + 'H', indices_blob[i:i+2])[0]
					cutout_indices.append(idx)
				self._align_to_4()

			# Horizontal billboard (previously called footer)
			horiz_size = eSRTConstants.HORIZONTAL_BILLBOARD_SIZE  # 1 int + 20 floats
			if self.pos + horiz_size > len(self.data):
				return {"billboards": "Horizontal billboard data out of range"}
			h_present = self._read_int()
			h_texcoords = [self._read_float() for _ in range(8)]
			h_positions = []
			for _ in range(4):
				h_positions.append(tuple(self._read_float() for _ in range(3)))

			return {
				"billboards": {
					"vertical": {
						"width": width,
						"top": top,
						"bottom": bottom,
						"num_billboards": num_billboards,
						"texcoords": texcoords,
						"rotated_flags": rotated_flags,
						"num_cutout_vertices": num_cutout_verts,
						"num_cutout_indices": num_cutout_indices,
						"cutout_vertices": cutout_vertices,
						"cutout_indices": cutout_indices,
					},
					"horizontal": {
						"present": bool(h_present),
						"texcoords": h_texcoords,
						"positions": h_positions,
					}
				}
			}
		except Exception:
			return {"billboards": "Parse error"}

	def _parse_custom_data(self):
		if self.pos + 20 > len(self.data):
			return {"custom_data": "Parse error"}
		refs = [self._read_int() for _ in range(5)]   # CCore::USER_STRING_COUNT = 5
		return {"custom_data": {"string_refs": refs}}


	#  Render states (version 6 layout: primary + optional depth/shadow + copies) ---------------------------------------------------------
	def _parse_render_states(self):
		try:
			if self.pos + 16 > len(self.data):
				return {"render_states": "Parse error"}
			state_count = self._read_int()
			has_secondary = self._read_int() == 1   # depth-only pass
			has_tertiary = self._read_int() == 1    # shadow-cast pass
			render_mode = self._read_int()          # shader path index (string)

			if state_count < 0 or state_count > 4096:
				return {"render_states": "Invalid count"}

			block_size = eSRTConstants.RENDER_STATE_SIZE
			primary_size = state_count * block_size
			if self.pos + primary_size > len(self.data):
				return {"render_states": "Primary block out of range"}
			primary_base = self.pos
			self.pos += primary_size

			secondary_base = None
			tertiary_base = None
			if has_secondary:
				if self.pos + primary_size > len(self.data):
					return {"render_states": "Secondary block out of range"}
				secondary_base = self.pos
				self.pos += primary_size
			if has_tertiary:
				if self.pos + primary_size > len(self.data):
					return {"render_states": "Tertiary block out of range"}
				tertiary_base = self.pos
				self.pos += primary_size

			# Billboard render state copies (1 per active pass + main)
			copy_count = 1 + int(has_secondary) + int(has_tertiary)
			for _ in range(copy_count):
				if self.pos + block_size > len(self.data):
					return {"render_states": "State copy out of range"}
				self.pos += block_size

			# Store only primary blocks for geometry creation
			blocks = []
			for i in range(state_count):
				start = primary_base + i * block_size
				blocks.append(self.data[start:start + block_size])
			self.render_states = {"count": state_count, "blocks": blocks}

			return {
				"render_states": {
					"count": state_count,
					"has_secondary": has_secondary,
					"has_tertiary": has_tertiary,
					"render_mode": render_mode,
					"primary_base": primary_base,
					"secondary_base": secondary_base,
					"tertiary_base": tertiary_base,
					"blocks": blocks,
				}
			}
		except Exception as exc:
			return {"render_states": f"Parse error: {exc}"}


	#  3D geometry descriptors (SLod + SDrawCall + SBone) ---------------------------------------------------------
	def _parse_3d_geometry_descriptors(self):
		try:
			num_lods = self._read_int()
			if num_lods < 0 or num_lods > 256:
				return {"3d_geometry": "Invalid LOD count"}

			lod_table_base = self.pos
			lod_table_size = eSRTConstants.LOD_TABLE_ENTRY_SIZE * num_lods
			if self.pos + lod_table_size > len(self.data):
				return {"3d_geometry": "LOD table out of range"}
			self.pos += lod_table_size

			lods = []
			for lod_idx in range(num_lods):
				lod_start = lod_table_base + lod_idx * eSRTConstants.LOD_TABLE_ENTRY_SIZE
				lod_words = struct.unpack(
					self.endian + '6I',
					self.data[lod_start:lod_start + eSRTConstants.LOD_TABLE_ENTRY_SIZE]
				)
				num_geoms = lod_words[0]      # m_nNumDrawCalls
				aux_count = lod_words[3]      # m_nNumBones

				if num_geoms < 0 or num_geoms > 4096:
					return {"3d_geometry": "Invalid geom count"}
				if aux_count < 0 or aux_count > 4096:
					return {"3d_geometry": "Invalid aux count"}

				if self.pos + num_geoms * eSRTConstants.DRAW_CALL_SIZE > len(self.data):
					return {"3d_geometry": "Geom descriptors out of range"}

				geoms = []
				for geom_idx in range(num_geoms):
					geom_words = struct.unpack(
						self.endian + '10I',
						self._read_bytes(eSRTConstants.DRAW_CALL_SIZE)
					)
					geoms.append({
						"geom": geom_idx,
						"render_state_index": geom_words[2],
						"num_vertices": geom_words[3],
						"num_indices": geom_words[6],
						"is_index_32": bool(geom_words[7] & 0xFF),
						"raw_words": list(geom_words),
					})

				aux_data = []
				aux_bytes = aux_count * eSRTConstants.BONE_SIZE
				if aux_count > 0:
					if self.pos + aux_bytes > len(self.data):
						return {"3d_geometry": "LOD aux data out of range"}
					aux_data = self._read_bytes(aux_bytes).hex()

				lods.append({
					"lod": lod_idx,
					"num_geoms": num_geoms,
					"aux_count": aux_count,
					"lod_words": list(lod_words),
					"geoms": geoms,
					"aux_data": aux_data,
				})

			self.geometry_descriptors = {"num_lods": num_lods, "lods": lods}
			return {"3d_geometry": {"num_lods": num_lods, "lods": lods}}
		except Exception as e:
			return {"3d_geometry": f"Parse error: {e}"}


	#  Vertex data decoding helpers ---------------------------------------------------------
	@staticmethod
	def _read_half_float(buf, endian):
		return struct.unpack(endian + 'e', buf)[0]

	def _decode_component(self, raw, comp_type):
		if comp_type == 0 and len(raw) >= 4:
			return struct.unpack(self.endian + 'f', raw[:4])[0]
		if comp_type == 1 and len(raw) >= 2:
			return self._read_half_float(raw[:2], self.endian)
		if comp_type == 2 and len(raw) >= 1:
			return (raw[0] / 255.0) * 2.0 - 1.0
		return 0.0

	def _decode_semantic(self, vertex_blob, base, stride, vf_block, semantic_id):
		desc_start = eSRTConstants.VF_DESC_SIZE * (semantic_id + eSRTConstants.VF_DESC_OFFSET)
		if desc_start + eSRTConstants.VF_DESC_SIZE > len(vf_block):
			return []
		desc = vf_block[desc_start:desc_start + eSRTConstants.VF_DESC_SIZE]
		comp_type = desc[0]

		component_count = sum(1 for c in desc[1:5] if c != 0xFF)
		if component_count <= 0:
			return []
		offsets = []
		for off in desc[9:13]:
			if off == 0xFF or off >= stride:
				continue
			offsets.append(off)
			if len(offsets) >= component_count:
				break

		values = []
		component_size = 4 if comp_type == 0 else 2 if comp_type == 1 else 1
		for off in offsets:
			data_start = base + off
			if data_start + component_size > len(vertex_blob):
				values.append(0.0)
				continue
			raw = vertex_blob[data_start:data_start + component_size]
			values.append(self._decode_component(raw, comp_type))
		return values


	#  Final vertex & index data ---------------------------------------------------------
	def _parse_vertex_index_data(self):
		raw_offset = self.pos
		raw = self.data[raw_offset:]
		meshes = []
		if not self.geometry_descriptors.get("lods"):
			return {
				"vertex_index_data": {
					"raw": raw.hex(),
					"raw_offset": raw_offset,
					"remaining_size": len(raw),
					"meshes": meshes,
				},
			}

		for lod in self.geometry_descriptors["lods"]:
			lod_idx = lod["lod"]
			for geom in lod["geoms"]:
				geom_idx = geom["geom"]
				rs_index = geom["render_state_index"]
				num_vertices = geom["num_vertices"]
				num_indices = geom["num_indices"]
				is_index_32 = geom["is_index_32"]

				if rs_index < 0 or rs_index >= len(self.render_states["blocks"]):
					continue
				vf_block = self.render_states["blocks"][rs_index]
				stride = vf_block[eSRTConstants.STRIDE_BYTE_OFFSET]
				if stride <= 0:
					continue

				vertex_blob_size = num_vertices * stride
				if self.pos + vertex_blob_size > len(self.data):
					continue
				vertex_blob = self.data[self.pos:self.pos + vertex_blob_size]
				self.pos += vertex_blob_size

				index_size = 4 if is_index_32 else 2
				index_blob_size = num_indices * index_size
				if self.pos + index_blob_size > len(self.data):
					continue
				index_blob = self.data[self.pos:self.pos + index_blob_size]
				self.pos += index_blob_size

				self._align_to_4()

				indices = []
				for i in range(num_indices):
					start = i * index_size
					if index_size == 4:
						indices.append(struct.unpack(self.endian + 'I', index_blob[start:start + 4])[0])
					else:
						indices.append(struct.unpack(self.endian + 'H', index_blob[start:start + 2])[0])

				vertices = []
				for v_idx in range(num_vertices):
					base = v_idx * stride
					pos_values = self._decode_semantic(vertex_blob, base, stride, vf_block, 0)
					nrm_values = self._decode_semantic(vertex_blob, base, stride, vf_block, 1)

					uv_values = self._decode_semantic(vertex_blob, base, stride, vf_block, 3)
					if len(uv_values) < 2:
						uv_values = self._decode_semantic(vertex_blob, base, stride, vf_block, 10)
					if len(uv_values) < 2:
						uv_values = self._decode_semantic(vertex_blob, base, stride, vf_block, 14)
					if len(pos_values) < 3:
						pos_values = list(struct.unpack(self.endian + '3f', vertex_blob[base:base + 12]))
					if len(nrm_values) < 3:
						nrm_values = [0.0, 0.0, 1.0]
					if len(uv_values) < 2:
						uv_values = [0.0, 0.0]

					vertices.append({
						"pos": tuple(pos_values[:3]),
						"normal": tuple(nrm_values[:3]),
						"uv": (uv_values[0], uv_values[1]),
					})

				meshes.append({
					"lod": lod_idx,
					"geom": geom_idx,
					"num_vertices": num_vertices,
					"num_indices": num_indices,
					"stride": stride,
					"render_state_index": rs_index,
					"vertices": vertices,
					"indices": indices,
					"index_size": index_size,
				})

		return {
			"vertex_index_data": {
				"raw_offset": raw_offset,
				"remaining_size": len(raw),
				"final_offset": self.pos,
				"meshes": meshes,
			},
		}

	def parse(self):
		result = {}
		result.update(self._parse_header())
		result.update(self._parse_platform())
		result.update(self._parse_extents())
		result.update(self._parse_lod())
		result.update(self._parse_wind())
		result.update(self._parse_additional())
		result.update(self._parse_string_table_preamble())
		result.update(self._parse_string_table())
		result.update(self._parse_collision_objects())
		result.update(self._parse_billboards())
		result.update(self._parse_custom_data())
		result.update(self._parse_render_states())
		result.update(self._parse_3d_geometry_descriptors())
		result.update(self._parse_vertex_index_data())
		return result

def _is_main_texture(name):
	if not isinstance(name, str):
		return False
	name = name.lower()
	if not name.endswith('.dds'):
		return False
	if any(x in name for x in ('_nm.', '_sm.', '_dam.', '_dnm.', '_spec.', '_rough.', '_metal.')):
		return False
	return True


def _is_normal_texture(name):
	if not isinstance(name, str):
		return False
	name = name.lower()
	return name.endswith('.dds') and '_nm' in name


def _texture_priority(name, texture_type):
	if texture_type == 'base':
		if not _is_main_texture(name):
			return None
		return (1 if name.lower().endswith('_hd.dds') else 0,)
	if texture_type == 'normal':
		if not _is_normal_texture(name):
			return None
		return (1 if name.lower().endswith('_nm_hd.dds') else 0,)
	return None


def _pick_texture_name(string_table, indices, texture_type):
	strings = []
	if string_table and isinstance(string_table, dict):
		strings = string_table.get('strings', [])

	best_name = None
	best_priority = None
	for idx in indices:
		if 0 <= idx < len(strings):
			name = strings[idx]
			priority = _texture_priority(name, texture_type)
			if priority is None:
				continue
			if best_priority is None or priority > best_priority:
				best_name = name
				best_priority = priority
	return best_name


def _find_texture_name(string_table, candidate_names):
	strings = []
	if string_table and isinstance(string_table, dict):
		strings = string_table.get('strings', [])

	lookup = {}
	for name in strings:
		if isinstance(name, str):
			lookup[name.lower()] = name

	for candidate in candidate_names:
		if not isinstance(candidate, str):
			continue
		match = lookup.get(candidate.lower())
		if match:
			return match
	return None


def _normal_texture_candidates(base_texture_name):
	if not isinstance(base_texture_name, str):
		return []
	base_lower = base_texture_name.lower()
	if base_lower.endswith('_hd.dds'):
		base_root = base_texture_name[:-7]
	elif base_lower.endswith('.dds'):
		base_root = base_texture_name[:-4]
	else:
		base_root = base_texture_name
	return [
		f"{base_root}_NM_hd.dds",
		f"{base_root}_NM.dds",
		f"{base_root}_nm_hd.dds",
		f"{base_root}_nm.dds",
	]


def _resolve_texture_path(base_dir, texture_name):
	if not texture_name:
		return None
	tex_path = Path(texture_name)
	if tex_path.is_absolute():
		return tex_path if tex_path.exists() else None
	candidate = base_dir / texture_name
	return candidate if candidate.exists() else None


def _make_material_from_image(image_path, mat_name, normal_image_path=None):
	if mat_name in bpy.data.materials:
		mat = bpy.data.materials[mat_name]
	else:
		mat = bpy.data.materials.new(mat_name)
	mat.use_nodes = True
	mat.blend_method = 'HASHED'
	mat.use_backface_culling = False
	mat.alpha_threshold = 0.5

	nodes = mat.node_tree.nodes
	links = mat.node_tree.links
	nodes.clear()

	output = nodes.new(type='ShaderNodeOutputMaterial')
	bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
	tex_node = nodes.new(type='ShaderNodeTexImage')
	normal_tex_node = nodes.new(type='ShaderNodeTexImage')
	separate_color_node = nodes.new(type='ShaderNodeSeparateColor')
	combine_color_node = nodes.new(type='ShaderNodeCombineColor')
	normal_map_node = nodes.new(type='ShaderNodeNormalMap')

	bsdf.inputs['Roughness'].default_value = 0.8
	bsdf.inputs['Metallic'].default_value = 0

	if image_path:
		try:
			tex_node.image = bpy.data.images.load(str(image_path))
			if tex_node.image:
				tex_node.image.colorspace_settings.name = 'sRGB'
				links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
				links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
		except Exception:
			bsdf.inputs['Alpha'].default_value = 1.0
	else:
		bsdf.inputs['Alpha'].default_value = 1.0

	if normal_image_path:
		try:
			normal_image = bpy.data.images.load(str(normal_image_path))
			if normal_image:
				normal_image.colorspace_settings.name = 'Non-Color'
				normal_tex_node.image = normal_image
				separate_color_node.mode = 'RGB'
				combine_color_node.mode = 'RGB'
				links.new(normal_tex_node.outputs['Color'], separate_color_node.inputs['Color'])
				links.new(normal_tex_node.outputs['Alpha'], combine_color_node.inputs['Red'])
				links.new(separate_color_node.outputs['Green'], combine_color_node.inputs['Green'])
				links.new(separate_color_node.outputs['Blue'], combine_color_node.inputs['Blue'])
				links.new(combine_color_node.outputs['Color'], normal_map_node.inputs['Color'])
				normal_map_node.space = 'TANGENT'
				links.new(normal_map_node.outputs['Normal'], bsdf.inputs['Normal'])
		except Exception:
			pass

	links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
	return mat


def _render_state_texture_indices(render_state_block):
	if not render_state_block or len(render_state_block) < 12:
		return []
	try:
		return list(struct.unpack('<3I', render_state_block[:12]))
	except Exception:
		return []


def create_materials_from_render_states(string_table, render_states, base_dir):
	materials = {}

	if not render_states or not isinstance(render_states, dict):
		return materials

	blocks = render_states.get('blocks', [])
	for rs_index, block in enumerate(blocks):
		indices = _render_state_texture_indices(block)
		main_tex = _pick_texture_name(string_table, indices, 'base')
		normal_tex = _pick_texture_name(string_table, indices, 'normal')
		if main_tex is None:
			strings = []
			if string_table and isinstance(string_table, dict):
				strings = string_table.get('strings', [])
			for idx in indices:
				if 0 <= idx < len(strings):
					name = strings[idx]
					if isinstance(name, str) and name.lower().endswith('.dds'):
						main_tex = name
						break
		if main_tex is None:
			continue
		if normal_tex is None:
			normal_tex = _find_texture_name(string_table, _normal_texture_candidates(main_tex))
		image_path = _resolve_texture_path(base_dir, main_tex)
		normal_image_path = _resolve_texture_path(base_dir, normal_tex) if normal_tex else None
		mat_name = Path(main_tex).stem
		mat = _make_material_from_image(image_path, mat_name, normal_image_path=normal_image_path)
		materials[rs_index] = mat
	return materials


def create_mesh_from_3d(mesh_data, name, target_collection=None, rotation=None):
	vertices = mesh_data.get('vertices', [])
	indices = mesh_data.get('indices', [])
	if not vertices or not indices or len(indices) % 3 != 0:
		return None
	verts = [v['pos'] for v in vertices]
	max_index = len(verts) - 1
	faces = []
	for i in range(0, len(indices), 3):
		tri = indices[i:i + 3]
		if len(tri) < 3:
			continue
		i0, i1, i2 = tri
		if (
			not isinstance(i0, int) or not isinstance(i1, int) or not isinstance(i2, int) or
			i0 < 0 or i1 < 0 or i2 < 0 or
			i0 > max_index or i1 > max_index or i2 > max_index
		):
			continue
		faces.append((i2, i1, i0))

	if not faces:
		return None

	mesh = bpy.data.meshes.new(name + "_mesh")
	try:
		mesh.from_pydata(verts, [], faces)
	except Exception:
		return None
	mesh.update()
	uv_layer = mesh.uv_layers.new(name="UVMap")
	for poly in mesh.polygons:
		for loop_idx in poly.loop_indices:
			vertex_idx = mesh.loops[loop_idx].vertex_index
			if 0 <= vertex_idx < len(vertices):
				u, v = vertices[vertex_idx]['uv']
				uv_layer.data[loop_idx].uv = (u, 1.0 - v)

	custom_normals = []
	for i in range(len(mesh.vertices)):
		src = vertices[i] if i < len(vertices) else {}
		n = src.get('normal', (0.0, 0.0, 1.0))
		if len(n) < 3:
			n = (0.0, 0.0, 1.0)
		custom_normals.append((float(n[0]), float(n[1]), float(n[2])))
	if custom_normals:
		try:
			mesh.normals_split_custom_set_from_vertices(custom_normals)
		except Exception:
			pass

	obj = bpy.data.objects.new(name, mesh)

	if rotation:
		obj.rotation_euler = rotation

	if target_collection is None:
		target_collection = bpy.context.collection
	target_collection.objects.link(obj)
	return obj


def get_or_create_collection(name, parent=None):
	col = bpy.data.collections.get(name)
	if col is None:
		col = bpy.data.collections.new(name)
		if parent is None:
			bpy.context.scene.collection.children.link(col)
		else:
			parent.children.link(col)
	return col


class IMPORT_OT_scots_pine_srt(bpy.types.Operator, ImportHelper):
	bl_idname = "import_scene.scots_pine_srt"
	bl_label = "Import SpeedTree SRT 06.0.0"
	bl_description = "Import SRT file and build available LOD geometry in Blender"
	bl_options = {'REGISTER', 'UNDO'}
	filename_ext = ".srt"
	filter_glob: StringProperty(default="*.srt", options={'HIDDEN'})  # type: ignore

	def execute(self, context):
		try:
			with open(self.filepath, 'rb') as f:
				parsed = SRTParser(f.read()).parse()
		except Exception as exc:
			self.report({'ERROR'}, f"Failed to import SRT: {exc}")
			return {'CANCELLED'}

		srt_path = Path(self.filepath)
		base_name = srt_path.stem
		base_dir = srt_path.parent

		vertex_index = parsed.get('vertex_index_data', {})
		meshes = vertex_index.get('meshes', [])
		string_table = parsed.get('string_table')
		render_states = parsed.get('render_states')

		materials = create_materials_from_render_states(
			string_table, render_states, base_dir
		)

		root_collection = get_or_create_collection(f"{base_name}_SRT")

		lods_dict = {}
		for mesh_data in meshes:
			lod = mesh_data.get('lod', 0)
			rs_index = mesh_data.get('render_state_index')
			if not materials or rs_index not in materials:
				continue
			lods_dict.setdefault(lod, []).append((mesh_data, rs_index))

		created_objects = 0

		for lod in sorted(lods_dict.keys()):
			lod_collection = get_or_create_collection(
				f"{base_name}_LOD{lod}", parent=root_collection
			)
			lod_collection.hide_viewport = False
			lod_collection.hide_render = False

			geom_objects = []
			for mesh_data, rs_index in lods_dict[lod]:
				geom = mesh_data.get('geom', 0)
				rotation_x_90 = mathutils.Euler((math.radians(90), 0, 0), 'XYZ')
				obj = create_mesh_from_3d(
					mesh_data,
					f"{base_name}_lod{lod}_geom{geom}",
					target_collection=lod_collection,
					rotation=rotation_x_90
				)
				if obj:
					obj.data.materials.append(materials[rs_index])
					geom_objects.append(obj)

			if not geom_objects:
				continue

			if len(geom_objects) > 1:
				bpy.ops.object.select_all(action='DESELECT')
				for obj in geom_objects:
					obj.select_set(True)
				context.view_layer.objects.active = geom_objects[0]
				bpy.ops.object.join()
				combined_obj = geom_objects[0]
				bpy.ops.object.select_all(action='DESELECT')
			else:
				combined_obj = geom_objects[0]

			combined_obj.name = f"{base_name}_LOD{lod}"
			combined_obj.hide_set(False)
			combined_obj.hide_render = False
			created_objects += 1
			self.report({'INFO'}, f"LOD {lod} created with {len(geom_objects)} geoms combined.")

		if created_objects == 0:
			self.report({'ERROR'}, "Parsed file but could not construct any geometry.")
			return {'CANCELLED'}

		return {'FINISHED'}


def menu_func_import(self, context):
	self.layout.operator(IMPORT_OT_scots_pine_srt.bl_idname, text="SpeedTree SRT (.srt)")


classes = (
	IMPORT_OT_scots_pine_srt,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)