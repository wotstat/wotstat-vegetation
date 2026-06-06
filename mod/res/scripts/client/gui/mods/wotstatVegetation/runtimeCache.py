import hashlib
import json
import os
import re


MOD_CACHE_DIR = 'wotstat-vegetation'
DEFAULT_CACHE_VERSION = 'runtime-v1'
EXPORT_FORMAT_VERSION = 'wot-collider-export-v1'
MAP_CACHE_FORMAT_VERSION = 2

GREEN_TEXTURE = 'mods/wotstat-vegetation/green.dds'
YELLOW_TEXTURE = 'mods/wotstat-vegetation/yellow.dds'
RED_TEXTURE = 'mods/wotstat-vegetation/red.dds'


try:
  string_types = (basestring,)
except NameError:
  string_types = (str,)


def cacheVersion(version):
  value = str(version or '').strip()
  if not value or value.startswith('{{'):
    return DEFAULT_CACHE_VERSION
  return value


def preferencesCacheRoot(preferencesPath):
  if not preferencesPath:
    return ''
  path = str(preferencesPath)
  normalized = path.replace('\\', '/')
  if normalized.lower().endswith('/preferences.xml') or normalized.lower().endswith('preferences.xml'):
    directory = os.path.dirname(path)
    if directory and directory != path:
      return directory
    parts = normalized.rsplit('/', 1)
    if len(parts) == 2:
      return parts[0]
  return path


def cacheRoot(preferencesPath, version):
  return os.path.join(
    preferencesCacheRoot(preferencesPath),
    'mods',
    MOD_CACHE_DIR,
    cacheVersion(version)
  )


def cachePaths(preferencesPath, version):
  root = cacheRoot(preferencesPath, version)
  return {
    'root': root,
    'colliders': os.path.join(root, 'colliders'),
    'maps': os.path.join(root, 'maps')
  }


def ensureDir(path):
  if path and not os.path.isdir(path):
    os.makedirs(path)


def normalizeResourcePath(value):
  if value is None:
    return ''
  if not isinstance(value, string_types):
    value = str(value)
  value = value.strip().replace('\\', '/')
  while value.startswith('./'):
    value = value[2:]
  if value.startswith('/'):
    value = value[1:]
  if value.lower().startswith('packages/'):
    value = value[len('packages/'):]
  return '/'.join([part for part in value.split('/') if part])


def normalizeResourcePathForKey(value):
  return normalizeResourcePath(value).lower()


def ensureSrtExtension(value):
  value = normalizeResourcePath(value)
  if value and not value.lower().endswith('.srt'):
    value += '.srt'
  return value


def stripSrtExtension(value):
  value = normalizeResourcePath(value)
  if value.lower().endswith('.srt'):
    return value[:-4]
  return value


def densityVariant(density):
  try:
    value = float(density)
  except (TypeError, ValueError):
    return 'red'
  if abs(value - 0.5) <= 0.0001:
    return 'green'
  if abs(value - 0.25) <= 0.0001:
    return 'yellow'
  return 'red'


def textureResourceForDensity(density):
  variant = densityVariant(density)
  if variant == 'green':
    return GREEN_TEXTURE
  if variant == 'yellow':
    return YELLOW_TEXTURE
  return RED_TEXTURE


def stableDigest(value, length=16):
  if not isinstance(value, string_types):
    value = str(value)
  if not isinstance(value, bytes):
    value = value.encode('utf-8')
  return hashlib.sha1(value).hexdigest()[:length]


def safeName(value, fallback='item'):
  value = normalizeResourcePath(value)
  if not value:
    return fallback
  name = os.path.splitext(value.replace('\\', '/').split('/')[-1])[0]
  name = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('._-')
  return name or fallback


def colliderCacheKey(assetPath, density):
  normalized = normalizeResourcePathForKey(ensureSrtExtension(assetPath))
  variant = densityVariant(density)
  material = textureResourceForDensity(density)
  digest = stableDigest(
    normalized + '|density=' + variant + '|texture=' + material +
    '|export=' + EXPORT_FORMAT_VERSION,
    20
  )
  return safeName(normalized, 'vegetation') + '-' + variant + '-' + digest


def colliderModelPaths(preferencesPath, version, assetPath, density):
  roots = cachePaths(preferencesPath, version)
  key = colliderCacheKey(assetPath, density)
  directory = os.path.join(roots['colliders'], key)
  base = os.path.join(directory, key)
  return {
    'key': key,
    'directory': directory,
    'base': base,
    'model': base + '.model',
    'visual': base + '.visual',
    'primitives': base + '.primitives',
    'obj': base + '.obj',
    'meta': base + '.json'
  }


def mapCachePath(preferencesPath, version, arenaName):
  roots = cachePaths(preferencesPath, version)
  normalized = normalizeResourcePathForKey(arenaName)
  name = safeName(normalized, 'map')
  return os.path.join(
    roots['maps'],
    name + '-' + stableDigest(normalized, 16) + '.json'
  )


def readJson(path):
  with open(path, 'r') as handle:
    return json.load(handle)


def writeJson(path, payload):
  ensureDir(os.path.dirname(path))
  tmpPath = path + '.tmp'
  with open(tmpPath, 'w') as handle:
    json.dump(payload, handle, sort_keys=True, separators=(',', ':'))
  if os.path.exists(path):
    os.remove(path)
  os.rename(tmpPath, path)


def validColliderFiles(paths):
  for key in ('model', 'visual', 'primitives'):
    if not os.path.isfile(paths[key]) or os.path.getsize(paths[key]) <= 0:
      return False
  return True


def validateMapPayload(payload, arenaName):
  return mapPayloadInvalidReason(payload, arenaName) is None


def mapPayloadInvalidReason(payload, arenaName):
  if not isinstance(payload, dict):
    return 'payload is not an object'
  if payload.get('arena') != arenaName:
    return 'arena mismatch'
  if payload.get('mapCacheFormatVersion') != MAP_CACHE_FORMAT_VERSION:
    return 'cache version mismatch'
  vegetation = payload.get('vegetation')
  if not isinstance(vegetation, list):
    return 'vegetation is not a list'
  for entry in vegetation:
    if not isinstance(entry, dict):
      return 'vegetation entry is not an object'
    if not entry.get('asset'):
      return 'vegetation entry missing asset'
    if 'visibilityMask' not in entry:
      return 'vegetation entry missing visibilityMask'
    try:
      int(entry.get('visibilityMask'))
    except Exception:
      return 'vegetation entry has invalid visibilityMask'
    matrix = entry.get('matrix')
    if not isinstance(matrix, list) or len(matrix) != 4:
      return 'vegetation entry has invalid matrix'
    for row in matrix:
      if not isinstance(row, list) or len(row) != 4:
        return 'vegetation entry has invalid matrix row'
    for derivedKey in (
      'gameModes',
      'possibleModes',
      'modeNames',
      'guessedModes',
      'visibilityMaskMeaning',
      'modeVisibility'
    ):
      if derivedKey in entry:
        return 'vegetation entry contains derived visibility field ' + derivedKey
  return None
