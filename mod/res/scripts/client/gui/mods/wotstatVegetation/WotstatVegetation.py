import ResMgr
import json
import BigWorld
import Math

from .spaceBinUnpacker import unpackVegetationFromSpaceBin
from adisp import adisp_process
from shared_utils import awaitNextFrame
from helpers.CallbackDelayer import CallbackDelayer
from helpers import isPlayerAvatar

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

    self.lastPosition = Math.Vector3(0, 0, 0)
    self.markers = []

    self.panel = ui.createPanel('Vegetation')
    self.panel.addCheckboxLine('Show positions (30m)', onToggleCallback=self.onShowPositions)
    self.panel.addCheckboxLine('Show colliders', onToggleCallback=self.onShowColliders)

  def dispose(self):
    pass

  def loadMapFromSpaceBin(self, mapName):
    if self.vegetationDataArena == mapName: return
    spacePath = 'spaces/' + mapName + '/space.bin'

    if not ResMgr.isFile(spacePath):
      print('WotstatVegetation: No vegetation data for map ' + mapName)
      self.vegetationData = []
      self.vegetationDataArena = ''
      return

    section = ResMgr.openSection(spacePath)
    try:
      self.vegetationData = unpackVegetationFromSpaceBin(section.asBinary)
      self.vegetationDataArena = mapName
    except Exception as error:
      print('[WOTSTAT-VEGETATION] failed to load vegetation from space.bin: ' + str(error))
      self.vegetationData = []
      self.vegetationDataArena = ''
      return

    print('[WOTSTAT-VEGETATION] loaded ' + str(len(self.vegetationData)) + ' vegetations from space.bin')

  def loadColliders(self):
    if self.collidersArena == self.vegetationDataArena: return

    self.collidersArena = self.vegetationDataArena
    self.colliders = []

    for v in self.vegetationData:
      modelName = 'mods/wotstat-vegetation/colliders/' + v['asset'].replace('.srt', '.model')
      refs = BigWorld.loadResourceListFG([modelName])
      if modelName in refs.failedIDs: continue
      
      model = refs[modelName]
      model.castsShadow = False
      
      matrix = toMatrix(v['matrix'])
      servo = BigWorld.Servo(matrix)
      model.addMotor(servo)
      self.colliders.append(model)

    print('[WOTSTAT-VEGETATION] loaded ' + str(len(self.colliders)) + ' colliders')

  @adisp_process
  def displayColliders(self):
    if self.collidersProcessing: return
    self.collidersProcessing = True

    player = BigWorld.player()

    i = 0
    for col in self.colliders:
      player.addModel(col)
      i += 1

      if i % 100 == 0: yield awaitNextFrame()

    self.collidersProcessing = False
    if not self.showColliders: self.hideColliders()

  @adisp_process
  def hideColliders(self):
    if self.collidersProcessing: return
    self.collidersProcessing = True
    
    player = BigWorld.player()

    i = 0
    for col in self.colliders:
      player.delModel(col)
      i += 1

      if i % 100 == 0: yield awaitNextFrame()

    self.collidersProcessing = False
    if self.showColliders: self.displayColliders()

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
        if not self.prepareColliders(): return

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
