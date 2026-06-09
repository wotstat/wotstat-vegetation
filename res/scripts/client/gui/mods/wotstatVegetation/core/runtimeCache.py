import hashlib
import json
import os
import re


MOD_CACHE_DIR = 'wotstat-vegetation'
DEFAULT_CACHE_VERSION = 'runtime-v1'
EXPORT_FORMAT_VERSION = 'wot-collider-export-v2'
MAP_CACHE_FORMAT_VERSION = 3

GREEN_TEXTURE = 'mods/wotstat-vegetation/green.dds'
YELLOW_TEXTURE = 'mods/wotstat-vegetation/yellow.dds'
RED_TEXTURE = 'mods/wotstat-vegetation/red.dds'


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
  if not isinstance(value, basestring):
    value = str(value)
  if not isinstance(value, bytes):
    value = value.encode('utf-8')
  return hashlib.sha1(value).hexdigest()[:length]


def safeName(value, fallback='item'):
  value = str(value)
  name = os.path.splitext(value.rsplit('/', 1)[-1])[0]
  name = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('._-')
  return name or fallback


def colliderCacheKey(assetPath, density):
  normalized = assetPath.lower()
  variant = densityVariant(density)
  material = textureResourceForDensity(density)
  digest = stableDigest(
    normalized + '|density=' + str(density) + '|variant=' + variant +
    '|texture=' + material +
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
  normalized = arenaName.lower()
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
