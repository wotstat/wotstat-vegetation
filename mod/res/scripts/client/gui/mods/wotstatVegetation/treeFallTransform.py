import math

GRAVITY = 9.81


def isFinite(value):
  if hasattr(math, 'isfinite'):
    return math.isfinite(value)
  return value == value and value != float('inf') and value != float('-inf')


def fallenTreePitch(fallPitchConstr, fallback=None, allowZero=False):
  if fallback is None:
    fallback = math.pi / 2.0
  try:
    pitch = float(fallPitchConstr)
  except (TypeError, ValueError):
    return fallback

  if not isFinite(pitch) or pitch > math.pi:
    return fallback
  if pitch < 0.0 or pitch == 0.0 and not allowZero:
    return fallback

  return pitch


def matrixYScale(matrixRows):
  _validateMatrixRows(matrixRows)
  y = matrixRows[1]
  return math.sqrt(y[0] * y[0] + y[1] * y[1] + y[2] * y[2])


def solvedRestingTreePose(standingMatrixRows, fallPitchConstr, fallingParams, solvePitch):
  pitchConstr = fallenTreePitch(fallPitchConstr)
  scale = matrixYScale(standingMatrixRows)
  mass = _fallingParam(fallingParams, 0, 0, 0.0)
  height = _fallingParam(fallingParams, 0, 1, 0.0)
  buryDepth = _fallingParam(fallingParams, 0, 3, 0.0)
  springStiffness = _fallingParam(fallingParams, 1, 0, 0.0)
  springAngle = _fallingParam(fallingParams, 1, 1, 0.0)

  heightScaled = height * scale
  massScaled = mass * scale * scale * scale
  stiffnessScaled = springStiffness * scale * scale
  weight = GRAVITY * massScaled
  angStiffness = 0.5 * heightScaled * stiffnessScaled
  approxPitch = pitchConstr - 0.5 * springAngle
  finalPitch = solvePitch(weight, angStiffness, pitchConstr - springAngle, approxPitch)
  finalPitch = fallenTreePitch(finalPitch, pitchConstr, allowZero=True)
  return (finalPitch, buryDepth * scale)


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
    pitch = fallenTreePitch(finalPitch, fallenTreePitch(fallPitchConstr), allowZero=True)

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


def _fallingParam(params, row, col, default):
  try:
    value = params.get(row, col)
  except Exception:
    try:
      value = params[row][col]
    except Exception:
      return default
  try:
    value = float(value)
  except (TypeError, ValueError):
    return default
  if not isFinite(value):
    return default
  return value


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
