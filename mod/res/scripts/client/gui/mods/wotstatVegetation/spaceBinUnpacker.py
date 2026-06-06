import math
import struct


SECTION_META_SIZE = 24
SPTR_RECORD_SIZE = 80
BWT2_MIN_SETTINGS_SIZE = 20
CHUNK_ID_BIAS = 0x7f
MIN_CHUNK_COORD = -CHUNK_ID_BIAS
MAX_CHUNK_COORD = 0xff - CHUNK_ID_BIAS
WGDE_CHUNK_ENTRY_SIZE = 12
WGDE_SPAN_ENTRY_SIZE = 8
WGDE_OBJECT_ENTRY_SIZE = 4
WGDE_SPEEDTREE_OBJECT_FLAG = 0x80000000
WGDE_SPEEDTREE_INDEX_MASK = 0x7fffffff


class SpaceBinUnpackError(Exception):
  pass
def _isFinite(value):
  if hasattr(math, 'isfinite'):
    return math.isfinite(value)
  return value == value and value != float('inf') and value != float('-inf')

def unpackVegetationFromSpaceBin(binary):
  sections = _parseSectionTable(binary)
  assets = _parseAssetsByKey(_sectionData(binary, sections, b'BWST'))
  records = _parseSptr(_sectionData(binary, sections, b'SpTr'))
  terrainGrid = _parseTerrainGrid(_sectionDataOptional(binary, sections, b'BWT2'))
  destrIndices = _parseSpeedtreeDestrIndices(
    _sectionDataOptional(binary, sections, b'WGDE'),
    records,
    terrainGrid
  )

  vegetation = []
  for index, (assetKey, matrix) in enumerate(records):
    asset = assets.get(assetKey)
    if asset is not None:
      vegetation.append({
        'asset': asset,
        'chunkID': _chunkIdForMatrix(terrainGrid, matrix),
        'destrIndex': destrIndices[index],
        'matrix': matrix
      })

  return vegetation


def _parseSectionTable(data):
  root = _readSectionMeta(data, 0)
  if root['id'] != b'BWTB':
    raise SpaceBinUnpackError(
      'invalid root section: expected BWTB, got ' + _sectionIdToString(root['id'])
    )

  sections = []
  for index in range(root['rowsCount']):
    sections.append(_readSectionMeta(data, SECTION_META_SIZE + index * SECTION_META_SIZE))

  return sections


def _readSectionMeta(data, offset):
  _checkBounds(data, offset, SECTION_META_SIZE, 'section metadata')

  return {
    'id': data[offset:offset + 4],
    'offset': _readU32(data, offset + 8),
    'length': _readU32(data, offset + 16),
    'rowsCount': _readU32(data, offset + 20)
  }


def _sectionData(data, sections, sectionId):
  for section in sections:
    if section['id'] == sectionId:
      offset = section['offset']
      length = section['length']
      _checkBounds(data, offset, length, 'section ' + _sectionIdToString(sectionId))
      return data[offset:offset + length]

  raise SpaceBinUnpackError('section ' + _sectionIdToString(sectionId) + ' not found')


def _sectionDataOptional(data, sections, sectionId):
  for section in sections:
    if section['id'] == sectionId:
      offset = section['offset']
      length = section['length']
      _checkBounds(data, offset, length, 'section ' + _sectionIdToString(sectionId))
      return data[offset:offset + length]

  return None


def _parseAssetsByKey(section):
  entrySize = _readU32(section, 0)
  entryCount = _readU32(section, 4)

  if entrySize < 12:
    raise SpaceBinUnpackError('unsupported BWST entry size: ' + str(entrySize))

  entriesStart = 8
  entriesBytes = entrySize * entryCount
  stringsLenOffset = entriesStart + entriesBytes
  _checkBounds(section, stringsLenOffset, 4, 'BWST strings length')

  stringsLen = _readU32(section, stringsLenOffset)
  stringsStart = stringsLenOffset + 4
  stringsEnd = stringsStart + stringsLen
  _checkBounds(section, stringsStart, stringsLen, 'BWST strings')

  assets = {}
  for index in range(entryCount):
    entryOffset = entriesStart + index * entrySize
    _checkBounds(section, entryOffset, entrySize, 'BWST entry')

    storedKey = _readU32(section, entryOffset)
    stringRelOffset = _readU32(section, entryOffset + 4)
    stringLen = _readU32(section, entryOffset + 8)
    stringStart = stringsStart + stringRelOffset
    stringEnd = stringStart + stringLen

    if stringEnd > stringsEnd:
      raise SpaceBinUnpackError('BWST string out of bounds: index=' + str(index))

    assetName = _decodeString(section[stringStart:stringEnd])
    if assetName.lower().endswith('.srt') and storedKey not in assets:
      assets[storedKey] = assetName

  return assets


