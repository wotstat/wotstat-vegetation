import BigWorld

getPreferencesFilePath = BigWorld.wg_getPreferencesFilePath if hasattr(BigWorld, 'wg_getPreferencesFilePath') else BigWorld.getPreferencesFilePath
getSpaceItemsVisibilityMask = BigWorld.wg_getSpaceItemsVisibilityMask if hasattr(BigWorld, 'wg_getSpaceItemsVisibilityMask') else BigWorld.getSpaceItemsVisibilityMask
getFallingParams = BigWorld.wg_getFallingParams if hasattr(BigWorld, 'wg_getFallingParams') else BigWorld.getFallingParams
solveDestructibleFallPitch = BigWorld.wg_solveDestructibleFallPitch if hasattr(BigWorld, 'wg_solveDestructibleFallPitch') else BigWorld.solveDestructibleFallPitch
checkDestructibleIsBush = BigWorld.wg_checkDestructibleIsBush if hasattr(BigWorld, 'wg_checkDestructibleIsBush') else BigWorld.checkDestructibleIsBush
