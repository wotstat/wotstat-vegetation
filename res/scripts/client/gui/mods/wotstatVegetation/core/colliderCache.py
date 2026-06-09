import os

import ResMgr

from .densityCache import VegetationDensityCache
from .runtimeCache import (
  colliderModelPaths,
  ensureDir,
  readJson,
  textureResourceForDensity,
  validColliderFiles,
  writeJson
)
from .unpack.srtCollisionUnpacker import parseSrtBinary, writeObj
from .unpack.wotModelExporter import exportColliderModel
from ..utils.logger import log


COLLIDER_CACHE_STATUS_NO_COLLIDER = 'no_collider'
NO_COLLIDER_REASON = 'no COLLISION mesh found'


class VegetationColliderCache(object):

  def __init__(self, preferencesPath, version):
    self.preferencesPath = preferencesPath
    self.version = version
    self.densities = VegetationDensityCache()
    self._modelPathByVariant = {}

  def ensureColliderModel(self, assetPath, densityMetadata):
    density = densityMetadata['camouflageDensity']
    paths = colliderModelPaths(self.preferencesPath, self.version, assetPath, density)
    texture = textureResourceForDensity(density)
    modelKey = paths['key']

    if modelKey in self._modelPathByVariant:
      return self._modelPathByVariant[modelKey]

    if _noColliderCacheHit(paths, assetPath, texture):
      self._modelPathByVariant[modelKey] = None
      return None

    if _validColliderCache(paths, assetPath, texture):
      self._modelPathByVariant[modelKey] = paths['model']
      return paths['model']

    try:
      modelPath = self._generateCollider(assetPath, densityMetadata, texture, paths)
    except ValueError as error:
      if str(error) != NO_COLLIDER_REASON:
        raise
      _writeNoColliderCache(paths, assetPath, densityMetadata, texture, str(error))
      self._modelPathByVariant[modelKey] = None
      return None

    self._modelPathByVariant[modelKey] = modelPath
    return modelPath

  def _generateCollider(self, assetPath, densityMetadata, texture, paths):
    if not ResMgr.isFile(assetPath):
      raise IOError('resource not found: ' + assetPath)
    data = ResMgr.openSection(assetPath).asBinary
    geometry = parseSrtBinary(data, assetPath)
    meshes = geometry.collisionMeshes()
    if not meshes:
      raise ValueError(NO_COLLIDER_REASON)

    for mesh in meshes:
      mesh.triangles = [(a, c, b) for a, b, c in mesh.triangles]

    ensureDir(paths['directory'])
    metadata = {
      'asset': assetPath,
      'density': densityMetadata['camouflageDensity'],
      'destructibles_density': densityMetadata['destructiblesDensity'],
      'camouflage_affects': densityMetadata['camouflageAffects'],
      'camouflage_density': densityMetadata['camouflageDensity'],
      'camouflage_reason': densityMetadata['camouflageReason'],
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

    return paths['model']

def _validColliderCache(paths, assetPath, texture):
  if not validColliderFiles(paths):
    return False

  if not os.path.isfile(paths['meta']):
    return False

  try:
    meta = readJson(paths['meta'])
  except Exception as error:
    log('collider cache metadata corrupt, regenerating ' + paths['meta'] + ': ' + str(error))
    return False

  if meta.get('asset') != assetPath or meta.get('texture') != texture:
    log('collider cache metadata mismatch, regenerating: ' + paths['meta'])
    return False

  return True


def _noColliderCacheHit(paths, assetPath, texture):
  if not os.path.isfile(paths['meta']):
    return False

  try:
    meta = readJson(paths['meta'])
  except Exception:
    return False

  if meta.get('status') != COLLIDER_CACHE_STATUS_NO_COLLIDER:
    return False
  if meta.get('asset') != assetPath or meta.get('texture') != texture:
    return False

  return True


def _writeNoColliderCache(paths, assetPath, densityMetadata, texture, reason):
  metadata = {
    'status': COLLIDER_CACHE_STATUS_NO_COLLIDER,
    'asset': assetPath,
    'density': densityMetadata['camouflageDensity'],
    'destructibles_density': densityMetadata['destructiblesDensity'],
    'camouflage_affects': densityMetadata['camouflageAffects'],
    'camouflage_density': densityMetadata['camouflageDensity'],
    'camouflage_reason': densityMetadata['camouflageReason'],
    'texture': texture,
    'reason': reason
  }
  ensureDir(paths['directory'])
  writeJson(paths['meta'], metadata)
