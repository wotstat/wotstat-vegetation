import BigWorld
import Math

from .colliderCache import VegetationColliderCache
from .logger import log
from .mapCache import loadMapVegetation
from .runtimeCache import normalizeResourcePathForKey
from .treeFallRuntime import (
  currentDestructiblesManager,
  currentDestructiblesSpaceID,
  decodeFallenTreeData,
  isBushDestructible,
  registerTreeFallHandler,
  unregisterTreeFallHandler
)
from .treeFallTransform import fallenTreeMatrixRows
from adisp import adisp_process
from shared_utils import awaitNextFrame
from helpers.CallbackDelayer import CallbackDelayer
from helpers import isPlayerAvatar
try:
  from helpers import getPreferencesFilePath as helpersGetPreferencesFilePath
except ImportError:
  helpersGetPreferencesFilePath = None

from gui.debugUtils import ui, gizmos, drawer


DEBUG_MODE = '{{DEBUG_MODE}}'
VERSION = '{{VERSION}}'


def toMatrix(dm):
  m = Math.Matrix() # type: Math.Matrix
  for x in range(4):
    for y in range(4):
      m.setElement(x, y, dm[x][y])
          
  return m

def add(a, b):
    return Math.Vector3(a.x + b.x, a.y + b.y, a.z + b.z)

def mul(a, s):
    return Math.Vector3(a.x * s, a.y * s, a.z * s)

def drawBasis(matrix, scale=3.0):
    origin = Math.Vector3(matrix[3][0], matrix[3][1], matrix[3][2])

    x_axis = Math.Vector3(matrix[0][0], matrix[0][1], matrix[0][2])
    y_axis = Math.Vector3(matrix[1][0], matrix[1][1], matrix[1][2])
    z_axis = Math.Vector3(matrix[2][0], matrix[2][1], matrix[2][2])

    x_end = add(origin, mul(x_axis, scale))
    y_end = add(origin, mul(y_axis, scale))
    z_end = add(origin, mul(z_axis, scale))

    return (
      drawer.createLine(points=[origin, x_end], color=0xff0000, backColor=0xff0000),
      drawer.createLine(points=[origin, y_end], color=0x00ff00, backColor=0x00ff00),
      drawer.createLine(points=[origin, z_end], color=0x0000ff, backColor=0x0000ff)
    )

