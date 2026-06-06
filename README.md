# wotstat-vegetation

Runtime vegetation camouflage collider visualizer for World of Tanks.

The mod reads the current arena `space.bin`, finds SpeedTree vegetation
instances, extracts `COLLISION` geometry from each referenced `.srt`, exports a
game-loadable `.model + .visual + .primitives` set, and spawns those generated
models in battle with `BigWorld.Model(path)`.

Generated assets are cached under:

```text
getPreferencesFilePath()/mods/wotstat-vegetation/{version}/colliders
getPreferencesFilePath()/mods/wotstat-vegetation/{version}/maps
```

Bundled prebuilt collider models are intentionally not used. The first enable on
a map may parse/generate missing data; later enables reuse the cache.

Shared visualization textures:

```text
density == 0.5  -> mods/wotstat-vegetation/green.dds
density == 0.25 -> mods/wotstat-vegetation/yellow.dds
otherwise       -> mods/wotstat-vegetation/red.dds
```

Local smoke checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/smoke_runtime_cache.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/smoke_runtime_spawner.py
```
