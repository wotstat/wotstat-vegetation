import json
import math
import os
import struct


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


class RenderState(object):

  def __init__(self, index, stride, name, kind, block):
    self.index = index
    self.stride = stride
    self.name = name
    self.kind = kind
    self.block = block


class Mesh(object):

  def __init__(self, lod, geom, renderState, vertices, triangles, sourcePath):
    self.lod = lod
    self.geom = geom
    self.renderState = renderState
    self.vertices = vertices
    self.triangles = triangles
    self.sourcePath = sourcePath

  @property
  def material_name(self):
    return self.renderState.name

  @property
  def material_kind(self):
    return self.renderState.kind


class SrtGeometry(object):

  def __init__(self, path, strings, extents, collisionObjectCount, renderStates, meshes):
    self.path = path
    self.strings = strings
    self.extents = extents
    self.speedtree_collision_object_count = collisionObjectCount
    self.render_states = renderStates
    self.meshes = meshes

  def collisionMeshes(self, lod=None, includeSolid=False):
    names = {'COLLISION': True}
    if includeSolid:
      names['SOLID'] = True

    meshes = []
    for mesh in self.meshes:
      if mesh.material_name in names or mesh.material_kind in names:
        meshes.append(mesh)

    if not meshes:
      return []

    selectedLod = lod
    if selectedLod is None:
      selectedLod = min([mesh.lod for mesh in meshes])

    return [mesh for mesh in meshes if mesh.lod == selectedLod]


class Reader(object):

  def __init__(self, data, path):
    self.data = data
    self.path = path
    self.pos = 0
    self.endian = '<'

  def readBytes(self, size):
    if self.pos < 0 or self.pos + size > len(self.data):
      raise SrtParseError(
        str(self.path) + ': unexpected end of file at offset ' + str(self.pos)
      )
    result = self.data[self.pos:self.pos + size]
    self.pos += size
    return result

  def u32(self):
    return struct.unpack(self.endian + 'I', self.readBytes(4))[0]

  def f32(self):
    return struct.unpack(self.endian + 'f', self.readBytes(4))[0]

  def byte(self):
    return _byteValue(self.readBytes(1), 0)

  def align4(self):
    self.pos = (self.pos + 3) & ~3


def parseSrtBinary(data, sourcePath):
  reader = Reader(data, sourcePath)

  header = _readCString(reader.data, 0)[0]
  if header != 'SRT 06.0.0':
    raise SrtParseError(str(sourcePath) + ': unsupported SRT header ' + repr(header))

  reader.pos = 16
  endianByte = reader.byte()
  reader.byte()
  reader.byte()
  reader.byte()
  reader.endian = '<' if endianByte == 0 else '>'

  extents = struct.unpack_from(reader.endian + '6f', reader.data, reader.pos)
  reader.pos += 24

  reader.u32()
  reader.pos += 16
  reader.pos += WIND_DATA_SIZE
  reader.pos += ADDITIONAL_DATA_SIZE
  reader.align4()

  reader.pos += 16
  strings = _parseStringTable(reader)

  collisionObjectCount = reader.u32()
  reader.pos += collisionObjectCount * COLLISION_OBJECT_SIZE

  _skipBillboards(reader)
  reader.pos += 20

  renderStates = _parseRenderStates(reader, strings)
  descriptors = _parseGeometryDescriptors(reader)
  meshes = _parseMeshData(reader, descriptors, renderStates, sourcePath)

  if reader.pos != len(reader.data):
    raise SrtParseError(
      str(sourcePath) + ': parser stopped at ' + str(reader.pos) +
      ', file size is ' + str(len(reader.data))
    )

  return SrtGeometry(
    sourcePath,
    strings,
    extents,
    collisionObjectCount,
    renderStates,
    meshes
  )


def combineMeshes(meshes):
  vertices = []
  triangles = []
  for mesh in meshes:
    base = len(vertices)
    vertices.extend(mesh.vertices)
    for a, b, c in mesh.triangles:
      triangles.append((a + base, b + base, c + base))
  return vertices, triangles


