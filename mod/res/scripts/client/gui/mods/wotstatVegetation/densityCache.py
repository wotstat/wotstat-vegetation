import re

import ResMgr

from .runtimeCache import ensureSrtExtension, normalizeResourcePathForKey, stripSrtExtension
from .logger import log as defaultLog


ENTRY_RE = re.compile(r'<entry>\s*(.*?)\s*</entry>', re.S)
TEXT_TAG_RE = r'<{tag}>\s*([^<]+?)\s*</{tag}>'
DESTRUCTIBLES_PATHS = (
  'scripts/destructibles.xml',
  'scripts/item_defs/destructibles.xml'
)


class VegetationDensityCache(object):

  def __init__(self, logger=None):
    self._logger = logger or defaultLog
    self._densities = None

  def densityFor(self, assetPath):
    if self._densities is None:
      self._densities = self._load()

    normalized = normalizeResourcePathForKey(assetPath)
    withoutSrt = normalizeResourcePathForKey(stripSrtExtension(assetPath))
    if normalized in self._densities:
      return self._densities[normalized]
    return self._densities.get(withoutSrt)

  def _load(self):
    densities = {}

    for path in DESTRUCTIBLES_PATHS:
      section = _openSection(path)
      if section is None:
        continue

      sectionDensities = _loadFromDataSection(section)
      if not sectionDensities:
        sectionDensities = _loadFromText(_sectionText(section))

      if sectionDensities:
        densities.update(sectionDensities)
        self._logger(
          'loaded vegetation densities from ' + path +
          ': keys=' + str(len(sectionDensities)) +
          ' assets=' + str(len(sectionDensities) // 2)
        )
      else:
        self._logger('destructibles density source had no vegetation entries: ' + path)

    if not densities:
      self._logger('destructibles.xml not found or unreadable, vegetation density is unknown')

    return densities


def _tagText(block, tag):
  match = re.search(TEXT_TAG_RE.format(tag=re.escape(tag)), block)
  if not match:
    return None
  return match.group(1).strip()


def _openSection(path):
  try:
    exists = not hasattr(ResMgr, 'isFile') or ResMgr.isFile(path)
  except Exception:
    exists = True

  try:
    section = ResMgr.openSection(path)
  except Exception:
    return None
  if section is None and not exists:
    return None
  return section


def _loadFromText(text):
  densities = {}
  if not text:
    return densities

  for block in ENTRY_RE.findall(text):
    _addDensity(
      densities,
      _tagText(block, 'filename'),
      _tagText(block, 'density')
    )
  return densities


def _loadFromDataSection(section):
  densities = {}
  _walkEntries(section, densities)
  return densities


def _walkEntries(section, densities):
  if section is None:
    return

  filename = _readString(section, 'filename')
  density = _readString(section, 'density')
  if filename and density:
    _addDensity(densities, filename, density)

  for _name, child in _children(section):
    _walkEntries(child, densities)


def _addDensity(densities, filename, density):
  if not filename or density is None:
    return

  normalized = normalizeResourcePathForKey(filename)
  if not normalized.startswith('vegetation/'):
    return

  try:
    value = float(density)
  except (TypeError, ValueError):
    return

  withSrt = normalizeResourcePathForKey(ensureSrtExtension(normalized))
  withoutSrt = normalizeResourcePathForKey(stripSrtExtension(normalized))
  densities[withSrt] = value
  densities[withoutSrt] = value


def _readString(section, name):
  try:
    if hasattr(section, 'readString'):
      value = section.readString(name, '')
      if value:
        return str(value).strip()
  except Exception:
    pass

  try:
    child = section[name]
    return _sectionScalar(child)
  except Exception:
    return None


def _children(section):
  seen = {}

  for child in _childrenFromValues(section):
    key = id(child)
    if key not in seen:
      seen[key] = True
      yield _sectionName(child), child

  for name, child in _childrenFromItems(section):
    key = id(child)
    if key not in seen:
      seen[key] = True
      yield name, child

  for name, child in _childrenFromKeys(section):
    key = id(child)
    if key not in seen:
      seen[key] = True
      yield name, child


def _childrenFromValues(section):
  try:
    values = section.values()
  except Exception:
    return []
  return [child for child in values if child is not None]


def _childrenFromItems(section):
  try:
    items = section.items()
  except Exception:
    return []

  result = []
  for item in items:
    try:
      name, child = item
    except Exception:
      continue
    if child is not None:
      result.append((name, child))
  return result


def _childrenFromKeys(section):
  try:
    keys = section.keys()
  except Exception:
    return []

  result = []
  for name in keys:
    try:
      child = section[name]
    except Exception:
      continue
    if child is not None:
      result.append((name, child))
  return result


def _sectionName(section):
  for attr in ('name', 'sectionName'):
    try:
      value = getattr(section, attr)
      if value:
        return str(value)
    except Exception:
      pass
  return ''


def _sectionScalar(section):
  for attr in ('asString', 'asWideString', 'asFloat', 'asInt', 'asBinary'):
    try:
      value = getattr(section, attr)
      if value is not None:
        return str(value).strip()
    except Exception:
      pass

  for method in ('readString', 'readFloat', 'readInt'):
    try:
      reader = getattr(section, method)
      value = reader('', '')
      if value is not None and value != '':
        return str(value).strip()
    except Exception:
      pass

  return None


def _sectionText(section):
  for attr in ('asBinary', 'asString', 'asWideString'):
    try:
      value = getattr(section, attr)
      if value:
        return str(value)
    except Exception:
      pass
  return ''
