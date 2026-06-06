#!/usr/bin/env python3
import os
import math
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


class FakeServo(object):

  def __init__(self, matrix):
    self.matrix = matrix


class FakeModel(object):

  def __init__(self, path):
    self.path = path
    self.castsShadow = True
    self.motors = []
    self.matrix = None

  def addMotor(self, motor):
    self.motors.append(motor)

  def delMotor(self, motor):
    if motor in self.motors:
      self.motors.remove(motor)


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
  bigworld.Model = FakeModel
  bigworld.Servo = FakeServo
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


class FakeColliderCache(object):

  def ensureColliderModel(self, asset):
    return asset.replace('.srt', '.model')


class FakeDestructiblesManager(object):

  def __init__(self, controllers):
    self.controllers = controllers

  def getController(self, chunkID):
    return self.controllers.get(chunkID)

  def getSpaceID(self):
    return 1


class FakeDestructiblesController(object):

  def __init__(self, fallenTrees):
    self.fallenTrees = fallenTrees


def identityMatrixRows(x=0.0, y=0.0, z=0.0):
  return [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [x, y, z, 1.0]
  ]


def main():
  player = FakePlayer()
  installStubs(player)

  from wotstatVegetation.WotstatVegetation import WotstatVegetation  # noqa: E402
  from wotstatVegetation.treeFallTransform import fallenTreeMatrixRows  # noqa: E402

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

  transform = fallenTreeMatrixRows(identityMatrixRows(), math.pi / 2.0, math.pi / 2.0)
  check(abs(transform[1][0] - 1.0) < 0.0001, 'fallen yaw points local tree height along +x')
  check(abs(transform[1][1]) < 0.0001, 'fallen tree no longer points up')

  app = WotstatVegetation()
  app.getColliderCache = lambda: FakeColliderCache()
  app.vegetationDataArena = '01_karelia'
  app.vegetationData = [{
    'asset': 'vegetation/Oak.srt',
    'chunkID': 100,
    'destrIndex': 7,
    'matrix': identityMatrixRows(10.0, 0.0, 20.0)
  }]

  app.loadColliders()
  app.loadColliders()
  check(len(app.colliders) == 1, 'repeated loadColliders must not duplicate models')
  check((100, 7) in app.treeColliderByID, 'tree id indexed')
  model = app.colliders[0]
  check(len(model.motors) == 1, 'standing collider has one transform motor')

  check(app.onTreeFall(100, 999, 0.0, math.pi / 2.0, 0.0, 'test') is False, 'unknown tree id ignored')
  check(app.onTreeFall(100, 7, 0.0, math.pi / 2.0, 0.0, 'test') is True, 'known tree fall handled')
  check(len(model.motors) == 1, 'fallen transform replaces motor instead of adding one')
  check(app.colliderInstances[0]['fallen'], 'collider marked fallen')
  check(abs(app.colliderInstances[0]['currentMatrixRows'][1][2] - 1.0) < 0.0001, 'fall yaw 0 points along +z')
  check(app.onTreeFall(100, 7, 0.0, math.pi / 2.0, 0.0, 'repeat') is False, 'repeated same fall state ignored')
  check(len(model.motors) == 1, 'repeated fall state keeps one motor')

  app.clearColliderInstances()
  check(app.treeColliderByID == {}, 'tree collider index cleared')
  check(app.treeColliderStates == {}, 'tree collider states cleared')

  app = WotstatVegetation()
  app.getColliderCache = lambda: FakeColliderCache()
  app.vegetationDataArena = '01_karelia'
  app.vegetationData = [{
    'asset': 'vegetation/Pine.srt',
    'chunkID': 200,
    'destrIndex': 8,
    'matrix': identityMatrixRows(15.0, 0.0, 25.0)
  }]
  app.loadColliders()

  areaModule = types.ModuleType('AreaDestructibles')
  areaModule.g_destructiblesManager = FakeDestructiblesManager({
    200: FakeDestructiblesController([(8, math.pi / 2.0, math.pi / 2.0, 0.0)])
  })
  sys.modules['AreaDestructibles'] = areaModule
  cacheModule = types.ModuleType('DestructiblesCache')
  cacheModule.decodeFallenTree = lambda data: data
  cacheModule.DESTR_TYPE_TREE = 0
  sys.modules['DestructiblesCache'] = cacheModule

  app.syncFallenTreeStates()
  check(app.colliderInstances[0]['fallen'], 'already fallen tree synced to fallen orientation')
  check(len(app.colliders[0].motors) == 1, 'sync replaces transform motor')

  print('smoke_runtime_spawner: ok')


if __name__ == '__main__':
  main()
