import os

import ResMgr

from .densityCache import VegetationDensityCache
from .runtimeCache import (
  colliderModelPaths,
  ensureDir,
  ensureSrtExtension,
  normalizeResourcePath,
  normalizeResourcePathForKey,
  readJson,
  textureResourceForDensity,
  validColliderFiles,
  writeJson
)
from .srtCollisionRuntime import parseSrtBinary, writeObj
from .wotModelExporter import exportColliderModel
from .logger import log as defaultLog


class VegetationColliderCache(object):

  def __init__(self, preferencesPath, version, logger=None):
    self.preferencesPath = preferencesPath
    self.version = version
    self.logger = logger or defaultLog
    self.densities = VegetationDensityCache(self.logger)
    self._modelPathByAsset = {}

  def ensureColliderModel(self, assetPath):
    assetPath = ensureSrtExtension(assetPath)
    normalizedAsset = normalizeResourcePath(assetPath)
    assetKey = normalizeResourcePathForKey(assetPath)

    if assetKey in self._modelPathByAsset:
      return self._modelPathByAsset[assetKey]

    density = self.densities.densityFor(normalizedAsset)
    paths = colliderModelPaths(self.preferencesPath, self.version, normalizedAsset, density)
    texture = textureResourceForDensity(density)

    if _validColliderCache(paths, normalizedAsset, texture, self.logger):
      self.logger(
        'collider cache hit: asset=' + normalizedAsset +
        ' density=' + str(density) +
        ' model=' + paths['model']
      )
      self._modelPathByAsset[assetKey] = paths['model']
      return paths['model']

    self.logger(
      'collider cache miss: asset=' + normalizedAsset +
      ' density=' + str(density) +
      ' texture=' + texture
    )

    try:
      modelPath = self._generateCollider(normalizedAsset, density, texture, paths)
    except Exception as error:
      self.logger('failed to generate collider for ' + normalizedAsset + ': ' + str(error))
      self._modelPathByAsset[assetKey] = None
      return None

    self._modelPathByAsset[assetKey] = modelPath
    return modelPath

  def _flipNormals(self, meshes):
    for mesh in meshes:
      mesh.triangles = [(a, c, b) for a, b, c in mesh.triangles]
    return meshes

  def _generateCollider(self, assetPath, density, texture, paths):
    data = _readResourceBinary(assetPath)
    geometry = parseSrtBinary(data, assetPath)
    meshes = geometry.collisionMeshes()
    if not meshes:
      raise ValueError('no COLLISION mesh found')

    meshes = self._flipNormals(meshes)

    ensureDir(paths['directory'])
    metadata = {
      'asset': assetPath,
      'density': density,
      'texture': texture,
      'lods': sorted(list(set([mesh.lod for mesh in meshes]))),
      'mesh_count': len(meshes)
    }
    writeObj(paths['obj'], meshes, metadata)

    resourceBase = os.path.splitext(paths['model'])[0].replace('\\', '/')
    result = exportColliderModel(paths['model'], meshes, texture, resourceBase)
    metadata.update({
      'key': paths['key'],
      'model': paths['model'],
      'visual': paths['visual'],
      'primitives': paths['primitives'],
      'obj': paths['obj'],
      'vertices': result['vertices'],
      'triangles': result['triangles'],
      'bbox': result['bbox']
    })
    writeJson(paths['meta'], metadata)

    self.logger(
      'generated collider model: asset=' + assetPath +
      ' vertices=' + str(result['vertices']) +
      ' triangles=' + str(result['triangles']) +
      ' model=' + paths['model']
    )
    return paths['model']


def _readResourceBinary(resourcePath):
  if not ResMgr.isFile(resourcePath):
    raise IOError('resource not found: ' + resourcePath)
  section = ResMgr.openSection(resourcePath)
  return section.asBinary


def _validColliderCache(paths, assetPath, texture, logger):
  if not validColliderFiles(paths):
    return False

  if not os.path.isfile(paths['meta']):
    logger('collider cache metadata missing, regenerating: ' + paths['meta'])
    return False

  try:
    meta = readJson(paths['meta'])
  except Exception as error:
    logger('collider cache metadata corrupt, regenerating ' + paths['meta'] + ': ' + str(error))
    return False

  if meta.get('asset') != assetPath or meta.get('texture') != texture:
    logger('collider cache metadata mismatch, regenerating: ' + paths['meta'])
    return False

  return True
