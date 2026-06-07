import BigWorld
import ArenaType


SERVER_VISIBILITY_MASK = 0x000fffff
ALL_VISIBILITY_MASK = 0xffffffff


def currentVisibilityMask():
  return int(ArenaType.getVisibilityMask(int(BigWorld.player().arenaTypeID))) & SERVER_VISIBILITY_MASK


def filterVegetationByVisibility(vegetation, activeMask):
  activeMask = int(activeMask) & ALL_VISIBILITY_MASK
  return [
    entry for entry in vegetation
    if int(entry['visibilityMask']) & activeMask
  ]
