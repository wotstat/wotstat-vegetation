import AreaDestructibles
import DestructiblesCache

from ..utils.logger import log


_handlers = []
_managerClass = None
_originalOrderDestructibleDestroy = None


def registerTreeFallHandler(handler):
  global _managerClass
  global _originalOrderDestructibleDestroy

  if handler in _handlers:
    return True

  if _originalOrderDestructibleDestroy is None:
    _managerClass = AreaDestructibles.DestructiblesManager
    _originalOrderDestructibleDestroy = _managerClass.orderDestructibleDestroy

    def hookedOrderDestructibleDestroy(self, chunkID, dmgType, destrData, isNeedAnimation, *args, **kwargs):
      result = _originalOrderDestructibleDestroy(self, chunkID, dmgType, destrData, isNeedAnimation, *args, **kwargs)
      if dmgType == DestructiblesCache.DESTR_TYPE_TREE:
        destrIndex, fallYaw, fallPitchConstr, fallSpeed = DestructiblesCache.decodeFallenTree(destrData)
        for registeredHandler in list(_handlers):
          registeredHandler(chunkID, destrIndex, fallYaw, fallPitchConstr, fallSpeed, 'event')
      return result

    _managerClass.orderDestructibleDestroy = hookedOrderDestructibleDestroy
    log('tree fall hook installed')

  _handlers.append(handler)
  return True


def unregisterTreeFallHandler(handler):
  global _managerClass
  global _originalOrderDestructibleDestroy

  while handler in _handlers:
    _handlers.remove(handler)

  if not _handlers and _managerClass is not None:
    _managerClass.orderDestructibleDestroy = _originalOrderDestructibleDestroy
    _managerClass = None
    _originalOrderDestructibleDestroy = None
    log('tree fall hook removed')
