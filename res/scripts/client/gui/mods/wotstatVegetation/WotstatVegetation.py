import BigWorld
import Math
import DestructiblesCache
import AreaDestructibles
from PlayerEvents import g_playerEvents
from adisp import adisp_process
from shared_utils import awaitNextFrame
from helpers.CallbackDelayer import CallbackDelayer
from helpers import isPlayerAvatar

from . import BigWorldCompat
from .colliderCache import VegetationColliderCache
from .logger import log
from .mapCache import loadMapVegetation
from .runtimeCache import densityVariant
from .treeFallRuntime import registerTreeFallHandler, unregisterTreeFallHandler
from .treeFallTransform import fallenTreeMatrixRows, solvedRestingTreePose
from .visibilityMask import currentVisibilityMask, filterVegetationByVisibility

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
    self.visibleVegetationData = []
    self.vegetationDataArena = ''
    self.activeVisibilityMask = None
    self.visibilityFilterApplied = False

    self.showPositions = False
    self.showColliders = False
    self.onlyCamouflable = True

    self.colliders = []
    self.colliderInstances = []
    self.collidersArena = ''
    self.collidersVisibilityMask = None
    self.collidersOnlyCamouflable = None
    self.collidersProcessing = False
    self.collidersVisible = False
    self.colliderCache = None
    self.treeColliderByID = {}
    self.treeColliderStates = {}
    self.treeFallHookRegistered = False

    self.lastPosition = Math.Vector3(0, 0, 0)
    self.markers = []

    self.panel = ui.createPanel('Vegetation')
    self.checkboxShowPositions = self.panel.addCheckboxLine('Show positions (30m)', self.showPositions, onToggleCallback=self.onShowPositions)
    self.checkboxShowColliders = self.panel.addCheckboxLine('Show colliders', self.showColliders, onToggleCallback=self.onShowColliders)
    self.checkboxOnlyCamuflagable = self.panel.addCheckboxLine('  Only camuflagable', self.onlyCamouflable, onToggleCallback=self.onOnlyCamouflable)
    g_playerEvents.onAvatarBecomeNonPlayer += self.onAvatarBecomeNonPlayer

  def dispose(self):
    self.showColliders = False
    g_playerEvents.onAvatarBecomeNonPlayer -= self.onAvatarBecomeNonPlayer
    self.stopCallback(self.update)
    self.clearMarkers()
    self.unregisterTreeFallHook()
    self.hideColliders()

  def onAvatarBecomeNonPlayer(self):
    self.resetArenaRuntimeState('avatar become non-player')

  def resetArenaRuntimeState(self, reason):
    self.showColliders = False
    self.showPositions = False
    self.stopCallback(self.update)
    self.clearMarkers()
    self.unregisterTreeFallHook()
    self.clearColliderInstances()
    self.collidersProcessing = False
    self.vegetationData = []
    self.visibleVegetationData = []
    self.vegetationDataArena = ''
    self.activeVisibilityMask = None
    self.visibilityFilterApplied = False
    self.checkboxShowColliders.isChecked = False
    self.checkboxShowPositions.isChecked = False
    log('arena runtime state reset: ' + str(reason))

  def getColliderCache(self):
    preferencesPath = BigWorldCompat.getPreferencesFilePath()
    if self.colliderCache is None or self.colliderCache.preferencesPath != preferencesPath:
      self.colliderCache = VegetationColliderCache(preferencesPath, VERSION)
    return self.colliderCache

  def loadMapFromSpaceBin(self, mapName):
    if self.vegetationDataArena == mapName: return

    vegetation = loadMapVegetation(mapName, BigWorldCompat.getPreferencesFilePath(), VERSION)
    if vegetation is None:
      self.vegetationData = []
      self.visibleVegetationData = []
      self.visibilityFilterApplied = False
      self.vegetationDataArena = ''
      return

    self.vegetationData = vegetation
    self.visibleVegetationData = vegetation
    self.visibilityFilterApplied = False
    self.vegetationDataArena = mapName

  def updateVisibilityFilter(self):
    self.activeVisibilityMask = currentVisibilityMask()
    self.visibleVegetationData = filterVegetationByVisibility(self.vegetationData, self.activeVisibilityMask)
    self.visibilityFilterApplied = True

  def loadColliders(self):
    if (
      self.collidersArena == self.vegetationDataArena and
      self.collidersVisibilityMask == self.activeVisibilityMask and
      self.collidersOnlyCamouflable == self.onlyCamouflable and
      self.colliders
    ):
      return

    self.clearColliderInstances()
    self.collidersArena = self.vegetationDataArena
    self.collidersVisibilityMask = self.activeVisibilityMask
    self.collidersOnlyCamouflable = self.onlyCamouflable
    colliderCache = self.getColliderCache()
    modelPathByAsset = {}
    densityMetadataByAsset = {}
    failedAssets = {}
    skippedRed = 0

    vegetation = self.visibleVegetationData if self.visibilityFilterApplied else self.vegetationData
    for v in vegetation:
      asset = v['asset']
      assetKey = asset.lower()

      if assetKey in failedAssets:
        continue

      if assetKey not in densityMetadataByAsset:
        densityMetadataByAsset[assetKey] = colliderCache.densities.metadataFor(asset)
      densityMetadata = densityMetadataByAsset[assetKey]
      if self.onlyCamouflable and densityVariant(densityMetadata.get('camouflageDensity')) == 'red':
        skippedRed += 1
        continue

      if assetKey not in modelPathByAsset:
        modelPath = colliderCache.ensureColliderModel(asset)
        if not modelPath:
          failedAssets[assetKey] = True
          continue
        modelPathByAsset[assetKey] = modelPath
      else:
        modelPath = modelPathByAsset[assetKey]
      
      model = BigWorld.Model(modelPath)
      model.castsShadow = False
      
      matrixRows = [list(row) for row in v['matrix']]
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
      ' skipped_red=' + str(skippedRed) +
      ' only_camuflagable=' + str(self.onlyCamouflable) +
      ' tree_ids=' + str(len(self.treeColliderByID))
    )

  def clearColliderInstances(self):
    self.colliders = []
    self.colliderInstances = []
    self.collidersArena = ''
    self.collidersVisibilityMask = None
    self.collidersOnlyCamouflable = None
    self.collidersVisible = False
    self.treeColliderByID = {}
    self.treeColliderStates = {}

  def treeIDText(self, key):
    return 'chunkID=' + str(key[0]) + ' destrIndex=' + str(key[1])

  def addTreeColliderIndex(self, instance):
    if instance.get('chunkID') is None or instance.get('destrIndex') is None:
      return
    key = (int(instance['chunkID']), int(instance['destrIndex']))
    entries = self.treeColliderByID.setdefault(key, [])
    entries.append(instance)

  def registerTreeFallHook(self):
    if self.treeFallHookRegistered:
      return
    if not self.treeColliderByID:
      return
    self.treeFallHookRegistered = registerTreeFallHandler(self.onTreeFall)

  def unregisterTreeFallHook(self):
    if not self.treeFallHookRegistered:
      return
    unregisterTreeFallHandler(self.onTreeFall)
    self.treeFallHookRegistered = False

  def syncFallenTreeStates(self):
    if not self.treeColliderByID:
      return

    chunksChecked = 0
    fallenSeen = 0
    updated = 0
    chunks = {}
    for chunkID, _destrIndex in self.treeColliderByID.keys():
      chunks[chunkID] = True

    for chunkID in chunks.keys():
      controller = AreaDestructibles.g_destructiblesManager.getController(chunkID)
      if controller is None:
        continue
      chunksChecked += 1
      for fallData in controller.fallenTrees:
        decoded = DestructiblesCache.decodeFallenTree(fallData)
        fallenSeen += 1
        destrIndex, fallYaw, fallPitchConstr, fallSpeed = decoded
        if self.onTreeFall(chunkID, destrIndex, fallYaw, fallPitchConstr, fallSpeed, 'sync'):
          updated += 1

    if fallenSeen or updated:
      log(
        'fallen tree state sync: chunks=' + str(chunksChecked) +
        ' fallen=' + str(fallenSeen) +
        ' updated=' + str(updated)
      )

  def onTreeFall(self, chunkID, destrIndex, fallYaw, fallPitchConstr, fallSpeed, source):
    key = (int(chunkID), int(destrIndex))
    instances = self.treeColliderByID.get(key)
    if not instances:
      return False

    state = (fallYaw, fallPitchConstr, fallSpeed)
    if self.treeColliderStates.get(key) == state:
      return False

    spaceID = AreaDestructibles.g_destructiblesManager.getSpaceID()
    if BigWorldCompat.checkDestructibleIsBush(spaceID, key[0], key[1]):
      self.treeColliderStates[key] = state
      return False

    updated = 0
    finalPitchLog = None
    buryDepthLog = None
    fallingParams = BigWorldCompat.getFallingParams(spaceID, key[0], key[1])
    for instance in instances:
      finalPitch, buryDepth = solvedRestingTreePose(
        instance['standingMatrixRows'],
        fallPitchConstr,
        fallingParams,
        BigWorldCompat.solveDestructibleFallPitch
      )
      if finalPitch is not None:
        finalPitchLog = finalPitch
        buryDepthLog = buryDepth
      matrixRows = fallenTreeMatrixRows(
        instance['standingMatrixRows'],
        fallYaw,
        fallPitchConstr,
        finalPitch=finalPitch,
        buryDepth=buryDepth
      )
      self.setColliderTransform(instance, matrixRows)
      updated += 1

    self.treeColliderStates[key] = state
    return True

  def setColliderTransform(self, instance, matrixRows):
    model = instance['model']
    model.delMotor(instance['servo'])
    matrix = toMatrix(matrixRows)
    servo = BigWorld.Servo(matrix)
    model.addMotor(servo)
    instance['servo'] = servo
    instance['currentMatrixRows'] = matrixRows
    instance['fallen'] = True

  @adisp_process
  def displayColliders(self):
    if self.collidersProcessing: return
    if self.collidersVisible:
      return
    self.collidersProcessing = True

    player = BigWorld.player()

    i = 0
    for col in self.colliders:
      player.addModel(col)
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
    self.collidersProcessing = True

    i = 0
    for col in self.colliders:
      player.delModel(col)
      i += 1

      if i % 100 == 0: yield awaitNextFrame()

    self.collidersVisible = False
    log('removed collider models: ' + str(i))
    self.collidersProcessing = False
    if self.showColliders:
      self.displayColliders()
    else:
      self.clearColliderInstances()

  @adisp_process
  def refreshColliders(self):
    if self.collidersProcessing:
      return

    wasShowing = self.showColliders
    self.unregisterTreeFallHook()

    player = BigWorld.player()
    oldColliders = list(self.colliders)
    if oldColliders and self.collidersVisible:
      self.collidersProcessing = True
      removed = 0
      for col in oldColliders:
        player.delModel(col)
        removed += 1

        if removed % 100 == 0: yield awaitNextFrame()

      self.collidersVisible = False
      self.collidersProcessing = False

    self.clearColliderInstances()

    if not wasShowing:
      return
    if not self.prepareColliders():
      self.showColliders = False
      return

    self.loadColliders()
    self.registerTreeFallHook()
    self.syncFallenTreeStates()
    self.displayColliders()

  def clearMarkers(self):
    for marker in self.markers: marker.destroy()
    self.markers = []

  def update(self):
    pos = BigWorld.camera().position # type: Math.Vector3

    if pos.distSqrTo(self.lastPosition) < 1: return 0.0
    self.lastPosition = pos

    self.clearMarkers()

    i = -1
    vegetation = self.visibleVegetationData if self.visibilityFilterApplied else self.vegetationData
    for v in vegetation:
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

  def onOnlyCamouflable(self, isEnabled):
    self.onlyCamouflable = bool(isEnabled)
    log('only camuflagable colliders: ' + str(self.onlyCamouflable))
    if self.showColliders:
      return self.refreshColliders()
        
  def prepareColliders(self):
    if not isPlayerAvatar(): return
    
    arenaName = BigWorld.player().arena.arenaType.geometryName
    if arenaName != self.vegetationDataArena: self.loadMapFromSpaceBin(arenaName)
    if arenaName != self.vegetationDataArena: return False
    self.updateVisibilityFilter()

    return True
