import ResMgr

from .runtimeCache import ensureSrtExtension, normalizeResourcePathForKey, stripSrtExtension
from .logger import log


DESTRUCTIBLES_PATHS = (
  'scripts/destructibles.xml',
  'scripts/item_defs/destructibles.xml'
)
VEGETATION_LIST_PATHS = {
  'bushes': 'vegetation/bushes.xml',
  'grassBushes': 'vegetation/grassBushes.xml'
}


class VegetationDensityCache(object):

  def __init__(self):
    self._densities = None
    self._vegetationLists = None

  def metadataFor(self, assetPath):
    if self._densities is None:
      self._densities = self._loadDensities()
    if self._vegetationLists is None:
      self._vegetationLists = self._loadVegetationLists()

    return camouflageMetadataFor(assetPath, self._densities, self._vegetationLists)

  def _loadDensities(self):
    densities = {}

    for path in DESTRUCTIBLES_PATHS:
      section = ResMgr.openSection(path)
      if section is None:
        continue

      densities.update(_loadFromDataSection(section))

    if not densities:
      log('destructibles.xml not found or unreadable, vegetation density is unknown')
    else:
      log('loaded vegetation densities: assets=' + str(len(densities) // 2))

    return densities

  def _loadVegetationLists(self):
    result = {
      'bushes': set(),
      'grassBushes': set()
    }

    for listName, path in VEGETATION_LIST_PATHS.items():
      section = ResMgr.openSection(path)
      if section is None:
        log('vegetation list not found or unreadable: ' + path)
        continue

      result[listName] = _loadNameListFromDataSection(section)

    log(
      'loaded vegetation lists: bushes=' + str(len(result['bushes'])) +
      ' grassBushes=' + str(len(result['grassBushes']))
    )

    return result


def camouflageMetadataFor(assetPath, densities, vegetationLists, hasCollisionMesh=True):
  normalized = normalizeResourcePathForKey(assetPath)
  withoutSrt = normalizeResourcePathForKey(stripSrtExtension(assetPath))
  if normalized in densities:
    destructiblesDensity = densities[normalized]
  else:
    destructiblesDensity = densities.get(withoutSrt)

  stem = _resourceStem(assetPath)
  bushes = vegetationLists.get('bushes', set())
  grassBushes = vegetationLists.get('grassBushes', set())

  if stem in grassBushes:
    vegetationList = 'grassBushes'
    camouflageAffects = False
    camouflageReason = 'listed_in_grassBushes'
  elif stem in bushes:
    vegetationList = 'bushes'
    camouflageAffects = bool(hasCollisionMesh and destructiblesDensity is not None)
    camouflageReason = 'listed_in_bushes' if camouflageAffects else 'missing_collision_or_density'
  else:
    vegetationList = 'unlisted'
    if hasCollisionMesh and destructiblesDensity is not None:
      camouflageAffects = True
      camouflageReason = 'collision_mesh_with_destructibles_density'
    else:
      camouflageAffects = None
      camouflageReason = 'not_enough_metadata'

  if camouflageAffects is True:
    camouflageDensity = destructiblesDensity
  elif camouflageAffects is False:
    camouflageDensity = 0.0
  else:
    camouflageDensity = None

  return {
    'resourcePath': normalized,
    'stem': stem,
    'vegetationList': vegetationList,
    'destructiblesDensity': destructiblesDensity,
    'camouflageAffects': camouflageAffects,
    'camouflageDensity': camouflageDensity,
    'camouflageReason': camouflageReason
  }


def _loadFromDataSection(section):
  densities = {}
  _walkEntries(section, densities)
  return densities


def _loadNameListFromDataSection(section):
  names = set()
  for child in section.values():
    if child.name != 'root':
      names.add(child.name.lower())
    _collectNameListChildren(child, names)
  return names


def _collectNameListChildren(section, names):
  for child in section.values():
    if child.name != 'root':
      names.add(child.name.lower())
    _collectNameListChildren(child, names)


def _resourceStem(assetPath):
  value = stripSrtExtension(assetPath)
  if not value:
    return ''
  value = value.replace('\\', '/')
  return value.rsplit('/', 1)[-1].lower()


def _walkEntries(section, densities):
  filename = section.readString('filename', '')
  density = section.readString('density', '')
  if filename and density:
    _addDensity(densities, filename, density)

  for child in section.values():
    _walkEntries(child, densities)


def _addDensity(densities, filename, density):
  if not filename or density is None:
    return

  normalized = normalizeResourcePathForKey(filename)
  if not normalized.startswith('vegetation/'):
    return

  value = float(density)

  withSrt = normalizeResourcePathForKey(ensureSrtExtension(normalized))
  withoutSrt = normalizeResourcePathForKey(stripSrtExtension(normalized))
  densities[withSrt] = value
  densities[withoutSrt] = value
