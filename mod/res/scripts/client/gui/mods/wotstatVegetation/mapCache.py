import ResMgr

from .spaceBinUnpacker import unpackVegetationFromSpaceBin
from .runtimeCache import (
  mapCachePath,
  normalizeResourcePathForKey,
  readJson,
  validateMapPayload,
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

  if not validateMapPayload(payload, arenaName):
    logger('map cache invalid, regenerating: ' + cachePath)
    return None

  return payload


def _logMapStats(logger, prefix, vegetation):
  unique = {}
  for entry in vegetation:
    asset = entry.get('asset')
    if asset:
      unique[normalizeResourcePathForKey(asset)] = True
  logger(
    prefix + ': vegetation count=' + str(len(vegetation)) +
    ' unique_srt=' + str(len(unique))
  )
