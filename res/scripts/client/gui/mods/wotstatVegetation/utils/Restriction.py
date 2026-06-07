
import BigWorld
import BattleReplay
from Singleton import Singleton
from Event import SafeEvent
from PlayerEvents import g_playerEvents
from constants import ARENA_GUI_TYPE

ALLOWED_ARENA_GUI_TYPES = (
  ARENA_GUI_TYPE.TRAINING,
  ARENA_GUI_TYPE.MAPS_TRAINING,
)

class Restriction(Singleton):

  @staticmethod
  def instance():
    return Restriction()

  def _singleton_init(self):
    self.onRestrictionChange = SafeEvent()
    self._allowed = True

    g_playerEvents.onAccountBecomePlayer += self._onAccountBecomePlayer
    g_playerEvents.onAvatarBecomePlayer += self._onAvatarBecomePlayer

  def isAllowed(self):
    return self._allowed

  def dispose(self):
    g_playerEvents.onAccountBecomePlayer -= self._onAccountBecomePlayer
    g_playerEvents.onAvatarBecomePlayer -= self._onAvatarBecomePlayer

  def _setAllowed(self, value):
    if self._allowed != value:
      self._allowed = value
      self.onRestrictionChange(self._allowed)

  def _onAccountBecomePlayer(self):
    self._setAllowed(True)

  def _onAvatarBecomePlayer(self):
    if BattleReplay.isPlaying():
      self._setAllowed(True)
      return

    player = BigWorld.player()
    if player is not None and hasattr(player, 'arenaGuiType'):
      self._setAllowed(player.arenaGuiType in ALLOWED_ARENA_GUI_TYPES)
    else:
      self._setAllowed(False)

def allowed():
  return Restriction.instance().isAllowed()