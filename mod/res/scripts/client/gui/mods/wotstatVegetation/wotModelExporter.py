import os
import struct
from xml.sax.saxutils import escape


ROOT_PREFIX = struct.pack('<I', 0x42A14E65)
SHADER_PATH = 'shaders/std_effects/lightonly_alpha.fx'


def _hexToBytes(value):
  try:
    return value.decode('hex')
  except AttributeError:
    return bytes.fromhex(value)


VERTEX_HEADER = (
  '78797a6e757674620000000000000000'
  '00000000000000000000c84200000000'
  'bb4c93b20000803fdfee8233f202501b'
  '0070686572653100617065310000703f'
  '4f000000'
)
VERTEX_HEADER = _hexToBytes(VERTEX_HEADER)

INDEX_HEADER = (
  '6c697374000000003900000000000000'
  '00000000000000000000000000000000'
  '00000000000000000000000000dad116'
  '000000000000c84200000000bb4c93b2'
  '5001000001000000'
)
INDEX_HEADER = _hexToBytes(INDEX_HEADER)


def exportColliderModel(modelPath, meshes, textureResourcePath, resourceBase=None):
  base = os.path.splitext(modelPath)[0]
  visualPath = base + '.visual'
  primitivesPath = base + '.primitives'
  if resourceBase is None:
    resourceBase = _resourceBaseFromPath(base)

  vertices, indices, mins, maxs = _meshesToExportData(meshes)
  _writePrimitives(primitivesPath, vertices, indices)
  _writeVisual(visualPath, textureResourcePath, mins, maxs)
  _writeModel(modelPath, resourceBase, mins, maxs)

  return {
    'model': modelPath,
    'visual': visualPath,
    'primitives': primitivesPath,
    'resourceBase': resourceBase,
    'vertices': len(vertices),
    'triangles': len(indices) // 3,
    'bbox': {'min': mins, 'max': maxs}
  }


def _resourceBaseFromPath(base):
  return base.replace('\\', '/')


def _meshesToExportData(meshes):
  vertices = []
  indices = []
  mins = [float('inf'), float('inf'), float('inf')]
  maxs = [float('-inf'), float('-inf'), float('-inf')]

  for mesh in meshes:
    for a, b, c in mesh.triangles:
      p0 = mesh.vertices[a]
      p1 = mesh.vertices[b]
      p2 = mesh.vertices[c]
      normal = _triangleNormal(p0, p1, p2)
      tangent = _fallbackTangent(normal)
      binormal = _normalize(_cross(normal, tangent), (0.0, 0.0, 1.0))

      for position in (p0, p1, p2):
        if len(vertices) >= 65535:
          raise ValueError(
            'WOT simple export uses 16-bit indices; reduce the mesh below 65535 exported vertices.'
          )
        _extendBounds(mins, maxs, position)
        vertices.append((position, normal, (0.0, 0.0), tangent, binormal))
        indices.append(len(vertices) - 1)

  if not vertices or not indices:
    raise ValueError('No triangles were found to export.')

  return vertices, indices, tuple(mins), tuple(maxs)


def _extendBounds(mins, maxs, position):
  for axis in range(3):
    mins[axis] = min(mins[axis], position[axis])
    maxs[axis] = max(maxs[axis], position[axis])


def _triangleNormal(p0, p1, p2):
  edge1 = _sub(p1, p0)
  edge2 = _sub(p2, p0)
  return _normalize(_cross(edge1, edge2), (0.0, 1.0, 0.0))


def _fallbackTangent(normal):
  axis = (1.0, 0.0, 0.0)
  if abs(_dot(normal, axis)) > 0.85:
    axis = (0.0, 1.0, 0.0)
  projected = _sub(axis, _mul(normal, _dot(axis, normal)))
  return _normalize(projected, (0.0, 0.0, 1.0))


def _sub(a, b):
  return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, scalar):
  return (a[0] * scalar, a[1] * scalar, a[2] * scalar)


def _dot(a, b):
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
  return (
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0]
  )


def _normalize(value, fallback):
  lengthSq = _dot(value, value)
  if lengthSq <= 1.0e-12:
    return fallback
  length = lengthSq ** 0.5
  return (value[0] / length, value[1] / length, value[2] / length)


def _formatVec(vec):
  return '%.6f %.6f %.6f' % (vec[0], vec[1], vec[2])


def _pad4(data):
  pad = (-len(data)) % 4
  if pad:
    return data + (b'\0' * pad)
  return data


