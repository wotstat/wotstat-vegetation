import ResMgr

from .spaceBinUnpacker import SpaceBinUnpackError, unpackVegetationFromSpaceBin
from .runtimeCache import MAP_CACHE_FORMAT_VERSION, mapCachePath, readJson, writeJson

from .logger import log


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
    return readJson(cachePath)
  except IOError:
    return None
  except Exception as error:
    log('map cache corrupt, regenerating ' + cachePath + ': ' + str(error))
    return None