def bbox(vertices):
  values = list(vertices)
  if not values:
    raise ValueError('cannot compute a bounding box for an empty mesh')
  mins = tuple([min([vertex[i] for vertex in values]) for i in range(3)])
  maxs = tuple([max([vertex[i] for vertex in values]) for i in range(3)])
  return mins, maxs


def writeObj(path, meshes, metadata=None):
  vertices, _triangles = combineMeshes(meshes)
  directory = os.path.dirname(path)
  if directory and not os.path.isdir(directory):
    os.makedirs(directory)

  with open(path, 'w') as handle:
    handle.write('# World of Tanks vegetation collision mesh\n')
    if meshes:
      handle.write('# source: ' + str(meshes[0].sourcePath) + '\n')
    handle.write('# vertices: ' + str(len(vertices)) + '\n')
    handle.write('# triangles: ' + str(sum([len(mesh.triangles) for mesh in meshes])) + '\n')
    if metadata:
      for key, value in metadata.items():
        if value is not None:
          handle.write('# ' + str(key) + ': ' + str(value) + '\n')
    handle.write('\n')

    vertexOffset = 0
    for mesh in meshes:
      groupName = _safeName('lod' + str(mesh.lod) + '_geom' + str(mesh.geom) + '_' +
                            (mesh.material_name or mesh.material_kind))
      handle.write('g ' + groupName + '\n')
      for x, y, z in mesh.vertices:
        handle.write('v %.9g %.9g %.9g\n' % (x, y, z))
      for a, b, c in mesh.triangles:
        handle.write(
          'f ' + str(a + vertexOffset + 1) + ' ' +
          str(b + vertexOffset + 1) + ' ' +
          str(c + vertexOffset + 1) + '\n'
        )
      vertexOffset += len(mesh.vertices)
      handle.write('\n')


def writeJson(path, meshes, metadata=None):
  vertices, triangles = combineMeshes(meshes)
  mins, maxs = bbox(vertices)
  payload = {
    'source': str(meshes[0].sourcePath) if meshes else None,
    'metadata': metadata or {},
    'vertex_count': len(vertices),
    'triangle_count': len(triangles),
    'bbox': {'min': mins, 'max': maxs},
    'vertices': vertices,
    'triangles': triangles,
    'meshes': [
      {
        'lod': mesh.lod,
        'geom': mesh.geom,
        'material_name': mesh.material_name,
        'material_kind': mesh.material_kind,
        'vertex_count': len(mesh.vertices),
        'triangle_count': len(mesh.triangles)
      }
      for mesh in meshes
    ]
  }
  directory = os.path.dirname(path)
  if directory and not os.path.isdir(directory):
    os.makedirs(directory)
  with open(path, 'w') as handle:
    json.dump(payload, handle, indent=2)


def _parseStringTable(reader):
  count = reader.u32()
  if count > 10000:
    raise SrtParseError(str(reader.path) + ': unreasonable string table count ' + str(count))

  entries = []
  for _index in range(count):
    entries.append((reader.u32(), reader.u32()))

  strings = []
  for _paddedSize, size in entries:
    raw = reader.readBytes(size)
    strings.append(_decodeBytes(raw.rstrip(_nullByte())))
  reader.align4()
  return strings


def _skipBillboards(reader):
  reader.pos += 12
  billboardCount = reader.u32()
  reader.pos += billboardCount * 16
  reader.pos += billboardCount
  reader.align4()

  cutoutVertexCount = reader.u32()
  cutoutIndexCount = reader.u32()
  reader.pos += cutoutVertexCount * 8
  reader.pos += cutoutIndexCount * 2
  reader.align4()

  reader.pos += HORIZONTAL_BILLBOARD_SIZE
  if reader.pos > len(reader.data):
    raise SrtParseError(str(reader.path) + ': billboard section exceeds file size')


