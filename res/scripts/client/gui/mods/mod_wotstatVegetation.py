from .wotstatVegetation.WotstatVegetation import WotstatVegetation

def init():
  global wotstatVegetation
  wotstatVegetation = WotstatVegetation()

def fini():
  wotstatVegetation.dispose()