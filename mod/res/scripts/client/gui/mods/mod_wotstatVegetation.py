from .wotstatVegetation.WotstatVegetation import WotstatVegetation

wotstatVegetation = None

def init():
  global wotstatVegetation
  wotstatVegetation = WotstatVegetation()

def fini():
  wotstatVegetation.dispose()