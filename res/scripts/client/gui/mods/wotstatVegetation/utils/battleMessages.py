from gui.Scaleform.genConsts.BATTLE_MESSAGES_CONSTS import BATTLE_MESSAGES_CONSTS
from gui.Scaleform.genConsts.BATTLE_VIEW_ALIASES import BATTLE_VIEW_ALIASES
from gui.Scaleform.framework import WindowLayer
from gui.shared.personality import ServicesLocator
from gui.Scaleform.daapi.view.battle.shared.messages.fading_messages import _COLOR_TO_METHOD

def showPlayerMessage(message, color=BATTLE_MESSAGES_CONSTS.COLOR_YELLOW):
  # type: (BATTLE_MESSAGES_CONSTS, str) -> None
  _showMessage(BATTLE_VIEW_ALIASES.PLAYER_MESSAGES, color, message)

def showVehicleMessage(message, color=BATTLE_MESSAGES_CONSTS.COLOR_YELLOW):
  # type: (BATTLE_MESSAGES_CONSTS, str) -> None
  _showMessage(BATTLE_VIEW_ALIASES.VEHICLE_MESSAGES, color, message)


def _showMessage(viewName, color, message):
  view = _getView(viewName)
  if not view: return

  fnName = _COLOR_TO_METHOD.get(color)
  fn = getattr(view, fnName, None)
  if not fn: return
  fn('key', message)


def _getView(name):
  # type: (str) -> object
  app = ServicesLocator.appLoader.getDefBattleApp()
  if not app: return

  battlePage = app.containerManager.getContainer(WindowLayer.VIEW).getView()
  if not battlePage: return

  return battlePage.components.get(name, None)