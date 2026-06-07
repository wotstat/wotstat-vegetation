#!/usr/bin/env python3
import os
import shutil
import sys
import tempfile
import types


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MOD_SCRIPTS = os.path.join(ROOT, 'mod', 'res', 'scripts', 'client', 'gui', 'mods')
sys.path.insert(0, MOD_SCRIPTS)
sys.modules.setdefault('BigWorld', types.ModuleType('BigWorld'))
sys.modules.setdefault('ResMgr', types.ModuleType('ResMgr'))

from wotstatVegetation.runtimeCache import (  # noqa: E402
  MAP_CACHE_FORMAT_VERSION,
  cachePaths,
  cacheVersion,
  colliderCacheKey,
  colliderModelPaths,
  densityVariant,
  mapPayloadInvalidReason,
  mapCachePath,
  preferencesCacheRoot,
  readJson,
  textureResourceForDensity,
  validateMapPayload,
  writeJson
)
from wotstatVegetation.wotModelExporter import exportColliderModel  # noqa: E402
from wotstatVegetation.spaceBinUnpacker import _chunkIdForMatrix  # noqa: E402
import wotstatVegetation.colliderCache as colliderCacheModule  # noqa: E402
from wotstatVegetation.colliderCache import VegetationColliderCache  # noqa: E402
from wotstatVegetation.densityCache import (  # noqa: E402
  _loadFromDataSection,
  _loadFromText,
  _loadNameListFromText,
  camouflageMetadataFor
)


def check(condition, message):
  if not condition:
    raise AssertionError(message)


class FakeSection(object):

  def __init__(self, children=None, value=None):
    self._children = children or []
    self.asString = value

  def readString(self, name, default=''):
    for childName, child in self._children:
      if childName == name:
        return child.asString
    return default

  def values(self):
    return [child for _name, child in self._children]

  def items(self):
    return list(self._children)

  def keys(self):
    return [name for name, _child in self._children]

  def __getitem__(self, name):
    for childName, child in self._children:
      if childName == name:
        return child
    raise KeyError(name)


class FakeDensityMetadata(object):

  def metadataFor(self, _asset):
    return {
      'camouflageDensity': None,
      'destructiblesDensity': None,
      'vegetationList': 'unlisted',
      'camouflageAffects': None,
      'camouflageReason': 'not_enough_metadata'
    }


class FakeSrtGeometryWithoutCollision(object):

  def collisionMeshes(self):
    return []