def _sectionTable(sections):
  parts = []
  for name, data in sections:
    nameBytes = name.encode('ascii')
    parts.append(struct.pack('<I', len(data)))
    parts.append(b'\0' * 16)
    parts.append(struct.pack('<I', len(nameBytes)))
    parts.append(_pad4(nameBytes))
  table = b''.join(parts)
  return table + struct.pack('<I', len(table))


def _signedBits(value, bits, scale):
  value = max(-1.0, min(1.0, float(value)))
  encoded = int(round(value * scale))
  if encoded < 0:
    encoded += 1 << bits
  return encoded & ((1 << bits) - 1)


def _packNormal(vec):
  return (
    _signedBits(vec[0], 11, 1023) |
    (_signedBits(vec[1], 11, 1023) << 11) |
    (_signedBits(vec[2], 10, 511) << 22)
  )


def _buildVerticesSection(vertices):
  header = bytearray(VERTEX_HEADER)
  struct.pack_into('<I', header, 0x40, len(vertices))

  parts = [_bytearrayToBytes(header)]
  for position, normal, texcoord, tangent, binormal in vertices:
    parts.append(struct.pack(
      '<3fI2f2I',
      position[0],
      position[1],
      position[2],
      _packNormal(normal),
      texcoord[0],
      texcoord[1],
      _packNormal(tangent),
      _packNormal(binormal)
    ))
  return b''.join(parts)


def _buildIndicesSection(indices, vertexCount):
  header = bytearray(INDEX_HEADER)
  struct.pack_into('<I', header, 0x40, len(indices))

  parts = [_bytearrayToBytes(header)]
  for index in indices:
    parts.append(struct.pack('<H', index))

  parts.append(struct.pack('<4I', 0, len(indices) // 3, 0, vertexCount))
  return b''.join(parts)


def _bytearrayToBytes(value):
  if not value:
    return b''
  return struct.pack('<' + str(len(value)) + 'B', *value)


def _writePrimitives(path, vertices, indices):
  _ensureParent(path)
  sections = [
    ('vertices', _buildVerticesSection(vertices)),
    ('indices', _buildIndicesSection(indices, len(vertices)))
  ]

  with open(path, 'wb') as handle:
    handle.write(ROOT_PREFIX)
    for _name, data in sections:
      handle.write(data)
    handle.write(_sectionTable(sections))


def _writeModel(path, resourceBase, mins, maxs):
  _ensureParent(path)
  resourceBase = escape(resourceBase)
  content = """<?xml version="1.0" encoding="utf-8"?>
<root>
\t<nodelessVisual>{resourceBase}</nodelessVisual>
\t<materialNames/>
\t<visibilityBox>
\t\t<min>{mins}</min>
\t\t<max>{maxs}</max>
\t</visibilityBox>
</root>
""".format(
    resourceBase=resourceBase,
    mins=_formatVec(mins),
    maxs=_formatVec(maxs)
  )
  with open(path, 'w') as handle:
    handle.write(content)


def _writeVisual(path, textureResourcePath, mins, maxs):
  _ensureParent(path)
  texturePath = escape(textureResourcePath)
  shaderPath = escape(SHADER_PATH)
  content = """<?xml version="1.0" encoding="utf-8"?>
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
\t\t\t\t\t<identifier>wotstatVegetationCollider</identifier>
\t\t\t\t\t<fx>{shaderPath}</fx>
\t\t\t\t\t<collisionFlags>0</collisionFlags>
\t\t\t\t\t<materialKind>0</materialKind>
\t\t\t\t\t<property>
\t\t\t\t\t\tlightEnable
\t\t\t\t\t\t<Bool>false</Bool>
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
\t\t\t\t\t\t<Texture>{texturePath}</Texture>
\t\t\t\t\t</property>
\t\t\t\t</material>
\t\t\t</primitiveGroup>
\t\t</geometry>
\t</renderSet>
\t<boundingBox>
\t\t<min>{mins}</min>
\t\t<max>{maxs}</max>
\t</boundingBox>
</root>
""".format(
    shaderPath=shaderPath,
    texturePath=texturePath,
    mins=_formatVec(mins),
    maxs=_formatVec(maxs)
  )
  with open(path, 'w') as handle:
    handle.write(content)


def _ensureParent(path):
  directory = os.path.dirname(path)
  if directory and not os.path.isdir(directory):
    os.makedirs(directory)