def _parseSptr(section):
  recordSize = _readU32(section, 0)
  recordCount = _readU32(section, 4)

  if recordSize != SPTR_RECORD_SIZE:
    raise SpaceBinUnpackError('unsupported SpTr record size: ' + str(recordSize))

  recordsStart = 8
  _checkBounds(section, recordsStart, recordCount * recordSize, 'SpTr records')

  records = []
  for index in range(recordCount):
    offset = recordsStart + index * recordSize
    records.append((_readU32(section, offset + 64), _readMatrix(section, offset)))

  return records


def _parseTerrainGrid(section):
  if section is None:
    return None

  settingsSize = _readU32(section, 0)
  if settingsSize < BWT2_MIN_SETTINGS_SIZE:
    raise SpaceBinUnpackError('unsupported BWT2 settings size: ' + str(settingsSize))

  _checkBounds(section, 4, settingsSize, 'BWT2 terrain settings')

  chunkSize = _readF32(section, 4)
  if not _isFinite(chunkSize) or chunkSize <= 0:
    raise SpaceBinUnpackError('invalid BWT2 chunk size: ' + str(chunkSize))

  minX = _readI32(section, 8)
  maxX = _readI32(section, 12)
  minZ = _readI32(section, 16)
  maxZ = _readI32(section, 20)

  if minX > maxX or minZ > maxZ:
    raise SpaceBinUnpackError(
      'invalid BWT2 bounds: min_x=' + str(minX) +
      ' max_x=' + str(maxX) +
      ' min_z=' + str(minZ) +
      ' max_z=' + str(maxZ)
    )

  for coord in (minX, maxX, minZ, maxZ):
    if coord < MIN_CHUNK_COORD or coord > MAX_CHUNK_COORD:
      raise SpaceBinUnpackError('BWT2 chunk coordinate out of encodable range: ' + str(coord))

  return {
    'chunkSize': chunkSize,
    'minX': minX,
    'maxX': maxX,
    'minZ': minZ,
    'maxZ': maxZ
  }


