SERVER_VISIBILITY_MASK = 0x000fffff
ALL_VISIBILITY_MASK = 0xffffffff


def _log(logger, message):
  if logger is not None:
    logger(message)


def _toUInt32(value):
  try:
    return int(value) & ALL_VISIBILITY_MASK
  except Exception:
    return None


def getCurrentBattleMode(logger=None):
  context = {
    'player': None,
    'spaceID': None,
    'arenaTypeID': None,
    'arenaBonusType': None,
    'arenaGuiType': None,
    'geometryName': None,
    'gameplayID': None,
    'gameplayName': None
  }

  try:
    import BigWorld
    player = BigWorld.player()
  except Exception as error:
    _log(logger, 'failed to read current player for visibility mask: ' + str(error))
    return context

  context['player'] = player
  if player is None:
    _log(logger, 'current player unavailable for visibility mask')
    return context

  context['spaceID'] = getattr(player, 'spaceID', None)
  context['arenaTypeID'] = getattr(player, 'arenaTypeID', None)
  context['arenaBonusType'] = getattr(player, 'arenaBonusType', None)
  context['arenaGuiType'] = getattr(player, 'arenaGuiType', None)

  arena = getattr(player, 'arena', None)
  arenaType = getattr(arena, 'arenaType', None)
  if arenaType is not None:
    context['geometryName'] = getattr(arenaType, 'geometryName', None)
    context['gameplayName'] = getattr(arenaType, 'gameplayName', None)
    if context['arenaTypeID'] is None:
      context['arenaTypeID'] = getattr(arenaType, 'id', None)
    context['gameplayID'] = getattr(arenaType, 'gameplayID', None)

  if context['gameplayID'] is None and context['arenaTypeID'] is not None:
    try:
      context['gameplayID'] = int(context['arenaTypeID']) >> 16
    except Exception:
      pass

  if context['gameplayName'] is None and context['gameplayID'] is not None:
    try:
      import ArenaType
      context['gameplayName'] = ArenaType.getGameplayName(context['gameplayID'])
    except Exception as error:
      _log(logger, 'failed to resolve gameplay name for visibility mask: ' + str(error))

  return context


def getCurrentActiveVegetationVisibilityMask(logger=None):
  context = getCurrentBattleMode(logger)
  return getActiveVegetationVisibilityMaskForContext(context, logger)


def getActiveVegetationVisibilityMaskForContext(context, logger=None):
  arenaMask = _arenaTypeVisibilityMask(context.get('arenaTypeID'), logger)
  engineMask = _engineSpaceVisibilityMask(context.get('player'), context.get('spaceID'), logger)

  if arenaMask is not None:
    if engineMask is not None and engineMask != arenaMask:
      _log(
        logger,
        'visibility mask mismatch: arenaType=0x%08x engine=0x%08x using arenaType' %
        (arenaMask, engineMask)
      )
    return arenaMask

  if engineMask is not None:
    _log(logger, 'using engine space visibility mask fallback: 0x%08x' % engineMask)
    return engineMask

  _log(logger, 'active vegetation visibility mask unavailable, falling back to all bits')
  return ALL_VISIBILITY_MASK


def buildCurrentVisibilityContext(logger=None):
  context = getCurrentBattleMode(logger)
  context['activeMask'] = getActiveVegetationVisibilityMaskForContext(context, logger)
  return context


def isInstanceVisibleForMask(instanceMask, activeMask):
  mask = _toUInt32(instanceMask)
  if mask is None:
    return True

  active = _toUInt32(activeMask)
  if active is None:
    active = ALL_VISIBILITY_MASK

  return bool(mask & active)


def filterVegetationByVisibility(vegetation, activeMask):
  visible = []
  stats = {
    'before': len(vegetation),
    'after': 0,
    'skipped': 0,
    'missingMask': 0,
    'invalidMask': 0
  }

  for entry in vegetation:
    if 'visibilityMask' not in entry:
      stats['missingMask'] += 1
      visible.append(entry)
      continue

    mask = _toUInt32(entry.get('visibilityMask'))
    if mask is None:
      stats['invalidMask'] += 1
      visible.append(entry)
      continue

    if isInstanceVisibleForMask(mask, activeMask):
      visible.append(entry)
    else:
      stats['skipped'] += 1

  stats['after'] = len(visible)
  return visible, stats


def _arenaTypeVisibilityMask(arenaTypeID, logger=None):
  if arenaTypeID is None:
    _log(logger, 'arenaTypeID unavailable for visibility mask')
    return None

  try:
    import ArenaType
    mask = _toUInt32(ArenaType.getVisibilityMask(int(arenaTypeID)))
  except Exception as error:
    _log(logger, 'failed to resolve ArenaType visibility mask: ' + str(error))
    return None

  if mask is None:
    _log(logger, 'ArenaType visibility mask is invalid: ' + str(mask))
    return None

  return mask & SERVER_VISIBILITY_MASK


def _engineSpaceVisibilityMask(player, spaceID, logger=None):
  if spaceID is None and player is not None:
    spaceID = getattr(player, 'spaceID', None)
  if spaceID is None:
    return None

  try:
    import BigWorld
    getter = getattr(BigWorld, 'wg_getSpaceItemsVisibilityMask', getattr(BigWorld, 'getSpaceItemsVisibilityMask', None))
    if getter is None or not callable(getter):
      return None
    rawMask = _toUInt32(getter(spaceID))
  except Exception as error:
    _log(logger, 'failed to read engine space visibility mask: ' + str(error))
    return None

  if rawMask is None:
    return None

  serverMask = rawMask & SERVER_VISIBILITY_MASK
  _log(
    logger,
    'engine space visibility mask: raw=0x%08x server=0x%08x' %
    (rawMask, serverMask)
  )
  if serverMask == 0:
    return None
  return serverMask
