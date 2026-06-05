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
  cachePaths,
  cacheVersion,
  colliderCacheKey,
  colliderModelPaths,
  densityVariant,
  mapCachePath,
  preferencesCacheRoot,
  readJson,
  textureResourceForDensity,
  validateMapPayload,
  writeJson
)
from wotstatVegetation.wotModelExporter import exportColliderModel  # noqa: E402
from wotstatVegetation.spaceBinUnpacker import _chunkIdForMatrix  # noqa: E402
from wotstatVegetation.densityCache import _loadFromDataSection, _loadFromText  # noqa: E402


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
      'arena': '01_karelia',
      'vegetation': [{
        'asset': asset,
        'chunkID': 1,
        'destrIndex': None,
        'matrix': [
          [1.0, 0.0, 0.0, 0.0],
          [0.0, 1.0, 0.0, 0.0],
          [0.0, 0.0, 1.0, 0.0],
          [10.0, 0.0, 20.0, 1.0]
        ]
      }]
    }
    check(validateMapPayload(payload, '01_karelia'), 'map payload validation')
    writeJson(mapPath, payload)
    check(validateMapPayload(readJson(mapPath), '01_karelia'), 'map cache json readback')
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
  finally:
    shutil.rmtree(tempdir)

  print('smoke_runtime_cache: ok')


if __name__ == '__main__':
  main()
