### | [RU](./README.md) | EN |

# WotStat Vegetation

A mod for displaying vegetation camouflage collisions used in the spotting system. It allows you to study their placement, shape, and behavior, investigate "holes" in bushes, and understand unexpected spotting situations.

> [!NOTE]
> The mod works only in `Replays` and `Training Battles`. In competitive modes — Random, Clan, and Team Battles — the mod will not work.

![Demo](.github/assets/demo-1.jpeg)

## Installation

1. Download the mod file [`wotstat.vegetation_1.0.0.wotmod`](https://github.com/wotstat/wotstat-vegetation/releases/latest).
2. Place it in the `WoT/mods/{CURRENT_GAME_VERSION}/` folder.

## Usage

* `F2` - Show/Hide vegetation collisions.
* `F3` - Show/Hide only camouflage collisions.

### Collision Color Meaning

The collision color depends on its camouflage properties:

* `Green` - adds 50% camouflage.
* `Yellow` - adds 25% camouflage; usually trees without foliage.
* `Red` - the collision does not provide camouflage but exists in the game; usually grass and trees far beyond the map boundaries. The same tree can be either camouflaging or not, this parameter is determined individually for each instance.

### Integration with wotstat-debug-utils

The mod supports integration with [wotstat-debug-utils](https://github.com/wotstat/wotstat-debug-utils).

Open the mod menu (`F2`) and find the `Vegetation` section. There you can control collision visibility, as well as display coordinate markers for all vegetation objects with their names within a 30-meter radius of the camera.

![Settings window](.github/assets/debug-utils-integration-en.png)

![Markers](.github/assets/vegetation-positoins.jpeg)

## Examples

![Demo](.github/assets/demo-2.jpeg)

![Demo](.github/assets/demo-4.jpeg)

![Demo](.github/assets/demo-3.jpeg)

![Demo](.github/assets/demo-5.jpeg)
