import ResMgr

from .unpack.spaceBinUnpacker import SpaceBinUnpackError, unpackVegetationFromSpaceBin
from .runtimeCache import MAP_CACHE_FORMAT_VERSION, mapCachePath, readJson, writeJson

from ..utils.logger import log


def loadMapVegetation(arenaName, preferencesPath, version):
  log('load map vegetation: map=' + arenaName)
  
  spacePath = 'spaces/' + arenaName + '/space.bin'
  cachePath = mapCachePath(preferencesPath, version, arenaName)

  payload = _readCachedMap(cachePath, arenaName)
  if payload is not None:
    vegetation = payload['vegetation']
  else:
    if not ResMgr.isFile(spacePath):
      log('space.bin not found for map: ' + arenaName)
      return None

    try:
      section = ResMgr.openSection(spacePath)
      vegetation = unpackVegetationFromSpaceBin(section.asBinary, sourcePath=spacePath)
    except SpaceBinUnpackError as error:
      log('failed to parse space.bin for ' + arenaName + ': ' + str(error))
      return None

    writeJson(cachePath, {
      'mapCacheFormatVersion': MAP_CACHE_FORMAT_VERSION,
      'version': version,
      'arena': arenaName,
      'spacePath': spacePath,
      'vegetation': vegetation
    })

  uniqueAssets = set([entry['asset'].lower() for entry in vegetation])
  log(
    'loaded map vegetation: map=' + arenaName +
    ' count=' + str(len(vegetation)) +
    ' unique_srt=' + str(len(uniqueAssets))
  )
  return vegetation


def _readCachedMap(cachePath, arenaName):
  try:
    payload = readJson(cachePath)
  except IOError:
    return None
  except Exception as error:
    log('map cache corrupt, regenerating ' + cachePath + ': ' + str(error))
    return None

  if not isinstance(payload, dict):
    log('map cache payload invalid, regenerating ' + cachePath)
    return None

  if payload.get('mapCacheFormatVersion') != MAP_CACHE_FORMAT_VERSION:
    log('map cache format changed, regenerating ' + cachePath)
    return None

  if payload.get('arena') != arenaName:
    log('map cache arena mismatch, regenerating ' + cachePath)
    return None

  vegetation = payload.get('vegetation')
  if not isinstance(vegetation, list):
    log('map cache vegetation payload invalid, regenerating ' + cachePath)
    return None

  for entry in vegetation:
    if not isinstance(entry, dict):
      log('map cache vegetation entry invalid, regenerating ' + cachePath)
      return None
    if 'destrIndex' not in entry:
      log('map cache missing destrIndex, regenerating ' + cachePath)
      return None

  return payload