def main():
  tempdir = tempfile.mkdtemp(prefix='wotstat-vegetation-smoke-')
  try:
    paths = cachePaths(tempdir, '1.2.3')
    check(
      paths['colliders'] == os.path.join(tempdir, 'mods', 'wotstat-vegetation', '1.2.3', 'colliders'),
      'collider cache path'
    )
    check(
      paths['maps'] == os.path.join(tempdir, 'mods', 'wotstat-vegetation', '1.2.3', 'maps'),
      'map cache path'
    )
    check(cacheVersion('{{VERSION}}') == 'runtime-v1', 'template version fallback')
    preferencesXml = os.path.join(tempdir, 'preferences.xml')
    check(preferencesCacheRoot(preferencesXml) == tempdir, 'preferences.xml root normalization')
    xmlPaths = cachePaths(preferencesXml, '1.2.3')
    check(
      xmlPaths['maps'] == os.path.join(tempdir, 'mods', 'wotstat-vegetation', '1.2.3', 'maps'),
      'preferences.xml cache path'
    )

    check(densityVariant(0.5) == 'green', '0.5 density variant')
    check(densityVariant(0.25) == 'yellow', '0.25 density variant')
    check(densityVariant(None) == 'red', 'unknown density variant')
    check(textureResourceForDensity(0.5) == 'mods/wotstat-vegetation/green.dds', 'green texture')
    check(textureResourceForDensity(0.25) == 'mods/wotstat-vegetation/yellow.dds', 'yellow texture')
    check(textureResourceForDensity(0.1) == 'mods/wotstat-vegetation/red.dds', 'red texture')

    densityText = '''
      <root>
        <entry>
          <filename>vegetation/Broadleaves/Oak_dry/Oak_dry_20m</filename>
          <density>0.5</density>
        </entry>
      </root>
    '''
    textDensities = _loadFromText(densityText)
    check(textDensities['vegetation/broadleaves/oak_dry/oak_dry_20m.srt'] == 0.5, 'text density with srt key')
    check(textDensities['vegetation/broadleaves/oak_dry/oak_dry_20m'] == 0.5, 'text density stem key')

    dataSection = FakeSection(children=[
      ('entries', FakeSection(children=[
        ('entry', FakeSection(children=[
          ('filename', FakeSection(value='vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_5m.srt')),
          ('density', FakeSection(value='0.25'))
        ]))
      ]))
    ])
    sectionDensities = _loadFromDataSection(dataSection)
    check(sectionDensities['vegetation/broadleaves/shrubs/bush_wild/bush_wild_5m.srt'] == 0.25, 'section density with srt key')
    check(sectionDensities['vegetation/broadleaves/shrubs/bush_wild/bush_wild_5m'] == 0.25, 'section density stem key')

    nameList = _loadNameListFromText('''
      <root>
        <Bush_Wild_5m/>
        <Pine_Young_almoust_2m/>
      </root>
    ''')
    check('bush_wild_5m' in nameList, 'vegetation list name parsed')
    check('pine_young_almoust_2m' in nameList, 'vegetation list mixed case parsed')
    check('root' not in nameList, 'vegetation list root ignored')

    vegetationLists = {
      'bushes': set(['bush_wild_5m']),
      'grassBushes': set(['pine_young_almoust_2m'])
    }
    grassMetadata = camouflageMetadataFor(
      'vegetation/Conifers/Pine_Young/Pine_Young_almoust_2m.srt',
      {
        'vegetation/conifers/pine_young/pine_young_almoust_2m.srt': 0.5,
        'vegetation/conifers/pine_young/pine_young_almoust_2m': 0.5
      },
      vegetationLists
    )
    check(grassMetadata['destructiblesDensity'] == 0.5, 'grass bush keeps raw destructibles density')
    check(grassMetadata['camouflageAffects'] is False, 'grass bush does not affect camouflage')
    check(grassMetadata['camouflageDensity'] == 0.0, 'grass bush effective camouflage density is zero')
    check(densityVariant(grassMetadata['camouflageDensity']) == 'red', 'grass bush renders red')

    bushMetadata = camouflageMetadataFor(
      'vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_5m.srt',
      sectionDensities,
      vegetationLists
    )
    check(bushMetadata['camouflageAffects'] is True, 'bush with density affects camouflage')
    check(bushMetadata['camouflageDensity'] == 0.25, 'bush uses destructibles density as camouflage density')

    unknownMetadata = camouflageMetadataFor(
      'vegetation/Broadleaves/Unknown/Unknown_5m.srt',
      {},
      vegetationLists
    )
    check(unknownMetadata['camouflageAffects'] is None, 'missing density camouflage is unknown')
    check(unknownMetadata['camouflageDensity'] is None, 'missing density effective density is unknown')

    asset = 'vegetation/Broadleaves/Oak_dry/Oak_dry_20m.srt'
    greenKey = colliderCacheKey(asset, 0.5)
    sameGreenKey = colliderCacheKey('packages/' + asset.upper(), 0.5)
    yellowKey = colliderCacheKey(asset, 0.25)
    check(greenKey == sameGreenKey, 'stable normalized collider key')
    check(greenKey != yellowKey, 'density affects collider key')

    modelPaths = colliderModelPaths(tempdir, '1.2.3', asset, 0.5)
    check(modelPaths['model'].endswith('.model'), 'model extension')
    check(modelPaths['visual'].endswith('.visual'), 'visual extension')
    check(modelPaths['primitives'].endswith('.primitives'), 'primitives extension')
    check(modelPaths['obj'].endswith('.obj'), 'debug obj extension')

    mapPath = mapCachePath(tempdir, '1.2.3', '01_karelia')
    payload = {
      'mapCacheFormatVersion': MAP_CACHE_FORMAT_VERSION,
      'arena': '01_karelia',
      'vegetation': [{
        'asset': asset,
        'chunkID': 1,
        'destrIndex': None,
        'visibilityMask': 1,
        'matrix': [
          [1.0, 0.0, 0.0, 0.0],
          [0.0, 1.0, 0.0, 0.0],
          [0.0, 0.0, 1.0, 0.0],
          [10.0, 0.0, 20.0, 1.0]
        ]
      }]
    }
    check(validateMapPayload(payload, '01_karelia'), 'map payload validation')
    check(mapPayloadInvalidReason(payload, '01_karelia') is None, 'map payload invalid reason')
    writeJson(mapPath, payload)
    check(validateMapPayload(readJson(mapPath), '01_karelia'), 'map cache json readback')
    oldPayload = dict(payload)
    del oldPayload['mapCacheFormatVersion']
    check(not validateMapPayload(oldPayload, '01_karelia'), 'old map cache version rejected')
    missingMaskPayload = dict(payload)
    missingMaskPayload['vegetation'] = [dict(payload['vegetation'][0])]
    del missingMaskPayload['vegetation'][0]['visibilityMask']
    check(not validateMapPayload(missingMaskPayload, '01_karelia'), 'missing visibility mask rejected')
    derivedPayload = dict(payload)
    derivedPayload['vegetation'] = [dict(payload['vegetation'][0])]
    derivedPayload['vegetation'][0]['modeVisibility'] = {'guessed': True}
    check(not validateMapPayload(derivedPayload, '01_karelia'), 'derived visibility fields rejected')
    chunkID = _chunkIdForMatrix(
      {'chunkSize': 100.0, 'minX': -1, 'maxX': 1, 'minZ': -1, 'maxZ': 1},
      payload['vegetation'][0]['matrix']
    )
    check(isinstance(chunkID, int), 'chunk id is integer')

    mesh = type('Mesh', (), {})()
    mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    mesh.triangles = [(0, 1, 2)]
    exportBase = os.path.join(tempdir, 'export', 'triangle.model')
    exportColliderModel(exportBase, [mesh], 'mods/wotstat-vegetation/red.dds')
    check(os.path.isfile(exportBase), 'exported model file')
    check(os.path.isfile(exportBase.replace('.model', '.visual')), 'exported visual file')
    check(os.path.isfile(exportBase.replace('.model', '.primitives')), 'exported primitives file')
    with open(exportBase.replace('.model', '.visual'), 'r') as handle:
      check('mods/wotstat-vegetation/red.dds' in handle.read(), 'visual texture reference')

    originalReadResourceBinary = colliderCacheModule._readResourceBinary
    originalParseSrtBinary = colliderCacheModule.parseSrtBinary
    parseCalls = {'count': 0}

    def fakeReadResourceBinary(_assetPath):
      return b'srt'

    def fakeParseSrtBinary(_data, _assetPath):
      parseCalls['count'] += 1
      return FakeSrtGeometryWithoutCollision()

    colliderCacheModule._readResourceBinary = fakeReadResourceBinary
    colliderCacheModule.parseSrtBinary = fakeParseSrtBinary
    try:
      noColliderCache = VegetationColliderCache(tempdir, '1.2.3')
      noColliderCache.densities = FakeDensityMetadata()
      noColliderAsset = 'vegetation/Grass/Moss/Moss_lod0.srt'
      check(noColliderCache.ensureColliderModel(noColliderAsset) is None, 'no-collider asset returns no model')
      check(parseCalls['count'] == 1, 'no-collider asset parsed first time')

      noColliderMeta = colliderModelPaths(tempdir, '1.2.3', noColliderAsset, None)['meta']
      noColliderPayload = readJson(noColliderMeta)
      check(noColliderPayload['status'] == 'no_collider', 'no-collider cache status stored')
      check(noColliderPayload['asset'] == noColliderAsset, 'no-collider asset stored')

      noColliderCache2 = VegetationColliderCache(tempdir, '1.2.3')
      noColliderCache2.densities = FakeDensityMetadata()
      check(noColliderCache2.ensureColliderModel(noColliderAsset) is None, 'no-collider cache returns no model')
      check(parseCalls['count'] == 1, 'no-collider cache hit skips reparsing')
    finally:
      colliderCacheModule._readResourceBinary = originalReadResourceBinary
      colliderCacheModule.parseSrtBinary = originalParseSrtBinary
  finally:
    shutil.rmtree(tempdir)

  print('smoke_runtime_cache: ok')


if __name__ == '__main__':
  main()
