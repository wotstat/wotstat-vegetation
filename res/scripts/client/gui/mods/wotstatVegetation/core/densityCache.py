import ResMgr

from ..utils.logger import log


DESTRUCTIBLES_PATHS = (
  'scripts/destructibles.xml',
  'scripts/item_defs/destructibles.xml'
)


class VegetationDensityCache(object):

  def __init__(self):
    self._densities = None

  def metadataFor(self, assetPath, destrIndex):
    if self._densities is None:
      self._densities = self._loadDensities()

    return camouflageMetadataFor(assetPath, destrIndex, self._densities)

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
      log('loaded vegetation densities: assets=' + str(len(densities)))

    return densities


def camouflageMetadataFor(assetPath, destrIndex, densities):
  normalized = assetPath.lower()
  destructiblesDensity = densities.get(normalized)

  if _densityIsPositive(destructiblesDensity):
    if destrIndex is not None:
      camouflageAffects = True
      camouflageDensity = destructiblesDensity
      camouflageReason = 'density_and_destr_index'
    else:
      camouflageAffects = False
      camouflageDensity = 0.0
      camouflageReason = 'missing_destr_index'
  else:
    camouflageAffects = False
    camouflageDensity = 0.0
    camouflageReason = 'missing_or_zero_density'

  return {
    'resourcePath': normalized,
    'destructiblesDensity': destructiblesDensity,
    'camouflageAffects': camouflageAffects,
    'camouflageDensity': camouflageDensity,
    'camouflageReason': camouflageReason
  }


def _densityIsPositive(density):
  try:
    return float(density) > 0.0
  except (TypeError, ValueError):
    return False


def _loadFromDataSection(section):
  densities = {}
  _walkEntries(section, densities)
  return densities


def _walkEntries(section, densities):
  filename = section.readString('filename', '')
  density = section.readString('density', '')
  if filename and density:
    _addDensity(densities, filename, density)

  for child in section.values():
    _walkEntries(child, densities)


def _addDensity(densities, filename, density):
  normalized = filename.lower()
  if not normalized.startswith('vegetation/'):
    return

  try:
    densities[normalized] = float(density)
  except (TypeError, ValueError):
    log('invalid vegetation density for ' + normalized + ': ' + str(density))
