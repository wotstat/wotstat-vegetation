#!/usr/bin/env python3
import os
import sys
import types


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MOD_SCRIPTS = os.path.join(ROOT, 'mod', 'res', 'scripts', 'client', 'gui', 'mods')
sys.path.insert(0, MOD_SCRIPTS)


class FakePlayer(object):

  def __init__(self):
    self.models = []
    self.adds = 0
    self.removes = 0
    self.arena = types.SimpleNamespace(
      arenaType=types.SimpleNamespace(geometryName='01_karelia')
    )

  def addModel(self, model):
    self.adds += 1
    self.models.append(model)

  def delModel(self, model):
    self.removes += 1
    if model in self.models:
      self.models.remove(model)


class FakeVector3(object):

  def __init__(self, x=0.0, y=0.0, z=0.0):
    self.x = x
    self.y = y
    self.z = z

  def distSqrTo(self, other):
    return (
      (self.x - other.x) ** 2 +
      (self.y - other.y) ** 2 +
      (self.z - other.z) ** 2
    )


class FakeMatrix(object):

  def __init__(self):
    self.values = [[0.0] * 4 for _ in range(4)]

  def setElement(self, x, y, value):
    self.values[x][y] = value


class FakeCallbackDelayer(object):

  def __init__(self):
    pass

  def delayCallback(self, *_args, **_kwargs):
    pass

  def stopCallback(self, *_args, **_kwargs):
    pass


class FakePanel(object):

  def addCheckboxLine(self, *_args, **_kwargs):
    pass


def installStubs(player):
  bigworld = types.ModuleType('BigWorld')
  bigworld.player = lambda: player
  bigworld.camera = lambda: types.SimpleNamespace(position=FakeVector3())
  sys.modules['BigWorld'] = bigworld

  mathModule = types.ModuleType('Math')
  mathModule.Vector3 = FakeVector3
  mathModule.Matrix = FakeMatrix
  sys.modules['Math'] = mathModule

  resmgr = types.ModuleType('ResMgr')
  resmgr.isFile = lambda _path: False
  sys.modules['ResMgr'] = resmgr

  adisp = types.ModuleType('adisp')
  adisp.adisp_process = lambda fn: fn
  sys.modules['adisp'] = adisp

  sharedUtils = types.ModuleType('shared_utils')
  sharedUtils.awaitNextFrame = lambda: None
  sys.modules['shared_utils'] = sharedUtils

  helpers = types.ModuleType('helpers')
  helpers.isPlayerAvatar = lambda: True
  helpers.getPreferencesFilePath = lambda: '/tmp'
  sys.modules['helpers'] = helpers

  callbackModule = types.ModuleType('helpers.CallbackDelayer')
  callbackModule.CallbackDelayer = FakeCallbackDelayer
  sys.modules['helpers.CallbackDelayer'] = callbackModule

  gui = types.ModuleType('gui')
  debugUtils = types.ModuleType('gui.debugUtils')
  debugUtils.ui = types.SimpleNamespace(createPanel=lambda _name: FakePanel())
  debugUtils.gizmos = types.SimpleNamespace(createMarker=lambda *_args, **_kwargs: None)
  debugUtils.drawer = types.SimpleNamespace(createLine=lambda *_args, **_kwargs: None)
  sys.modules['gui'] = gui
  sys.modules['gui.debugUtils'] = debugUtils


def drain(result):
  if result is None:
    return
  for _item in result:
    pass


def check(condition, message):
  if not condition:
    raise AssertionError(message)


def main():
  player = FakePlayer()
  installStubs(player)

  from wotstatVegetation.WotstatVegetation import WotstatVegetation  # noqa: E402

  app = WotstatVegetation()
  app.colliders = ['model-a', 'model-b']
  app.collidersArena = '01_karelia'
  app.showColliders = True

  drain(app.displayColliders())
  drain(app.displayColliders())
  check(player.adds == 2, 'repeated display must not duplicate addModel calls')
  check(len(player.models) == 2, 'models visible after display')

  app.showColliders = False
  drain(app.hideColliders())
  drain(app.hideColliders())
  check(player.removes == 2, 'repeated hide must not duplicate delModel calls')
  check(len(player.models) == 0, 'models removed after hide')
  check(app.colliders == [], 'collider references cleared on disable')
  check(app.collidersArena == '', 'collider arena cleared on disable')

  print('smoke_runtime_spawner: ok')


if __name__ == '__main__':
  main()