def _parseRenderStates(reader, strings):
  stateCount = reader.u32()
  hasSecondary = reader.u32() == 1
  hasTertiary = reader.u32() == 1
  reader.u32()

  primaryBase = reader.pos
  reader.pos += stateCount * RENDER_STATE_SIZE
  if hasSecondary:
    reader.pos += stateCount * RENDER_STATE_SIZE
  if hasTertiary:
    reader.pos += stateCount * RENDER_STATE_SIZE
  reader.pos += (1 + int(hasSecondary) + int(hasTertiary)) * RENDER_STATE_SIZE

  states = []
  for index in range(stateCount):
    block = reader.data[
      primaryBase + index * RENDER_STATE_SIZE:
      primaryBase + (index + 1) * RENDER_STATE_SIZE
    ]
    nameRef = struct.unpack_from(reader.endian + 'I', block, MATERIAL_NAME_OFFSET)[0]
    kindRef = struct.unpack_from(reader.endian + 'I', block, MATERIAL_KIND_OFFSET)[0]
    states.append(RenderState(
      index,
      _byteValue(block, STRIDE_BYTE_OFFSET),
      _stringRef(strings, nameRef),
      _stringRef(strings, kindRef),
      block
    ))
  return states


def _parseGeometryDescriptors(reader):
  lodCount = reader.u32()
  lodTableBase = reader.pos
  reader.pos += lodCount * LOD_TABLE_ENTRY_SIZE

  descriptors = []
  for lodIndex in range(lodCount):
    lodWords = struct.unpack_from(
      reader.endian + '6I',
      reader.data,
      lodTableBase + lodIndex * LOD_TABLE_ENTRY_SIZE
    )
    drawCallCount = lodWords[0]
    boneCount = lodWords[3]

    for geomIndex in range(drawCallCount):
      words = struct.unpack(reader.endian + '10I', reader.readBytes(DRAW_CALL_SIZE))
      descriptors.append({
        'lod': lodIndex,
        'geom': geomIndex,
        'render_state_index': words[2],
        'vertex_count': words[3],
        'index_count': words[6],
        'is_index_32': bool(words[7] & 0xFF)
      })
    reader.pos += boneCount * BONE_SIZE
  return descriptors


def _parseMeshData(reader, descriptors, renderStates, sourcePath):
  meshes = []
  for descriptor in descriptors:
    stateIndex = descriptor['render_state_index']
    if stateIndex >= len(renderStates):
      raise SrtParseError(str(reader.path) + ': bad render state index ' + str(stateIndex))
    renderState = renderStates[stateIndex]
    stride = renderState.stride
    if stride <= 0:
      raise SrtParseError(
        str(reader.path) + ': zero vertex stride in render state ' + str(stateIndex)
      )

    vertexCount = descriptor['vertex_count']
    indexCount = descriptor['index_count']
    vertexBlob = reader.readBytes(vertexCount * stride)
    indexSize = 4 if descriptor['is_index_32'] else 2
    indexBlob = reader.readBytes(indexCount * indexSize)
    reader.align4()

    vertices = _decodePositions(reader, vertexBlob, stride, renderState.block, vertexCount)
    indices = _decodeIndices(reader.endian, indexBlob, indexSize, indexCount)
    triangles = _triangleIndices(indices, vertexCount, reader.path)

    meshes.append(Mesh(
      descriptor['lod'],
      descriptor['geom'],
      renderState,
      vertices,
      triangles,
      sourcePath
    ))
  return meshes


def _decodePositions(reader, vertexBlob, stride, renderStateBlock, vertexCount):
  desc = _semanticDescriptor(renderStateBlock, stride, 0)
  vertices = []
  for vertexIndex in range(vertexCount):
    base = vertexIndex * stride
    values = _decodeSemanticValues(reader.endian, vertexBlob, base, desc)
    if len(values) < 3 and base + 12 <= len(vertexBlob):
      values = list(struct.unpack_from(reader.endian + '3f', vertexBlob, base))
    if len(values) < 3:
      raise SrtParseError(
        str(reader.path) + ': could not decode position for vertex ' + str(vertexIndex)
      )
    vertices.append((values[0], values[1], values[2]))
  return vertices


