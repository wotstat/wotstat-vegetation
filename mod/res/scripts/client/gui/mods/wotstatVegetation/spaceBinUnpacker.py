import struct


SECTION_META_SIZE = 24
SPTR_RECORD_SIZE = 80


class SpaceBinUnpackError(Exception):
  pass


def unpackVegetationFromSpaceBin(binary):
  sections = _parseSectionTable(binary)
  assets = _parseAssetsByKey(_sectionData(binary, sections, b'BWST'))
  records = _parseSptr(_sectionData(binary, sections, b'SpTr'))

  vegetation = []
  for assetKey, matrix in records:
    asset = assets.get(assetKey)
    if asset is not None:
      vegetation.append({'asset': asset, 'matrix': matrix})

  return vegetation


def _parseSectionTable(data):
  root = _readSectionMeta(data, 0)
  if root['id'] != b'BWTB':
    raise SpaceBinUnpackError('invalid root section: expected BWTB, got ' + root['id'])

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
      _checkBounds(data, offset, length, 'section ' + sectionId)
      return data[offset:offset + length]

  raise SpaceBinUnpackError('section ' + sectionId + ' not found')


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


def _checkBounds(data, offset, size, label):
  if offset < 0 or size < 0 or offset + size > len(data):
    raise SpaceBinUnpackError(label + ' out of bounds at offset ' + str(offset))
