import BigWorld
import Math

from .colliderCache import VegetationColliderCache
from .logger import log
from .mapCache import loadMapVegetation
from .runtimeCache import normalizeResourcePathForKey
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
    self.collidersArena = ''
    self.collidersProcessing = False
    self.collidersVisible = False
    self.colliderCache = None

    self.lastPosition = Math.Vector3(0, 0, 0)
    self.markers = []

    self.panel = ui.createPanel('Vegetation')
    self.panel.addCheckboxLine('Show positions (30m)', onToggleCallback=self.onShowPositions)
    self.panel.addCheckboxLine('Show colliders', onToggleCallback=self.onShowColliders)

  def dispose(self):
    self.showColliders = False
    self.stopCallback(self.update)
    self.clearMarkers()
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
      
      matrix = toMatrix(v['matrix'])
      servo = BigWorld.Servo(matrix)
      model.addMotor(servo)
      self.colliders.append(model)

    log(
      'prepared collider instances: instances=' + str(len(self.colliders)) +
      ' unique_models=' + str(len(modelPathByAsset)) +
      ' failed_assets=' + str(len(failedAssets))
    )

  def clearColliderInstances(self):
    self.colliders = []
    self.collidersArena = ''
    self.collidersVisible = False

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
      self.colliders = []
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
        self.displayColliders()

    else:
      if self.showColliders:
        self.showColliders = False

        self.hideColliders()
        
  def prepareColliders(self):
    if not isPlayerAvatar(): return
    
    arenaName = BigWorld.player().arena.arenaType.geometryName
    if arenaName != self.vegetationDataArena: self.loadMapFromSpaceBin(arenaName)
    if arenaName != self.vegetationDataArena: return False

    return True
