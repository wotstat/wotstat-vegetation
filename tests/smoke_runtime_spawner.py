#!/usr/bin/env python3
import os
import math
import sys
import types


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MOD_SCRIPTS = os.path.join(ROOT, 'mod', 'res', 'scripts', 'client', 'gui', 'mods')
sys.path.insert(0, MOD_SCRIPTS)


if not hasattr(types, 'SimpleNamespace'):

  class SimpleNamespace(object):

    def __init__(self, **kwargs):
      self.__dict__.update(kwargs)

  types.SimpleNamespace = SimpleNamespace


class FakePlayer(object):

  def __init__(self):
    self.models = []
    self.adds = 0
    self.removes = 0
    self.spaceID = 9
    self.arenaTypeID = 1
    self.arenaBonusType = 0
    self.arenaGuiType = 0
    self.arena = types.SimpleNamespace(
      arenaType=types.SimpleNamespace(
        id=1,
        geometryName='01_karelia',
        gameplayID=0,
        gameplayName='ctf'
      )
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


class FakeEvent(object):

  def __init__(self):
    self.handlers = []

  def __iadd__(self, handler):
    self.handlers.append(handler)
    return self

  def __isub__(self, handler):
    while handler in self.handlers:
      self.handlers.remove(handler)
    return self

  def fire(self):
    for handler in list(self.handlers):
      handler()


def installStubs(player):
  bigworld = types.ModuleType('BigWorld')
  bigworld.player = lambda: player
  bigworld.camera = lambda: types.SimpleNamespace(position=FakeVector3())
  bigworld.Model = FakeModel
  bigworld.Servo = FakeServo
  bigworld.wg_getSpaceItemsVisibilityMask = lambda _spaceID: 1
  sys.modules['BigWorld'] = bigworld

  arenaType = types.ModuleType('ArenaType')
  arenaType.getVisibilityMask = lambda _arenaTypeID: 1
  arenaType.getGameplayName = lambda _gameplayID: 'ctf'
  sys.modules['ArenaType'] = arenaType

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

  playerEvents = types.ModuleType('PlayerEvents')
  playerEvents.g_playerEvents = types.SimpleNamespace(
    onAvatarBecomeNonPlayer=FakeEvent()
  )
  sys.modules['PlayerEvents'] = playerEvents

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

  def densityMetadataFor(self, asset):
    if 'Red' in asset or 'Grass' in asset:
      density = 0.0
      affects = False
      reason = 'test_red'
    else:
      density = 0.5
      affects = True
      reason = 'test_green'
    return {
      'camouflageDensity': density,
      'camouflageAffects': affects,
      'camouflageReason': reason
    }


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


class FakeFallingParams(object):

  def __init__(self, values):
    self.values = values

  def get(self, row, col):
    return self.values.get((row, col), 0.0)


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
  from wotstatVegetation.visibility_mask import (  # noqa: E402
    buildCurrentVisibilityContext,
    filterVegetationByVisibility,
    isInstanceVisibleForMask
  )

  context = buildCurrentVisibilityContext()
  check(context['activeMask'] == 1, 'active visibility mask from ArenaType')
  check(isInstanceVisibleForMask(1, context['activeMask']), 'matching visibility mask visible')
  check(not isInstanceVisibleForMask(2, context['activeMask']), 'non-matching visibility mask hidden')
  visible, stats = filterVegetationByVisibility([
    {'visibilityMask': 1},
    {'visibilityMask': 2}
  ], context['activeMask'])
  check(len(visible) == 1 and stats['skipped'] == 1, 'visibility filter skips hidden instances')

  app = WotstatVegetation()
  check(app.avatarLeaveHookRegistered, 'avatar leave hook registered')
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
  app.dispose()
  check(not app.avatarLeaveHookRegistered, 'avatar leave hook unregistered on dispose')

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
    'visibilityMask': 1,
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
  app.onlyCamouflable = True
  app.vegetationData = [
    {
      'asset': 'vegetation/Green.srt',
      'chunkID': 110,
      'destrIndex': 1,
      'matrix': identityMatrixRows(10.0, 0.0, 20.0)
    },
    {
      'asset': 'vegetation/Red.srt',
      'chunkID': 111,
      'destrIndex': 2,
      'matrix': identityMatrixRows(15.0, 0.0, 25.0)
    }
  ]
  app.loadColliders()
  check(len(app.colliders) == 1, 'only camuflagable skips red colliders')
  check((110, 1) in app.treeColliderByID, 'green tree remains indexed')
  check((111, 2) not in app.treeColliderByID, 'red tree skipped from tree index')

  app = WotstatVegetation()
  app.getColliderCache = lambda: FakeColliderCache()
  app.vegetationDataArena = '01_karelia'
  app.vegetationData = [
    {
      'asset': 'vegetation/Pine.srt',
      'chunkID': 200,
      'destrIndex': 8,
      'visibilityMask': 1,
      'matrix': identityMatrixRows(15.0, 0.0, 25.0)
    },
    {
      'asset': 'vegetation/Hidden.srt',
      'chunkID': 201,
      'destrIndex': 9,
      'visibilityMask': 2,
      'matrix': identityMatrixRows(20.0, 0.0, 30.0)
    }
  ]
  app.updateVisibilityFilter('01_karelia')
  app.loadColliders()
  check(len(app.colliders) == 1, 'hidden visibility mask not spawned')
  check((201, 9) not in app.treeColliderByID, 'hidden tree id not indexed')

  areaModule = types.ModuleType('AreaDestructibles')
  areaModule.g_destructiblesManager = FakeDestructiblesManager({
    200: FakeDestructiblesController([(8, math.pi / 2.0, math.pi / 2.0, 0.0)])
  })
  sys.modules['AreaDestructibles'] = areaModule
  cacheModule = types.ModuleType('DestructiblesCache')
  cacheModule.decodeFallenTree = lambda data: data
  cacheModule.DESTR_TYPE_TREE = 0
  sys.modules['DestructiblesCache'] = cacheModule
  bigworld = sys.modules['BigWorld']
  bigworld.wg_getFallingParams = lambda _spaceID, _chunkID, _destrIndex: FakeFallingParams({
    (0, 0): 100.0,
    (0, 1): 5.0,
    (0, 3): 0.25,
    (1, 0): 3.0,
    (1, 1): 0.2
  })
  bigworld.wg_solveDestructibleFallPitch = lambda _weight, _angStiffness, minPitch, _approxPitch: minPitch

  app.syncFallenTreeStates()
  check(app.colliderInstances[0]['fallen'], 'already fallen tree synced to fallen orientation')
  check(len(app.colliders[0].motors) == 1, 'sync replaces transform motor')
  finalRows = app.colliderInstances[0]['currentMatrixRows']
  check(abs(finalRows[1][0] - math.sin(math.pi / 2.0 - 0.2)) < 0.0001, 'sync uses solved final pitch')
  check(abs(finalRows[3][1] + 0.25 * math.sin(math.pi / 2.0 - 0.2)) < 0.0001, 'sync applies bury depth')
  check(app.onTreeFall(201, 9, 0.0, math.pi / 2.0, 0.0, 'hidden') is False, 'hidden tree fall does not create collider')

  app.onShowColliders(True)
  app.collidersVisible = True
  player.adds = 0
  player.removes = 0
  drain(app.onOnlyCamouflable(True))
  check(app.onlyCamouflable, 'only camuflagable flag enabled')
  check(player.removes == 1, 'toggle refresh removes old visible colliders')
  check(len(app.colliders) == 1, 'toggle refresh keeps filtered collider list')

  app = WotstatVegetation()
  app.colliders = ['engine-owned-model']
  app.colliderInstances = [{'model': 'engine-owned-model'}]
  app.collidersArena = '01_karelia'
  app.collidersVisible = True
  app.collidersProcessing = True
  app.showColliders = True
  app.showPositions = True
  app.vegetationDataArena = '01_karelia'
  app.vegetationData = [{
    'asset': 'vegetation/Pine.srt',
    'visibilityMask': 1,
    'matrix': identityMatrixRows()
  }]
  app.visibleVegetationData = list(app.vegetationData)
  app.treeColliderByID = {(1, 2): [{'model': 'engine-owned-model'}]}
  app.treeColliderStates = {(1, 2): ('fall',)}
  player.removes = 0
  sys.modules['PlayerEvents'].g_playerEvents.onAvatarBecomeNonPlayer.fire()
  check(player.removes == 0, 'avatar leave reset must not delModel engine-cleaned colliders')
  check(app.colliders == [], 'avatar leave clears collider references')
  check(app.colliderInstances == [], 'avatar leave clears collider instances')
  check(app.collidersArena == '', 'avatar leave clears collider arena')
  check(app.vegetationData == [], 'avatar leave clears map data')
  check(app.visibleVegetationData == [], 'avatar leave clears filtered map data')
  check(app.vegetationDataArena == '', 'avatar leave clears map arena')
  check(app.treeColliderByID == {}, 'avatar leave clears tree index')
  check(app.treeColliderStates == {}, 'avatar leave clears tree states')
  check(not app.showColliders, 'avatar leave clears show colliders flag')
  check(not app.showPositions, 'avatar leave clears show positions flag')
  check(not app.collidersProcessing, 'avatar leave clears processing flag')

  print('smoke_runtime_spawner: ok')


if __name__ == '__main__':
  main()
