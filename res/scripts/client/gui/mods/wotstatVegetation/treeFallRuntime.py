_handlers = []
_hookedManagerClass = None
_originalOrderDestructibleDestroy = None


def registerTreeFallHandler(handler, logger=None):
  global _hookedManagerClass
  global _originalOrderDestructibleDestroy

  if handler in _handlers:
    return True

  if _originalOrderDestructibleDestroy is None:
    try:
      import AreaDestructibles
      managerClass = AreaDestructibles.DestructiblesManager
      original = managerClass.orderDestructibleDestroy
    except Exception as error:
      _log(logger, 'tree fall hook registration failed: ' + str(error))
      return False

    def hookedOrderDestructibleDestroy(self, chunkID, dmgType, destrData, isNeedAnimation, *args, **kwargs):
      result = original(self, chunkID, dmgType, destrData, isNeedAnimation, *args, **kwargs)
      try:
        _notifyTreeFall(chunkID, dmgType, destrData, 'event', logger)
      except Exception as error:
        _log(logger, 'tree fall hook notification failed: ' + str(error))
      return result

    managerClass.orderDestructibleDestroy = hookedOrderDestructibleDestroy
    _hookedManagerClass = managerClass
    _originalOrderDestructibleDestroy = original
    _log(logger, 'tree fall hook installed')

  _handlers.append(handler)
  _log(logger, 'tree fall handler registered: handlers=' + str(len(_handlers)))
  return True


def unregisterTreeFallHandler(handler, logger=None):
  global _hookedManagerClass
  global _originalOrderDestructibleDestroy

  while handler in _handlers:
    _handlers.remove(handler)

  if _handlers:
    _log(logger, 'tree fall handler unregistered: handlers=' + str(len(_handlers)))
    return

  if _hookedManagerClass is not None and _originalOrderDestructibleDestroy is not None:
    try:
      _hookedManagerClass.orderDestructibleDestroy = _originalOrderDestructibleDestroy
      _log(logger, 'tree fall hook removed')
    except Exception as error:
      _log(logger, 'tree fall hook removal failed: ' + str(error))

  _hookedManagerClass = None
  _originalOrderDestructibleDestroy = None


def decodeFallenTreeData(fallData, logger=None):
  try:
    import DestructiblesCache
    return DestructiblesCache.decodeFallenTree(fallData)
  except Exception as error:
    _log(logger, 'failed to decode fallen tree data ' + str(fallData) + ': ' + str(error))
    return None


def currentDestructiblesManager(logger=None):
  try:
    import AreaDestructibles
    return AreaDestructibles.g_destructiblesManager
  except Exception as error:
    _log(logger, 'failed to access destructibles manager: ' + str(error))
    return None


def currentDestructiblesSpaceID(logger=None):
  manager = currentDestructiblesManager(logger)
  if manager is None:
    return None
  try:
    return manager.getSpaceID()
  except Exception as error:
    _log(logger, 'failed to read destructibles space id: ' + str(error))
    return None


def isBushDestructible(spaceID, chunkID, destrIndex, logger=None):
  if spaceID is None:
    return False
  try:
    import BigWorld
    checker = getattr(BigWorld, 'wg_checkDestructibleIsBush', getattr(BigWorld, 'checkDestructibleIsBush', None))
    if checker is None or not callable(checker):
      return False
    return bool(checker(spaceID, chunkID, destrIndex))
  except Exception as error:
    _log(
      logger,
      'failed to check tree/bush state: chunkID=' + str(chunkID) +
      ' destrIndex=' + str(destrIndex) + ' error=' + str(error)
    )
    return False


def _notifyTreeFall(chunkID, dmgType, destrData, source, logger):
  try:
    import DestructiblesCache
  except Exception as error:
    _log(logger, 'failed to load DestructiblesCache for tree fall event: ' + str(error))
    return

  if dmgType != DestructiblesCache.DESTR_TYPE_TREE:
    return

  decoded = decodeFallenTreeData(destrData, logger)
  if decoded is None:
    return

  destrIndex, fallYaw, fallPitchConstr, fallSpeed = decoded
  for handler in list(_handlers):
    try:
      handler(chunkID, destrIndex, fallYaw, fallPitchConstr, fallSpeed, source)
    except Exception as error:
      _log(
        logger,
        'tree fall handler failed: chunkID=' + str(chunkID) +
        ' destrIndex=' + str(destrIndex) + ' error=' + str(error)
      )


def _log(logger, message):
  if logger is not None:
    try:
      logger(message)
    except Exception:
      pass
