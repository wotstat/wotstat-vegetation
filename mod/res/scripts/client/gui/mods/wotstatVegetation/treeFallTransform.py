import math


def isFinite(value):
  if hasattr(math, 'isfinite'):
    return math.isfinite(value)
  return value == value and value != float('inf') and value != float('-inf')


def fallenTreePitch(fallPitchConstr):
  try:
    pitch = float(fallPitchConstr)
  except (TypeError, ValueError):
    pitch = math.pi / 2.0

  if not isFinite(pitch) or pitch <= 0.0 or pitch > math.pi:
    return math.pi / 2.0

  return pitch


def fallenTreeMatrixRows(standingMatrixRows, fallYaw, fallPitchConstr=None, finalPitch=None, buryDepth=0.0):
  _validateMatrixRows(standingMatrixRows)
  try:
    yaw = float(fallYaw)
  except (TypeError, ValueError):
    raise ValueError('invalid fall yaw: ' + str(fallYaw))
  if not isFinite(yaw):
    raise ValueError('invalid fall yaw: ' + str(fallYaw))

  if finalPitch is None:
    pitch = fallenTreePitch(fallPitchConstr)
  else:
    pitch = fallenTreePitch(finalPitch)

  try:
    buryDepth = float(buryDepth)
  except (TypeError, ValueError):
    buryDepth = 0.0
  if not isFinite(buryDepth):
    buryDepth = 0.0

  base = _copyMatrixRows(standingMatrixRows)
  translation = list(base[3])
  base[3] = [0.0, 0.0, 0.0, translation[3]]

  matrix = _multiplyRows(base, _rotationYRows(-yaw))
  matrix = _multiplyRows(matrix, _rotationXRows(pitch))
  matrix = _multiplyRows(matrix, _rotationYRows(yaw))
  matrix[3] = [
    translation[0],
    translation[1] - buryDepth * math.sin(pitch),
    translation[2],
    translation[3]
  ]
  return matrix


def _copyMatrixRows(matrixRows):
  return [list(row) for row in matrixRows]


def _validateMatrixRows(matrixRows):
  if matrixRows is None or len(matrixRows) != 4:
    raise ValueError('matrix must have 4 rows')
  for row in matrixRows:
    if row is None or len(row) != 4:
      raise ValueError('matrix rows must have 4 values')
    for value in row:
      try:
        number = float(value)
      except (TypeError, ValueError):
        raise ValueError('matrix contains a non-number value: ' + str(value))
      if not isFinite(number):
        raise ValueError('matrix contains a non-finite value: ' + str(value))


def _multiplyRows(a, b):
  result = []
  for row in range(4):
    resultRow = []
    for col in range(4):
      value = 0.0
      for idx in range(4):
        value += a[row][idx] * b[idx][col]
      resultRow.append(value)
    result.append(resultRow)
  return result


def _rotationXRows(angle):
  c = math.cos(angle)
  s = math.sin(angle)
  return [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, c, s, 0.0],
    [0.0, -s, c, 0.0],
    [0.0, 0.0, 0.0, 1.0]
  ]


def _rotationYRows(angle):
  c = math.cos(angle)
  s = math.sin(angle)
  return [
    [c, 0.0, -s, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [s, 0.0, c, 0.0],
    [0.0, 0.0, 0.0, 1.0]
  ]