class WotstatVegetation(CallbackDelayer):

  def __init__(self):
    
    CallbackDelayer.__init__(self)

    self.vegetationData = []
    self.vegetationDataArena = ''

    self.showPositions = False
    self.showColliders = False

    self.colliders = []
    self.colliderInstances = []
    self.collidersArena = ''
    self.collidersProcessing = False
    self.collidersVisible = False
    self.colliderCache = None
    self.treeColliderByID = {}
    self.treeColliderStates = {}
    self.treeFallHookRegistered = False

    self.lastPosition = Math.Vector3(0, 0, 0)
    self.markers = []

    self.panel = ui.createPanel('Vegetation')
    self.panel.addCheckboxLine('Show positions (30m)', onToggleCallback=self.onShowPositions)
    self.panel.addCheckboxLine('Show colliders', onToggleCallback=self.onShowColliders)

  def dispose(self):
    self.showColliders = False
    self.stopCallback(self.update)
    self.clearMarkers()
    self.unregisterTreeFallHook()
    self.hideColliders()

  def preferencesPath(self):
    getters = (
      helpersGetPreferencesFilePath,
      getattr(BigWorld, 'wg_getPreferencesFilePath', None),
      getattr(BigWorld, 'getPreferencesFilePath', None)
    )
    for getter in getters:
      if getter is None or not callable(getter):
        continue
      try:
        path = getter()
      except Exception as error:
        log('failed to resolve preferences path: ' + str(error))
        continue
      if path:
        return path
    log('preferences path unavailable, using relative cache root')
    return ''

  def getColliderCache(self):
    preferencesPath = self.preferencesPath()
    if self.colliderCache is None or self.colliderCache.preferencesPath != preferencesPath:
      self.colliderCache = VegetationColliderCache(preferencesPath, VERSION, log)
    return self.colliderCache

  def loadMapFromSpaceBin(self, mapName):
    if self.vegetationDataArena == mapName: return

    vegetation = loadMapVegetation(mapName, self.preferencesPath(), VERSION, log)
    if vegetation is None:
      self.vegetationData = []
      self.vegetationDataArena = ''
      return

    self.vegetationData = vegetation
    self.vegetationDataArena = mapName

  def loadColliders(self):
    if self.collidersArena == self.vegetationDataArena and self.colliders:
      log('collider instances already prepared for arena: ' + self.collidersArena)
      return

    self.clearColliderInstances()
    self.collidersArena = self.vegetationDataArena
    colliderCache = self.getColliderCache()
    modelPathByAsset = {}
    failedAssets = {}

    for v in self.vegetationData:
      asset = v.get('asset')
      if not asset:
        continue
      assetKey = normalizeResourcePathForKey(asset)

      if assetKey in failedAssets:
        continue

      if assetKey not in modelPathByAsset:
        modelPath = colliderCache.ensureColliderModel(asset)
        if not modelPath:
          failedAssets[assetKey] = True
          continue
        modelPathByAsset[assetKey] = modelPath
      else:
        modelPath = modelPathByAsset[assetKey]
      
      try:
        model = BigWorld.Model(modelPath)
        model.castsShadow = False
      except Exception as error:
        log('failed to create BigWorld.Model for ' + modelPath + ': ' + str(error))
        failedAssets[assetKey] = True
        continue
      
      matrixRows = self.copyMatrixRows(v['matrix'])
      matrix = toMatrix(matrixRows)
      servo = BigWorld.Servo(matrix)
      model.addMotor(servo)
      self.colliders.append(model)
      instance = {
        'model': model,
        'servo': servo,
        'asset': asset,
        'standingMatrixRows': matrixRows,
        'currentMatrixRows': matrixRows,
        'chunkID': v.get('chunkID'),
        'destrIndex': v.get('destrIndex'),
        'fallen': False
      }
      self.colliderInstances.append(instance)
      self.addTreeColliderIndex(instance)

    log(
      'prepared collider instances: instances=' + str(len(self.colliders)) +
      ' unique_models=' + str(len(modelPathByAsset)) +
      ' failed_assets=' + str(len(failedAssets)) +
      ' tree_ids=' + str(len(self.treeColliderByID))
    )

  def clearColliderInstances(self):
    self.colliders = []
    self.colliderInstances = []
    self.collidersArena = ''
    self.collidersVisible = False
    self.treeColliderByID = {}
    self.treeColliderStates = {}

  def copyMatrixRows(self, matrixRows):
    return [list(row) for row in matrixRows]

  def treeKey(self, chunkID, destrIndex):
    if chunkID is None or destrIndex is None:
      return None
    try:
      return (int(chunkID), int(destrIndex))
    except Exception as error:
      log(
        'invalid tree id: chunkID=' + str(chunkID) +
        ' destrIndex=' + str(destrIndex) + ' error=' + str(error)
      )
      return None

  def treeIDText(self, key):
    if key is None:
      return 'chunkID=None destrIndex=None'
    return 'chunkID=' + str(key[0]) + ' destrIndex=' + str(key[1])

  def addTreeColliderIndex(self, instance):
    key = self.treeKey(instance.get('chunkID'), instance.get('destrIndex'))
    if key is None:
      return
    entries = self.treeColliderByID.setdefault(key, [])
    entries.append(instance)
    if len(entries) > 1:
      log('duplicate tree collider id: ' + self.treeIDText(key) + ' count=' + str(len(entries)))

  def treeChunks(self):
    chunks = {}
    for chunkID, _destrIndex in self.treeColliderByID.keys():
      chunks[chunkID] = True
    return chunks.keys()

  def registerTreeFallHook(self):
    if self.treeFallHookRegistered:
      return
    if not self.treeColliderByID:
      log('tree fall hook skipped: no destructible tree ids in collider set')
      return
    self.treeFallHookRegistered = registerTreeFallHandler(self.onTreeFall, log)

  def unregisterTreeFallHook(self):
    if not self.treeFallHookRegistered:
      return
    unregisterTreeFallHandler(self.onTreeFall, log)
    self.treeFallHookRegistered = False

  def syncFallenTreeStates(self):
    if not self.treeColliderByID:
      return

    manager = currentDestructiblesManager(log)
    if manager is None:
      log('fallen tree state sync skipped: destructibles manager unavailable')
      return

    chunksChecked = 0
    fallenSeen = 0
    updated = 0
    for chunkID in self.treeChunks():
      try:
        controller = manager.getController(chunkID)
      except Exception as error:
        log('failed to read destructibles controller for chunkID=' + str(chunkID) + ': ' + str(error))
        continue
      if controller is None:
        continue
      chunksChecked += 1
      try:
        fallenTrees = getattr(controller, 'fallenTrees', ()) or ()
      except Exception as error:
        log('failed to read fallenTrees for chunkID=' + str(chunkID) + ': ' + str(error))
        continue
      for fallData in fallenTrees:
        decoded = decodeFallenTreeData(fallData, log)
        if decoded is None:
          continue
        fallenSeen += 1
        destrIndex, fallYaw, fallPitchConstr, fallSpeed = decoded
        if self.onTreeFall(chunkID, destrIndex, fallYaw, fallPitchConstr, fallSpeed, 'sync'):
          updated += 1

    log(
      'fallen tree state sync complete: chunks=' + str(chunksChecked) +
      ' fallen=' + str(fallenSeen) +
      ' updated=' + str(updated)
    )

  def onTreeFall(self, chunkID, destrIndex, fallYaw, fallPitchConstr, fallSpeed, source):
    key = self.treeKey(chunkID, destrIndex)
    if key is None:
      log(
        'tree fall event missing tree id: chunkID=' + str(chunkID) +
        ' destrIndex=' + str(destrIndex)
      )
      return False

    instances = self.treeColliderByID.get(key)
    if not instances:
      log(
        'tree fall event has no collider: ' + self.treeIDText(key) +
        ' source=' + str(source) +
        ' yaw=' + str(fallYaw)
      )
      return False

    state = (fallYaw, fallPitchConstr, fallSpeed)
    if self.treeColliderStates.get(key) == state:
      return False

    spaceID = currentDestructiblesSpaceID(log)
    if isBushDestructible(spaceID, key[0], key[1], log):
      self.treeColliderStates[key] = state
      log(
        'tree fall event is bush, collider unchanged: ' + self.treeIDText(key) +
        ' source=' + str(source)
      )
      return False

    log(
      'detected tree fall: ' + self.treeIDText(key) +
      ' source=' + str(source) +
      ' yaw=' + str(fallYaw) +
      ' pitchConstr=' + str(fallPitchConstr) +
      ' speed=' + str(fallSpeed)
    )

    updated = 0
    for instance in instances:
      try:
        matrixRows = fallenTreeMatrixRows(instance['standingMatrixRows'], fallYaw, fallPitchConstr)
      except Exception as error:
        log('failed to compute fallen tree collider transform: ' + self.treeIDText(key) + ' error=' + str(error))
        continue
      if self.setColliderTransform(instance, matrixRows, key):
        updated += 1

    if updated > 0:
      self.treeColliderStates[key] = state
      log(
        'updated fallen tree collider transform: ' + self.treeIDText(key) +
        ' models=' + str(updated) +
        ' yaw=' + str(fallYaw)
      )
      return True

    log('tree fall event did not update collider: ' + self.treeIDText(key))
    return False

  def setColliderTransform(self, instance, matrixRows, key):
    model = instance.get('model')
    if model is None:
      log('missing collider model for tree: ' + self.treeIDText(key))
      return False

    oldServo = instance.get('servo')
    if oldServo is not None and getattr(model, 'delMotor', None) is not None:
      try:
        motors = getattr(model, 'motors', None)
        if motors is None:
          model.delMotor(oldServo)
        else:
          try:
            hasOldServo = oldServo in motors
          except Exception:
            hasOldServo = True
          if hasOldServo:
            model.delMotor(oldServo)
      except Exception as error:
        log('failed to remove old collider transform motor: ' + self.treeIDText(key) + ' error=' + str(error))

    matrix = toMatrix(matrixRows)
    try:
      servo = BigWorld.Servo(matrix)
      model.addMotor(servo)
      instance['servo'] = servo
    except Exception as error:
      log('failed to replace collider transform motor: ' + self.treeIDText(key) + ' error=' + str(error))
      try:
        model.matrix = matrix
        instance['servo'] = None
      except Exception as matrixError:
        log('failed to assign collider matrix directly: ' + self.treeIDText(key) + ' error=' + str(matrixError))
        return False

    instance['currentMatrixRows'] = matrixRows
    instance['fallen'] = True
    return True

  @adisp_process
  def displayColliders(self):
    if self.collidersProcessing: return
    if self.collidersVisible:
      log('collider models already visible: ' + str(len(self.colliders)))
      return
    self.collidersProcessing = True

    player = BigWorld.player()

    i = 0
    for col in self.colliders:
      try:
        player.addModel(col)
      except Exception as error:
        log('failed to add collider model: ' + str(error))
      i += 1

      if i % 100 == 0: yield awaitNextFrame()

    self.collidersVisible = True
    log('spawned collider models: ' + str(i))
    self.collidersProcessing = False
    if not self.showColliders: self.hideColliders()

  @adisp_process
  def hideColliders(self):
    if self.collidersProcessing: return
    if not self.colliders and not self.collidersVisible:
      return
    
    player = BigWorld.player()
    if not player: 
      self.collidersVisible = False
      if not self.showColliders:
        self.clearColliderInstances()
        log('cleared collider model references without player')
      return

    self.collidersProcessing = True

    i = 0
    for col in self.colliders:
      try:
        player.delModel(col)
      except Exception as error:
        log('failed to remove collider model: ' + str(error))
      i += 1

      if i % 100 == 0: yield awaitNextFrame()

    self.collidersVisible = False
    log('removed collider models: ' + str(i))
    self.collidersProcessing = False
    if self.showColliders:
      self.displayColliders()
    else:
      self.clearColliderInstances()
      log('cleared collider model references')

  def clearMarkers(self):
    for marker in self.markers: marker.destroy()
    self.markers = []

  def update(self):
    pos = BigWorld.camera().position # type: Math.Vector3

    if pos.distSqrTo(self.lastPosition) < 1: return 0.0
    self.lastPosition = pos

    self.clearMarkers()

    i = -1
    for v in self.vegetationData:
      i += 1

      matrix = v['matrix']
      vPos = Math.Vector3(matrix[3][0], matrix[3][1], matrix[3][2])
      
      if pos.distSqrTo(vPos) > 30**2: continue
      
      modelName = v['asset'].replace('.srt', '') + ' [' + str(i) + ']'
      self.markers.append(gizmos.createMarker(vPos, size=5, text=modelName))

      for l in drawBasis(matrix, 1): self.markers.append(l)

    return 0.0

  def onShowPositions(self, isEnabled):
    self.showPositions = isEnabled

    if not self.prepareColliders(): return

    if isEnabled: self.delayCallback(0.0, self.update)
    else:
      self.stopCallback(self.update)
      self.clearMarkers()

  def onShowColliders(self, isEnabled):

    if isEnabled:

      if not self.showColliders:
        self.showColliders = True
        if not self.prepareColliders():
          self.showColliders = False
          return

        self.loadColliders()
        self.registerTreeFallHook()
        self.syncFallenTreeStates()
        self.displayColliders()

    else:
      if self.showColliders:
        self.showColliders = False
        self.unregisterTreeFallHook()

        self.hideColliders()
        
  def prepareColliders(self):
    if not isPlayerAvatar(): return
    
    arenaName = BigWorld.player().arena.arenaType.geometryName
    if arenaName != self.vegetationDataArena: self.loadMapFromSpaceBin(arenaName)
    if arenaName != self.vegetationDataArena: return False

    return True
