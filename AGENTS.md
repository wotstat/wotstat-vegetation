# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

WotStat Vegetation is a World of Tanks mod that visualizes vegetation camouflage colliders used by the spotting system. It is intended for replays and training battles only, and the runtime restriction logic must remain in place for competitive battle modes.

The mod is packaged as `wotstat.vegetation_<version>.wotmod` and copied as `wotstat.vegetation_<version>.mtmod`.

## Repository Layout

- `res/scripts/client/gui/mods/mod_wotstatVegetation.py` is the WoT mod entry point.
- `res/scripts/client/gui/mods/wotstatVegetation/WotstatVegetation.py` contains the main runtime controller.
- `res/scripts/client/gui/mods/wotstatVegetation/core/` contains cache, parsing, model export, vegetation, and fallen-tree logic.
- `res/scripts/client/gui/mods/wotstatVegetation/core/unpack/` contains binary unpackers/exporters for WoT resources.
- `res/scripts/client/gui/mods/wotstatVegetation/utils/` contains compatibility helpers, restrictions, i18n, logging, battle messages, and visibility filtering.
- `res/mods/wotstat-vegetation/*.dds` are runtime textures used by generated collider models.
- `meta.xml` is the packaged mod metadata template.
- `build.sh` builds the release/debug mod archives.
- `wot-src/` is ignored reference/source material. Do not edit it unless the user explicitly asks.

## Runtime Environment

- The in-game code targets the World of Tanks Python 2 runtime.
- Keep syntax Python 2 compatible: no f-strings, no variable annotations, no keyword-only arguments, and no Python 3-only standard-library APIs.
- WoT/BigWorld modules such as `BigWorld`, `Math`, `ResMgr`, `BattleReplay`, `AreaDestructibles`, `DestructiblesCache`, `PlayerEvents`, and `gui.*` exist only inside the game client.
- Do not replace game API calls with local stand-ins in production code. If local checks are needed, keep them separate from runtime code.

## Coding Conventions

- Preserve the existing two-space indentation style.
- Prefer package-relative imports inside `wotstatVegetation`.
- Use `utils.logger.log()` for mod logging.
- Keep source text ASCII unless a file already contains or needs localized text, such as `utils/i18n.py`.
- Preserve existing placeholder values:
  - `{{VERSION}}` is replaced by `build.sh`.
  - `'{{DEBUG_MODE}}'` is replaced by `build.sh`.
- Keep expensive runtime work incremental where possible. Existing code yields with `awaitNextFrame()` while adding/removing many models.
- Avoid broad refactors around BigWorld callbacks, event registration, or cache formats unless the task specifically requires them.

## Behavior Constraints

- The mod must remain unavailable outside replays and allowed training modes. Respect `utils/Restriction.py` and the user-facing README note.
- `F2` toggles vegetation collider visibility.
- `F3` toggles "only camouflaging" colliders.
- Camouflage is determined per vegetation instance: the asset must have `density > 0` in `destructibles.xml`, and that map instance must have `destrIndex != None`.
- Do not use `vegetation/bushes.xml` or `vegetation/grassBushes.xml` as camouflage fallbacks.
- Collider colors map to camouflage density:
  - green: 50% camouflage
  - yellow: 25% camouflage
  - red: no camouflage effect because density is missing/zero or the instance has no `destrIndex`
- Keep optional `wotstat-debug-utils` integration optional. Imports from `gui.debugUtils` must continue to fail gracefully.

## Caches and Generated Data

- Runtime caches are written under the player preferences path in `mods/wotstat-vegetation/<version>/`.
- Cache helpers live in `core/runtimeCache.py`.
- Preserve cache format version constants unless intentionally changing cache compatibility.
- Do not commit generated `build/`, `.pyc`, `.wotmod`, `.mtmod`, or local runtime cache artifacts.

## Build Commands

Use the provided script:

```bash
./build.sh -v 1.0.0
```

For a debug build:

```bash
./build.sh -v 1.0.0 -d
```

The build script:

- removes and recreates `build/`
- copies `res/`
- substitutes version/debug placeholders
- runs `python2 -m compileall ./build`
- packages compiled `.pyc` files, `meta.xml`, and `.dds` textures
- writes `.wotmod` and `.mtmod` archives at the repository root

## Verification

There is no standard automated test suite in this repository. For code changes:

- Run `./build.sh -v <version>` when Python 2 is available.
- Treat successful packaging as the basic smoke test.
- For logic that depends on WoT APIs, verify in the game client, replay, or training battle when possible.
- If Python 2 or the game client is unavailable, say so clearly in the final response and explain what was checked instead.

## Documentation

- Keep `README.md` and `README_EN.md` aligned when changing public behavior, install steps, hotkeys, supported modes, or screenshots.
- Use English for `README_EN.md` and Russian for `README.md`.
- Update this file when project workflows or important constraints change.
