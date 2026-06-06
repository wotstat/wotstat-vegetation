import ResMgr

from .spaceBinUnpacker import unpackVegetationFromSpaceBin
from .runtimeCache import (
  MAP_CACHE_FORMAT_VERSION,
  mapPayloadInvalidReason,
  mapCachePath,
  normalizeResourcePathForKey,
  readJson,
  writeJson
)
from .logger import log as defaultLog


def loadMapVegetation(arenaName, preferencesPath, version, logger=None):
  logger = logger or defaultLog
  spacePath = 'spaces/' + arenaName + '/space.bin'
  cachePath = mapCachePath(preferencesPath, version, arenaName)

  logger('current map: ' + arenaName + ' space=' + spacePath)

  payload = _readCachedMap(cachePath, arenaName, logger)
  if payload is not None:
    vegetation = payload['vegetation']
    _logMapStats(logger, 'map cache hit', vegetation)
    return vegetation

  logger('map cache miss: ' + cachePath)
  if not ResMgr.isFile(spacePath):
    logger('space.bin not found for map: ' + arenaName)
    return None

  try:
    section = ResMgr.openSection(spacePath)
    vegetation = unpackVegetationFromSpaceBin(section.asBinary)
  except Exception as error:
    logger('failed to parse space.bin for ' + arenaName + ': ' + str(error))
    return None

  _logMapStats(logger, 'parsed space.bin', vegetation)
  try:
    writeJson(cachePath, {
      'mapCacheFormatVersion': MAP_CACHE_FORMAT_VERSION,
      'version': version,
      'arena': arenaName,
      'spacePath': spacePath,
      'vegetation': vegetation
    })
    logger('wrote map cache: ' + cachePath)
  except Exception as error:
    logger('failed to write map cache ' + cachePath + ': ' + str(error))

  return vegetation


def _readCachedMap(cachePath, arenaName, logger):
  try:
    payload = readJson(cachePath)
  except IOError:
    return None
  except Exception as error:
    logger('map cache corrupt, regenerating ' + cachePath + ': ' + str(error))
    return None

  invalidReason = mapPayloadInvalidReason(payload, arenaName)
  if invalidReason is not None:
    logger('map cache invalid, regenerating: ' + cachePath + ' reason=' + invalidReason)
    return None

  return payload


def _logMapStats(logger, prefix, vegetation):
  unique = {}
  masks = {}
  for entry in vegetation:
    asset = entry.get('asset')
    if asset:
      unique[normalizeResourcePathForKey(asset)] = True
    if 'visibilityMask' in entry:
      try:
        mask = int(entry.get('visibilityMask')) & 0xffffffff
        masks[mask] = masks.get(mask, 0) + 1
      except Exception:
        masks['invalid'] = masks.get('invalid', 0) + 1
  numericMasks = []
  for key in masks.keys():
    if key != 'invalid':
      numericMasks.append(key)
  maskText = ','.join([
    ('0x%08x' % mask) + ':' + str(masks[mask])
    for mask in sorted(numericMasks)
  ])
  if 'invalid' in masks:
    if maskText:
      maskText += ','
    maskText += 'invalid:' + str(masks['invalid'])
  logger(
    prefix + ': vegetation count=' + str(len(vegetation)) +
    ' unique_srt=' + str(len(unique)) +
    ' visibility_masks=' + (maskText or 'none')
  )