def _parseSpeedtreeDestrIndices(section, records, terrainGrid):
  speedtreeCount = len(records)
  destrIndices = [None] * speedtreeCount
  if section is None:
    return destrIndices

  chunkTable = _readWGDETable(section, 0, WGDE_CHUNK_ENTRY_SIZE)
  spanTable = _readWGDETable(section, chunkTable['end'], WGDE_SPAN_ENTRY_SIZE)

  if spanTable['end'] == len(section):
    return destrIndices

  objectTable = _readWGDETable(section, spanTable['end'], WGDE_OBJECT_ENTRY_SIZE)
  candidates = [[] for _ in range(speedtreeCount)]

  for chunkIndex in range(chunkTable['count']):
    chunkOffset = chunkTable['start'] + chunkIndex * chunkTable['entrySize']
    chunkId = _readU32(section, chunkOffset)
    spanStart = _readU32(section, chunkOffset + 4)
    spanCount = _readU32(section, chunkOffset + 8)

    if spanStart + spanCount > spanTable['count']:
      raise SpaceBinUnpackError('WGDE chunk span range out of bounds: index=' + str(chunkIndex))

    for localDestrIndex in range(spanCount):
      spanOffset = spanTable['start'] + (spanStart + localDestrIndex) * spanTable['entrySize']
      objectIndexes = (_readU32(section, spanOffset), _readU32(section, spanOffset + 4))
      objectValues = []

      for objectIndex in objectIndexes:
        if objectIndex >= objectTable['count']:
          raise SpaceBinUnpackError(
            'WGDE object index out of bounds: chunk_index=' + str(chunkIndex) +
            ' local_index=' + str(localDestrIndex)
          )

        value = _readU32(section, objectTable['start'] + objectIndex * objectTable['entrySize'])
        objectValues.append(value)

      speedtreeIndexes = []
      for value in objectValues:
        if value & WGDE_SPEEDTREE_OBJECT_FLAG == 0:
          continue

        speedtreeIndex = value & WGDE_SPEEDTREE_INDEX_MASK
        if speedtreeIndex >= speedtreeCount:
          continue

        if speedtreeIndex not in speedtreeIndexes:
          speedtreeIndexes.append(speedtreeIndex)

      for speedtreeIndex in speedtreeIndexes:
        speedtreeValue = WGDE_SPEEDTREE_OBJECT_FLAG | speedtreeIndex
        candidates[speedtreeIndex].append({
          'chunkID': chunkId,
          'destrIndex': localDestrIndex,
          'isSelfRow': objectValues[0] == speedtreeValue and objectValues[1] == speedtreeValue
        })

  for speedtreeIndex, speedtreeCandidates in enumerate(candidates):
    if not speedtreeCandidates:
      continue

    matrixChunkId = _chunkIdForMatrix(terrainGrid, records[speedtreeIndex][1])
    chunkCandidates = [
      candidate for candidate in speedtreeCandidates
      if candidate['chunkID'] == matrixChunkId
    ]
    if chunkCandidates:
      speedtreeCandidates = chunkCandidates

    selfCandidates = [
      candidate for candidate in speedtreeCandidates
      if candidate['isSelfRow']
    ]
    if selfCandidates:
      speedtreeCandidates = selfCandidates

    destrIndices[speedtreeIndex] = min(
      candidate['destrIndex'] for candidate in speedtreeCandidates
    )

  return destrIndices


def _readWGDETable(section, offset, expectedEntrySize):
  _checkBounds(section, offset, 8, 'WGDE table header')

  entrySize = _readU32(section, offset)
  entryCount = _readU32(section, offset + 4)

  if entrySize != expectedEntrySize:
    raise SpaceBinUnpackError(
      'unsupported WGDE entry size at offset ' + str(offset) +
      ': expected ' + str(expectedEntrySize) +
      ', got ' + str(entrySize)
    )

  tableStart = offset + 8
  tableBytes = entrySize * entryCount
  _checkBounds(section, tableStart, tableBytes, 'WGDE table')
  return {
    'start': tableStart,
    'end': tableStart + tableBytes,
    'entrySize': entrySize,
    'count': entryCount
  }


def _chunkIdForMatrix(terrainGrid, matrix):
  if terrainGrid is None:
    return None

  chunkSize = terrainGrid['chunkSize']
  x = _clampInt(int(math.floor(matrix[3][0] / chunkSize)), terrainGrid['minX'], terrainGrid['maxX'])
  z = _clampInt(int(math.floor(matrix[3][2] / chunkSize)), terrainGrid['minZ'], terrainGrid['maxZ'])
  return ((x + CHUNK_ID_BIAS) << 8) | (z + CHUNK_ID_BIAS)


def _clampInt(value, minimum, maximum):
  return max(minimum, min(maximum, value))


def _decodeString(raw):
  if raw.endswith(b'\x00'):
    raw = raw[:-1]
  return raw.decode('utf-8', 'replace')


def _readMatrix(data, offset):
  _checkBounds(data, offset, 64, 'matrix')
  values = struct.unpack_from('<16f', data, offset)
  return [
    list(values[0:4]),
    list(values[4:8]),
    list(values[8:12]),
    list(values[12:16])
  ]


def _readU32(data, offset):
  _checkBounds(data, offset, 4, 'u32')
  return struct.unpack_from('<I', data, offset)[0]


def _readI32(data, offset):
  _checkBounds(data, offset, 4, 'i32')
  return struct.unpack_from('<i', data, offset)[0]


def _readF32(data, offset):
  _checkBounds(data, offset, 4, 'f32')
  return struct.unpack_from('<f', data, offset)[0]


def _sectionIdToString(sectionId):
  return sectionId.decode('ascii', 'replace')


def _checkBounds(data, offset, size, label):
  if offset < 0 or size < 0 or offset + size > len(data):
    raise SpaceBinUnpackError(label + ' out of bounds at offset ' + str(offset))