def _decodeIndices(endian, indexBlob, indexSize, indexCount):
  fmt = 'I' if indexSize == 4 else 'H'
  result = []
  for index in range(indexCount):
    result.append(struct.unpack_from(endian + fmt, indexBlob, index * indexSize)[0])
  return result


def _triangleIndices(indices, vertexCount, path):
  if len(indices) % 3 != 0:
    raise SrtParseError(str(path) + ': index count ' + str(len(indices)) + ' is not divisible by 3')
  if indices and max(indices) >= vertexCount:
    raise SrtParseError(
      str(path) + ': index references vertex ' + str(max(indices)) +
      ', but only ' + str(vertexCount) + ' exist'
    )

  result = []
  for index in range(0, len(indices), 3):
    result.append((indices[index], indices[index + 1], indices[index + 2]))
  return result


def _semanticDescriptor(renderStateBlock, stride, semanticId):
  descStart = VF_DESC_SIZE * (semanticId + VF_DESC_OFFSET)
  desc = renderStateBlock[descStart:descStart + VF_DESC_SIZE]
  if len(desc) != VF_DESC_SIZE:
    return 0, []

  componentType = _byteValue(desc, 0)
  componentCount = 0
  for index in range(1, 5):
    if _byteValue(desc, index) != 0xFF:
      componentCount += 1

  offsets = []
  for index in range(9, 13):
    offset = _byteValue(desc, index)
    if offset != 0xFF and offset < stride:
      offsets.append(offset)
    if len(offsets) >= componentCount:
      break
  return componentType, offsets


def _decodeSemanticValues(endian, vertexBlob, base, desc):
  componentType, offsets = desc
  componentSize = 4 if componentType == 0 else 2 if componentType == 1 else 1
  values = []
  for offset in offsets:
    start = base + offset
    if start + componentSize > len(vertexBlob):
      break
    raw = vertexBlob[start:start + componentSize]
    if componentType == 0:
      values.append(struct.unpack(endian + 'f', raw)[0])
    elif componentType == 1:
      half = struct.unpack(endian + 'H', raw)[0]
      values.append(_halfToFloat(half))
    elif componentType == 2:
      values.append((_byteValue(raw, 0) / 255.0) * 2.0 - 1.0)
  return values


def _readCString(data, offset):
  if isinstance(data, bytes):
    terminator = b'\0'
  else:
    terminator = '\0'
  end = data.index(terminator, offset)
  return _decodeBytes(data[offset:end]), end + 1


def _stringRef(strings, index):
  if 0 <= index < len(strings):
    return strings[index]
  return ''


def _safeName(value):
  cleaned = ''.join([ch if ch.isalnum() or ch in '._-' else '_' for ch in value])
  return cleaned or 'mesh'


def _byteValue(data, index):
  value = data[index]
  if isinstance(value, int):
    return value
  return ord(value)


def _decodeBytes(value):
  if hasattr(value, 'decode'):
    return value.decode('utf-8', 'replace')
  return value


def _nullByte():
  try:
    return b'\0'
  except Exception:
    return '\0'


def _halfToFloat(value):
  sign = -1.0 if (value & 0x8000) else 1.0
  exponent = (value >> 10) & 0x1F
  mantissa = value & 0x03FF

  if exponent == 0:
    if mantissa == 0:
      return -0.0 if sign < 0 else 0.0
    return sign * math.ldexp(float(mantissa), -24)

  if exponent == 31:
    if mantissa == 0:
      return sign * float('inf')
    return float('nan')

  return sign * math.ldexp(1.0 + float(mantissa) / 1024.0, exponent - 15)
