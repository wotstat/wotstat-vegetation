import math
import physics_shared

def fallenTreePitch(fallPitchConstr, fallback=None, allowZero=False):
  if fallback is None:
    fallback = math.pi / 2.0
  pitch = float(fallPitchConstr)

  if pitch > math.pi:
    return fallback
  if pitch < 0.0 or pitch == 0.0 and not allowZero:
    return fallback

  return pitch


def matrixYScale(matrixRows):
  y = matrixRows[1]
  return math.sqrt(y[0] * y[0] + y[1] * y[1] + y[2] * y[2])


def solvedRestingTreePose(standingMatrixRows, fallPitchConstr, fallingParams, solvePitch):
  pitchConstr = fallenTreePitch(fallPitchConstr)
  scale = matrixYScale(standingMatrixRows)
  mass = float(fallingParams.get(0, 0))
  height = float(fallingParams.get(0, 1))
  buryDepth = float(fallingParams.get(0, 3))
  springStiffness = float(fallingParams.get(1, 0))
  springAngle = float(fallingParams.get(1, 1))

  heightScaled = height * scale
  massScaled = mass * scale * scale * scale
  stiffnessScaled = springStiffness * scale * scale
  weight = physics_shared.G * massScaled
  angStiffness = 0.5 * heightScaled * stiffnessScaled
  approxPitch = pitchConstr - 0.5 * springAngle
  finalPitch = solvePitch(weight, angStiffness, pitchConstr - springAngle, approxPitch)
  finalPitch = fallenTreePitch(finalPitch, pitchConstr, allowZero=True)
  return (finalPitch, buryDepth * scale)


def fallenTreeMatrixRows(standingMatrixRows, fallYaw, fallPitchConstr=None, finalPitch=None, buryDepth=0.0):
  yaw = float(fallYaw)

  if finalPitch is None:
    pitch = fallenTreePitch(fallPitchConstr)
  else:
    pitch = fallenTreePitch(finalPitch, fallenTreePitch(fallPitchConstr), allowZero=True)

  buryDepth = float(buryDepth)

  base = [list(row) for row in standingMatrixRows]
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
